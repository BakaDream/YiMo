from typing import List, Optional
from PySide6.QtWidgets import (
    QTableView, QHeaderView, QAbstractItemView, QMenu, QMessageBox, QApplication, QDialog, QTextEdit, QVBoxLayout, QPushButton
)
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Slot, QUrl
)
from PySide6.QtGui import QAction, QCursor, QDesktopServices
from yimo.models.task import TranslationTask, TaskStatus
from yimo.i18n.manager import I18nManager

class TaskTableModel(QAbstractTableModel):
    def __init__(self, tasks: List[TranslationTask] = None):
        super().__init__()
        self._i18n: I18nManager | None = None
        self._tasks = tasks or []
        self._header_keys = [
            "task.headers.file",
            "task.headers.status",
            "task.headers.retries",
            "task.headers.message",
        ]

    def set_i18n(self, i18n: I18nManager | None) -> None:
        self._i18n = i18n
        if self._header_keys:
            self.headerDataChanged.emit(Qt.Horizontal, 0, len(self._header_keys) - 1)
        if self._tasks:
            start_index = self.index(0, 0)
            end_index = self.index(len(self._tasks) - 1, self.columnCount() - 1)
            self.dataChanged.emit(start_index, end_index)

    def set_tasks(self, tasks: List[TranslationTask]):
        self.beginResetModel()
        self._tasks = tasks
        self.endResetModel()
        
    def get_task(self, row: int) -> Optional[TranslationTask]:
        if 0 <= row < len(self._tasks):
            return self._tasks[row]
        return None

    def update_task_at(self, index_of_task: int):
        # Bounds check to avoid creating invalid indices with valid row numbers but invalid model state
        if index_of_task < 0 or index_of_task >= len(self._tasks):
            return
            
        start_index = self.index(index_of_task, 0)
        end_index = self.index(index_of_task, self.columnCount() - 1)
        
        # Ensure indices are valid before emitting
        if start_index.isValid() and end_index.isValid():
            self.dataChanged.emit(start_index, end_index)
        
    def refresh_all(self):
        """Notify views that all data might have changed (e.g. status reset)"""
        if not self._tasks:
            return
        start_index = self.index(0, 0)
        end_index = self.index(len(self._tasks) - 1, self.columnCount() - 1)
        self.dataChanged.emit(start_index, end_index)

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._tasks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._header_keys)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._tasks)):
            return None

        task = self._tasks[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return task.name
            elif col == 1:
                if self._i18n is None:
                    return task.status.value.upper()
                return self._i18n.t(f"status.{task.status.value}")
            elif col == 2:
                return task.retries # Return int for proper sorting
            elif col == 3:
                return task.error_message or ""
        
        if role == Qt.ForegroundRole:
            if col == 1:
                status = task.status
                if status == TaskStatus.COMPLETED:
                    return Qt.darkGreen
                elif status == TaskStatus.FAILED:
                    return Qt.red
                elif status == TaskStatus.PROCESSING:
                    return Qt.blue
                elif status == TaskStatus.PENDING:
                    return Qt.black
        
        if role == Qt.TextAlignmentRole:
             if col == 2: # Retries
                 return Qt.AlignCenter
                
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self._header_keys):
                key = self._header_keys[section]
                if self._i18n is None:
                    return {
                        "task.headers.file": "File Name",
                        "task.headers.status": "Status",
                        "task.headers.retries": "Retries",
                        "task.headers.message": "Message",
                    }.get(key, key)
                return self._i18n.t(key)
        return None

class MessageDialog(QDialog):
    def __init__(self, title, message, i18n: I18nManager | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)
        self._i18n = i18n
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(message)
        self.text_edit.setReadOnly(True)
        
        self.btn_close = QPushButton(self._i18n.t("task.msg.close") if self._i18n else "Close")
        self.btn_close.setProperty("variant", "secondary")
        self.btn_close.clicked.connect(self.accept)
        
        layout.addWidget(self.text_edit)
        layout.addWidget(self.btn_close)

class TaskListView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._i18n: I18nManager | None = None
        self.task_model = TaskTableModel()
        
        # Proxy model for sorting
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.task_model)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseInsensitive)
        
        self.setModel(self.proxy_model)
        self.setSortingEnabled(True)
        
        # Appearance
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)      # File Name stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Retries
        header.setSectionResizeMode(3, QHeaderView.Stretch) # Message 
        
        # Context Menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def retranslate_ui(self, i18n: I18nManager | None) -> None:
        self._i18n = i18n
        self.task_model.set_i18n(i18n)

    def show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
            
        task = self.get_task_from_proxy_index(index)
        if not task:
            return

        menu = QMenu(self)
        
        # File Operations (Source)
        action_open_file = QAction(self._i18n.t("task.ctx.open_source") if self._i18n else "Open Source File", self)
        action_copy_path = QAction(self._i18n.t("task.ctx.copy_source") if self._i18n else "Copy Source Absolute Path", self)
        
        action_open_file.triggered.connect(lambda: self.open_file(index))
        action_copy_path.triggered.connect(lambda: self.copy_path(index))
        
        menu.addAction(action_open_file)
        menu.addAction(action_copy_path)
        menu.addSeparator()

        # File Operations (Destination)
        action_open_dest = QAction(self._i18n.t("task.ctx.view_dest") if self._i18n else "View Translated File", self)
        action_copy_dest = QAction(self._i18n.t("task.ctx.copy_dest") if self._i18n else "Copy Translated Path", self)
        
        # Check if destination file exists
        dest_exists = task.dest_path.exists()
        action_open_dest.setEnabled(dest_exists)
        action_copy_dest.setEnabled(dest_exists)
        
        action_open_dest.triggered.connect(lambda: self.view_dest_file(task))
        action_copy_dest.triggered.connect(lambda: self.copy_dest_path(task))
        
        menu.addAction(action_open_dest)
        menu.addAction(action_copy_dest)
        menu.addSeparator()

        # Message Operations
        action_copy_msg = QAction(self._i18n.t("task.ctx.copy_msg") if self._i18n else "Copy Message", self)
        action_view_msg = QAction(self._i18n.t("task.ctx.view_msg") if self._i18n else "View Message", self)
        
        action_copy_msg.triggered.connect(lambda: self.copy_message(index))
        action_view_msg.triggered.connect(lambda: self.view_message(index))
        
        menu.addAction(action_copy_msg)
        menu.addAction(action_view_msg)
        
        menu.exec(QCursor.pos())

    def get_task_from_proxy_index(self, index: QModelIndex) -> Optional[TranslationTask]:
        # Ensure the index belongs to the proxy model before mapping
        if index.model() != self.proxy_model:
            return None
            
        source_index = self.proxy_model.mapToSource(index)
        return self.task_model.get_task(source_index.row())

    def open_file(self, index: QModelIndex):
        task = self.get_task_from_proxy_index(index)
        if task and task.source_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(task.source_path.absolute())))
        else:
            title = self._i18n.t("err.app.title") if self._i18n else "Error"
            QMessageBox.warning(self, title, self._i18n.t("task.err.file_missing") if self._i18n else "File does not exist.")

    def copy_path(self, index: QModelIndex):
        task = self.get_task_from_proxy_index(index)
        if task:
            clipboard = QApplication.clipboard()
            clipboard.setText(str(task.source_path.absolute()))

    def view_dest_file(self, task: TranslationTask):
        if task and task.dest_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(task.dest_path.absolute())))
        else:
            title = self._i18n.t("err.app.title") if self._i18n else "Error"
            QMessageBox.warning(
                self,
                title,
                self._i18n.t("task.err.dest_missing") if self._i18n else "Translated file does not exist yet.",
            )

    def copy_dest_path(self, task: TranslationTask):
        if task:
            clipboard = QApplication.clipboard()
            clipboard.setText(str(task.dest_path.absolute()))

    def copy_message(self, index: QModelIndex):
        task = self.get_task_from_proxy_index(index)
        if task and task.error_message:
            clipboard = QApplication.clipboard()
            clipboard.setText(task.error_message)

    def view_message(self, index: QModelIndex):
        task = self.get_task_from_proxy_index(index)
        if task:
            msg = task.error_message or (self._i18n.t("task.msg.none") if self._i18n else "No message.")
            title = (
                self._i18n.t("task.msg.title", name=task.name) if self._i18n else f"Message for {task.name}"
            )
            dialog = MessageDialog(title, msg, i18n=self._i18n, parent=self)
            dialog.exec()
