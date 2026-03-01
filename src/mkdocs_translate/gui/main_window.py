import asyncio
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QMessageBox, QStatusBar, QToolBar, QSplitter, QFileDialog
)
from PySide6.QtCore import QThread, Signal, Slot, QObject, Qt, QEvent
from PySide6.QtGui import QAction, QCloseEvent

from mkdocs_translate.models.config import AppConfig
from mkdocs_translate.core.processor import Processor
from mkdocs_translate.models.task import TaskStatus, TranslationTask, ProjectState
from mkdocs_translate.gui.widgets.file_selector import FileSelector
from mkdocs_translate.gui.widgets.progress_panel import ProgressPanel
from mkdocs_translate.gui.widgets.settings_dialog import SettingsDialog
from mkdocs_translate.gui.widgets.task_list import TaskListView

class WorkerSignals(QObject):
    progress = Signal(object) # TranslationTask
    finished = Signal()
    error = Signal(str)

class TranslationWorker(QThread):
    def __init__(self, processor, tasks):
        super().__init__()
        self.processor = processor
        self.tasks = tasks
        self.signals = WorkerSignals()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def on_progress(task):
            self.signals.progress.emit(task)

        try:
            loop.run_until_complete(
                self.processor.process_tasks(self.tasks, on_progress)
            )
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            loop.close()

    def stop(self):
        self.processor.stop()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MkDocs Translate")
        self.resize(1000, 700)
        
        # Load Config
        try:
            self.config = AppConfig.load()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", f"Failed to load {AppConfig.default_path()}: {e}\nUsing defaults.")
            self.config = AppConfig()
        self.processor = Processor(self.config)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        # Toolbar
        self.setup_toolbar()

        # Splitter for better layout
        self.splitter = QSplitter(Qt.Vertical)
        
        # Top Panel (File Selector + Progress + Buttons)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.file_selector = FileSelector()
        self.progress_panel = ProgressPanel()
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_scan = QPushButton("Scan Files")
        self.btn_start = QPushButton("Start Translation")
        self.btn_stop = QPushButton("Stop")
        self.btn_retry = QPushButton("Retry Failed")
        self.btn_save = QPushButton("Save Project")
        self.btn_load = QPushButton("Load Project")
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_retry.setEnabled(False)
        
        btn_layout.addWidget(self.btn_scan)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_retry)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_load)
        
        top_layout.addWidget(self.file_selector)
        top_layout.addWidget(self.progress_panel)
        top_layout.addLayout(btn_layout)
        
        # Bottom Panel (Task List)
        self.task_list = TaskListView()
        
        # Add to splitter
        self.splitter.addWidget(top_widget)
        self.splitter.addWidget(self.task_list)
        self.splitter.setStretchFactor(1, 1) # Give more space to list
        
        self.main_layout.addWidget(self.splitter)
        
        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Logic State
        self.tasks = []
        self.worker = None

        # Signals
        self.btn_scan.clicked.connect(self.scan_files)
        self.btn_start.clicked.connect(self.start_translation)
        self.btn_stop.clicked.connect(self.stop_translation)
        self.btn_retry.clicked.connect(self.retry_failed)
        self.btn_save.clicked.connect(self.save_project)
        self.btn_load.clicked.connect(self.load_project)
        self.file_selector.paths_changed.connect(self.on_paths_changed)

    def closeEvent(self, event: QCloseEvent):
        """Handle application closure to ensure threads are stopped."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "Exit Confirmation",
                "Translation is still in progress. Are you sure you want to stop and exit?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.status_bar.showMessage("Stopping background tasks...")
                # Stop the processor logic
                self.worker.stop()
                # Wait for the thread to finish cleanly
                self.worker.quit()
                self.worker.wait(5000) # Wait up to 5 seconds
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        action_settings = QAction("Settings", self)
        action_settings.triggered.connect(self.open_settings)
        toolbar.addAction(action_settings)

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            new_config = dialog.get_new_config()
            self.config = new_config
            self.config.save()
            self.processor.update_config(self.config)
            self.status_bar.showMessage("Settings saved", 3000)

    def on_paths_changed(self):
        self.btn_start.setEnabled(False)
        self.tasks = []
        self.progress_panel.reset()
        self.task_list.task_model.set_tasks([])
        self.btn_retry.setEnabled(False)

    def scan_files(self):
        src = self.file_selector.src_edit.text()
        dest = self.file_selector.dest_edit.text()
        
        if not src or not dest:
            QMessageBox.warning(self, "Input Error", "Please select source and destination paths.")
            return

        try:
            self.tasks = self.processor.scan_directory(Path(src), Path(dest))
            count = len(self.tasks)
            # Update panel and list
            self.progress_panel.update_progress(count, 0, 0, count)
            self.task_list.task_model.set_tasks(self.tasks)
            
            self.status_bar.showMessage(f"Found {count} files to process")
            self.btn_start.setEnabled(count > 0)
            self.btn_retry.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", str(e))

    def start_translation(self):
        provider = self.config.get_active_provider()
        if not provider.api_key:
             QMessageBox.warning(self, "Configuration Error", "Please set API Key for the active provider in Settings.")
             self.open_settings()
             return

        self.btn_start.setEnabled(False)
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.file_selector.setEnabled(False)
        self.btn_retry.setEnabled(False)
        self.btn_load.setEnabled(False)
        
        self.worker = TranslationWorker(self.processor, self.tasks)
        self.worker.signals.progress.connect(self.on_worker_progress)
        self.worker.signals.finished.connect(self.on_worker_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.start()
        
    def retry_failed(self):
        failed_tasks = [t for t in self.tasks if t.status == TaskStatus.FAILED]
        if not failed_tasks:
            QMessageBox.information(self, "Info", "No failed tasks to retry.")
            return

        # Reset failed tasks to PENDING
        for t in failed_tasks:
            t.reset()
            # Also notify the view that these rows changed
            try:
                idx = self.tasks.index(t)
                self.task_list.task_model.update_task_at(idx)
            except ValueError:
                pass
        
        self.start_translation()
    
    def save_project(self):
        if not self.tasks:
            QMessageBox.warning(self, "Warning", "No tasks to save.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "YAML Files (*.yaml *.yml)")
        if not path:
            return
            
        try:
            src = Path(self.file_selector.src_edit.text())
            dest = Path(self.file_selector.dest_edit.text())
            project = ProjectState(source_dir=src, dest_dir=dest, tasks=self.tasks)
            project.save_to_file(Path(path))
            self.status_bar.showMessage(f"Project saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "YAML Files (*.yaml *.yml)")
        if not path:
            return
            
        try:
            project = ProjectState.load_from_file(Path(path))
            self.file_selector.src_edit.setText(str(project.source_dir))
            self.file_selector.dest_edit.setText(str(project.dest_dir))
            
            self.tasks = project.tasks
            
            # Clean up PROCESSING tasks which might be stale
            for task in self.tasks:
                if task.status == TaskStatus.PROCESSING:
                    task.reset()
            
            # Update UI
            count = len(self.tasks)
            completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
            pending = sum(1 for t in self.tasks if t.status in (TaskStatus.PENDING, TaskStatus.PROCESSING))
            
            self.progress_panel.update_progress(pending, completed, failed, count)
            self.task_list.task_model.set_tasks(self.tasks)
            
            self.status_bar.showMessage(f"Loaded project from {path}")
            
            # Reset UI states based on loaded data
            self.btn_start.setEnabled(pending > 0 or failed > 0)
            if failed > 0:
                self.btn_retry.setEnabled(True)
                
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def stop_translation(self):
        if self.worker:
            self.btn_stop.setEnabled(False)
            self.status_bar.showMessage("Stopping...")
            self.worker.stop()
            # Immediately reset processing tasks to PENDING for visibility.
            for task in self.tasks:
                if task.status == TaskStatus.PROCESSING:
                    task.reset()
            self.task_list.task_model.refresh_all()
            completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
            pending = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)
            self.progress_panel.update_progress(pending, completed, failed, len(self.tasks), "Stopped")

    def on_worker_progress(self, task: TranslationTask):
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        pending = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)
        processing = sum(1 for t in self.tasks if t.status == TaskStatus.PROCESSING)
        
        total_pending = pending + processing
        total = len(self.tasks)
        
        self.progress_panel.update_progress(total_pending, completed, failed, total, task.name)
        
        # Update Table View
        try:
            idx = self.tasks.index(task)
            self.task_list.task_model.update_task_at(idx)
        except ValueError:
            pass

    def on_worker_finished(self):
        self.status_bar.showMessage("Processing finished")
        
        # Clean up any leftover PROCESSING tasks (just in case)
        for task in self.tasks:
            if task.status == TaskStatus.PROCESSING:
                task.reset()
        
        self.task_list.task_model.refresh_all() # SAFER full refresh
        
        self.reset_ui_state()
        
        failed_count = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        if failed_count > 0:
             self.btn_retry.setEnabled(True)
             QMessageBox.warning(self, "Finished", f"Finished with {failed_count} errors. You can click 'Retry Failed'.")
        else:
             QMessageBox.information(self, "Finished", "All translation tasks completed.")

    def on_worker_error(self, error_msg):
        self.status_bar.showMessage(f"Error: {error_msg}")
        self.reset_ui_state()
        QMessageBox.critical(self, "Error", str(error_msg))

    def reset_ui_state(self):
        self.btn_start.setEnabled(True)
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.file_selector.setEnabled(True)
        self.worker = None
        self.btn_load.setEnabled(True)
        
        # Check if we should enable retry
        if any(t.status == TaskStatus.FAILED for t in self.tasks):
            self.btn_retry.setEnabled(True)
