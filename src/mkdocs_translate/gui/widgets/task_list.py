from typing import List, Optional
from PySide6.QtWidgets import (
    QTableView, QHeaderView, QAbstractItemView, QMenu, QMessageBox, QApplication, QDialog, QTextEdit, QVBoxLayout, QPushButton
)
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Slot, QUrl
)
from PySide6.QtGui import QAction, QCursor, QDesktopServices
from mkdocs_translate.models.task import TranslationTask, TaskStatus

class TaskTableModel(QAbstractTableModel):
    def __init__(self, tasks: List[TranslationTask] = None):
        super().__init__()
        self._tasks = tasks or []
        self._headers = ["File Name", "Status", "Retries", "Message"]

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
        end_index = self.index(index_of_task, len(self._headers) - 1)
        
        # Ensure indices are valid before emitting
        if start_index.isValid() and end_index.isValid():
            self.dataChanged.emit(start_index, end_index)
        
    def refresh_all(self):
        """Notify views that all data might have changed (e.g. status reset)"""
        if not self._tasks:
            return
        start_index = self.index(0, 0)
        end_index = self.index(len(self._tasks) - 1, len(self._headers) - 1)
        self.dataChanged.emit(start_index, end_index)

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._tasks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._tasks)):
            return None

        task = self._tasks[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return task.name
            elif col == 1:
                return task.status.value.upper()
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
            return self._headers[section]
        return None

class MessageDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(message)
        self.text_edit.setReadOnly(True)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        
        layout.addWidget(self.text_edit)
        layout.addWidget(self.btn_close)

class TaskListView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
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

    def show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
            
        task = self.get_task_from_proxy_index(index)
        if not task:
            return

        menu = QMenu(self)
        
        # File Operations (Source)
        action_open_file = QAction("Open Source File", self)
        action_copy_path = QAction("Copy Source Absolute Path", self)
        
        action_open_file.triggered.connect(lambda: self.open_file(index))
        action_copy_path.triggered.connect(lambda: self.copy_path(index))
        
        menu.addAction(action_open_file)
        menu.addAction(action_copy_path)
        menu.addSeparator()

        # File Operations (Destination)
        action_open_dest = QAction("View Translated File", self)
        action_copy_dest = QAction("Copy Translated Path", self)
        
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
        action_copy_msg = QAction("Copy Message", self)
        action_view_msg = QAction("View Message", self)
        
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
            QMessageBox.warning(self, "Error", "File does not exist.")

    def copy_path(self, index: QModelIndex):
        task = self.get_task_from_proxy_index(index)
        if task:
            clipboard = QApplication.clipboard()
            clipboard.setText(str(task.source_path.absolute()))

    def view_dest_file(self, task: TranslationTask):
        if task and task.dest_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(task.dest_path.absolute())))
        else:
            QMessageBox.warning(self, "Error", "Translated file does not exist yet.")

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
             msg = task.error_message or "No message."
             dialog = MessageDialog(f"Message for {task.name}", msg, self)
             dialog.exec()
