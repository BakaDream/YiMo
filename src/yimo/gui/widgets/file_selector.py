from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Signal, Qt

class FileSelector(QWidget):
    # Signal emitted when paths change: (source_path, dest_path, mode)
    paths_changed = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Mode Selection
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        
        self.radio_dir = QRadioButton("Directory Mode")
        self.radio_file = QRadioButton("Single File Mode")
        self.radio_dir.setChecked(True)
        
        self.mode_group.addButton(self.radio_dir, 1)
        self.mode_group.addButton(self.radio_file, 2)
        
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.radio_dir)
        mode_layout.addWidget(self.radio_file)
        mode_layout.addStretch()
        
        self.layout.addLayout(mode_layout)

        # Source Selection
        src_layout = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("Select source directory or file...")
        self.src_btn = QPushButton("Browse Source")
        src_layout.addWidget(QLabel("Source:"))
        src_layout.addWidget(self.src_edit)
        src_layout.addWidget(self.src_btn)
        self.layout.addLayout(src_layout)

        # Destination Selection
        dest_layout = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Select destination directory...")
        self.dest_btn = QPushButton("Browse Output")
        dest_layout.addWidget(QLabel("Output:"))
        dest_layout.addWidget(self.dest_edit)
        dest_layout.addWidget(self.dest_btn)
        self.layout.addLayout(dest_layout)

        # Connections
        self.src_btn.clicked.connect(self.browse_source)
        self.dest_btn.clicked.connect(self.browse_dest)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        self.src_edit.textChanged.connect(self.emit_paths)
        self.dest_edit.textChanged.connect(self.emit_paths)

    def browse_source(self):
        if self.radio_dir.isChecked():
            path = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select Markdown File", "", "Markdown Files (*.md *.markdown)")
        
        if path:
            self.src_edit.setText(path)
            # Auto-suggest destination if empty
            if not self.dest_edit.text():
                p = Path(path)
                if self.radio_dir.isChecked():
                    suggested = p.parent / (p.name + "-zh")
                else:
                    suggested = p.parent / (p.stem + "-zh" + p.suffix)
                self.dest_edit.setText(str(suggested))

    def browse_dest(self):
        if self.radio_dir.isChecked():
            path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        else:
            # For single file output, we still typically select a target file path, 
            # but picking a directory is also common. Let's stick to Save File for single file mode.
             path, _ = QFileDialog.getSaveFileName(self, "Select Output File", self.dest_edit.text())

        if path:
            self.dest_edit.setText(path)

    def on_mode_changed(self):
        self.src_edit.clear()
        self.dest_edit.clear()
        self.emit_paths()

    def emit_paths(self):
        mode = "directory" if self.radio_dir.isChecked() else "file"
        self.paths_changed.emit(self.src_edit.text(), self.dest_edit.text(), mode)
