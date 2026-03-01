import asyncio
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QMessageBox, QStatusBar, QToolBar, QSplitter, QFileDialog
)
from PySide6.QtCore import QThread, Signal, Slot, QObject, Qt, QEvent, QLocale
from PySide6.QtGui import QAction, QCloseEvent

from yimo.models.config import AppConfig
from yimo.core.processor import Processor
from yimo.models.task import TaskStatus, TranslationTask, ProjectState
from yimo.gui.widgets.file_selector import FileSelector
from yimo.gui.widgets.progress_panel import ProgressPanel
from yimo.gui.widgets.settings_dialog import SettingsDialog
from yimo.gui.widgets.task_list import TaskListView
from yimo.i18n.manager import I18nManager

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
        self.i18n = I18nManager()
        self.resize(1000, 700)
        
        # Load Config
        try:
            self.config = AppConfig.load()
        except Exception as e:
            self.config = AppConfig()
            self.i18n.set_from_config(self.config, QLocale.system().name())
            QMessageBox.warning(
                self,
                self.i18n.t("err.config.title"),
                self.i18n.t(
                    "err.config.load_failed",
                    path=str(AppConfig.default_path()),
                    error=str(e),
                ),
            )
        self.i18n.set_from_config(self.config, QLocale.system().name())
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
        self.btn_scan = QPushButton("")
        self.btn_start = QPushButton("")
        self.btn_stop = QPushButton("")
        self.btn_retry = QPushButton("")
        self.btn_save = QPushButton("")
        self.btn_load = QPushButton("")
        
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

        # Initial translations
        self.apply_i18n()

    def apply_i18n(self) -> None:
        self.retranslate_ui()
        self.file_selector.retranslate_ui(self.i18n)
        self.progress_panel.retranslate_ui(self.i18n)
        self.task_list.retranslate_ui(self.i18n)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.i18n.t("app.title"))
        if getattr(self, "toolbar", None) is not None:
            self.toolbar.setWindowTitle(self.i18n.t("main.toolbar"))
        if getattr(self, "action_settings", None) is not None:
            self.action_settings.setText(self.i18n.t("main.settings"))

        self.btn_scan.setText(self.i18n.t("main.scan_files"))
        self.btn_start.setText(self.i18n.t("main.start"))
        self.btn_stop.setText(self.i18n.t("main.stop"))
        self.btn_retry.setText(self.i18n.t("main.retry_failed"))
        self.btn_save.setText(self.i18n.t("main.save_project"))
        self.btn_load.setText(self.i18n.t("main.load_project"))

    def closeEvent(self, event: QCloseEvent):
        """Handle application closure to ensure threads are stopped."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, 
                self.i18n.t("main.exit.title"),
                self.i18n.t("main.exit.body"),
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.status_bar.showMessage(self.i18n.t("main.exit.stopping"))
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
        self.toolbar = QToolBar(self.i18n.t("main.toolbar"))
        self.addToolBar(self.toolbar)
        
        self.action_settings = QAction(self.i18n.t("main.settings"), self)
        self.action_settings.triggered.connect(self.open_settings)
        self.toolbar.addAction(self.action_settings)

    def open_settings(self):
        dialog = SettingsDialog(self.config, self.i18n, self)
        if dialog.exec():
            new_config = dialog.get_new_config()
            self.config = new_config
            self.config.save()
            self.processor.update_config(self.config)
            self.i18n.set_from_config(self.config, QLocale.system().name())
            self.apply_i18n()
            self.status_bar.showMessage(self.i18n.t("main.status.settings_saved"), 3000)

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
            QMessageBox.warning(self, self.i18n.t("err.input.title"), self.i18n.t("err.input.need_paths"))
            return

        try:
            self.tasks = self.processor.scan_directory(Path(src), Path(dest))
            count = len(self.tasks)
            # Update panel and list
            self.progress_panel.update_progress(count, 0, 0, count)
            self.task_list.task_model.set_tasks(self.tasks)
            
            self.status_bar.showMessage(self.i18n.t("main.status.found_files", count=count))
            self.btn_start.setEnabled(count > 0)
            self.btn_retry.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, self.i18n.t("err.scan.title"), str(e))

    def start_translation(self):
        provider = self.config.get_active_provider()
        if not provider.api_key:
             QMessageBox.warning(self, self.i18n.t("warn.config.title"), self.i18n.t("warn.config.need_key"))
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
            QMessageBox.information(self, self.i18n.t("info.title"), self.i18n.t("info.no_failed"))
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
            QMessageBox.warning(self, self.i18n.t("warn.title"), self.i18n.t("warn.no_tasks_save"))
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("dlg.save_project.title"),
            "",
            self.i18n.t("dlg.yaml_filter"),
        )
        if not path:
            return
            
        try:
            src = Path(self.file_selector.src_edit.text())
            dest = Path(self.file_selector.dest_edit.text())
            project = ProjectState(source_dir=src, dest_dir=dest, tasks=self.tasks)
            project.save_to_file(Path(path))
            self.status_bar.showMessage(self.i18n.t("main.status.project_saved", path=path))
        except Exception as e:
            QMessageBox.critical(self, self.i18n.t("err.save.title"), str(e))

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.i18n.t("dlg.load_project.title"),
            "",
            self.i18n.t("dlg.yaml_filter"),
        )
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
            
            self.status_bar.showMessage(self.i18n.t("main.status.project_loaded", path=path))
            
            # Reset UI states based on loaded data
            self.btn_start.setEnabled(pending > 0 or failed > 0)
            if failed > 0:
                self.btn_retry.setEnabled(True)
                
        except Exception as e:
            QMessageBox.critical(self, self.i18n.t("err.load.title"), str(e))

    def stop_translation(self):
        if self.worker:
            self.btn_stop.setEnabled(False)
            self.status_bar.showMessage(self.i18n.t("main.status.stopping"))
            self.worker.stop()
            # Immediately reset processing tasks to PENDING for visibility.
            for task in self.tasks:
                if task.status == TaskStatus.PROCESSING:
                    task.reset()
            self.task_list.task_model.refresh_all()
            completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
            pending = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)
            self.progress_panel.update_progress(pending, completed, failed, len(self.tasks), self.i18n.t("progress.stopped"))

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
        self.status_bar.showMessage(self.i18n.t("main.status.processing_finished"))
        
        # Clean up any leftover PROCESSING tasks (just in case)
        for task in self.tasks:
            if task.status == TaskStatus.PROCESSING:
                task.reset()
        
        self.task_list.task_model.refresh_all() # SAFER full refresh
        
        self.reset_ui_state()
        
        failed_count = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        if failed_count > 0:
             self.btn_retry.setEnabled(True)
             QMessageBox.warning(self, self.i18n.t("done.title"), self.i18n.t("done.with_errors", count=failed_count))
        else:
             QMessageBox.information(self, self.i18n.t("done.title"), self.i18n.t("done.all_ok"))

    def on_worker_error(self, error_msg):
        self.status_bar.showMessage(f"Error: {error_msg}")
        self.reset_ui_state()
        QMessageBox.critical(self, self.i18n.t("err.app.title"), str(error_msg))

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
