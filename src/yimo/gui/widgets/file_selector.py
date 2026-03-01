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
        self._i18n = None
        self.layout = QVBoxLayout(self)
        
        # Mode Selection
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        
        self.radio_dir = QRadioButton("")
        self.radio_file = QRadioButton("")
        self.radio_dir.setChecked(True)
        
        self.mode_group.addButton(self.radio_dir, 1)
        self.mode_group.addButton(self.radio_file, 2)
        
        self.mode_label = QLabel("")
        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.radio_dir)
        mode_layout.addWidget(self.radio_file)
        mode_layout.addStretch()
        
        self.layout.addLayout(mode_layout)

        # Source Selection
        src_layout = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_btn = QPushButton("")
        self.src_label = QLabel("")
        src_layout.addWidget(self.src_label)
        src_layout.addWidget(self.src_edit)
        src_layout.addWidget(self.src_btn)
        self.layout.addLayout(src_layout)

        # Destination Selection
        dest_layout = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_btn = QPushButton("")
        self.dest_label = QLabel("")
        dest_layout.addWidget(self.dest_label)
        dest_layout.addWidget(self.dest_edit)
        dest_layout.addWidget(self.dest_btn)
        self.layout.addLayout(dest_layout)

        # Connections
        self.src_btn.clicked.connect(self.browse_source)
        self.dest_btn.clicked.connect(self.browse_dest)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        self.src_edit.textChanged.connect(self.emit_paths)
        self.dest_edit.textChanged.connect(self.emit_paths)

        self.retranslate_ui(self._i18n)

    def retranslate_ui(self, i18n) -> None:
        self._i18n = i18n
        if self._i18n is None:
            self.mode_label.setText("Mode:")
            self.radio_dir.setText("Directory Mode")
            self.radio_file.setText("Single File Mode")
            self.src_label.setText("Source:")
            self.src_edit.setPlaceholderText("Select source directory or file...")
            self.src_btn.setText("Browse Source")
            self.dest_label.setText("Output:")
            self.dest_edit.setPlaceholderText("Select destination directory...")
            self.dest_btn.setText("Browse Output")
            return

        self.mode_label.setText(self._i18n.t("fs.mode"))
        self.radio_dir.setText(self._i18n.t("fs.mode.dir"))
        self.radio_file.setText(self._i18n.t("fs.mode.file"))
        self.src_label.setText(self._i18n.t("fs.source"))
        self.src_edit.setPlaceholderText(self._i18n.t("fs.placeholder.src"))
        self.src_btn.setText(self._i18n.t("fs.browse_source"))
        self.dest_label.setText(self._i18n.t("fs.output"))
        self.dest_edit.setPlaceholderText(self._i18n.t("fs.placeholder.dest"))
        self.dest_btn.setText(self._i18n.t("fs.browse_output"))

    def browse_source(self):
        if self.radio_dir.isChecked():
            caption = self._i18n.t("dlg.select_src_dir") if self._i18n else "Select Source Directory"
            path = QFileDialog.getExistingDirectory(self, caption)
        else:
            caption = self._i18n.t("dlg.select_md_file") if self._i18n else "Select Markdown File"
            filter_text = self._i18n.t("dlg.md_filter") if self._i18n else "Markdown Files (*.md *.markdown)"
            path, _ = QFileDialog.getOpenFileName(self, caption, "", filter_text)
        
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
            caption = self._i18n.t("dlg.select_output_dir") if self._i18n else "Select Output Directory"
            path = QFileDialog.getExistingDirectory(self, caption)
        else:
            # For single file output, we still typically select a target file path, 
            # but picking a directory is also common. Let's stick to Save File for single file mode.
            caption = self._i18n.t("dlg.select_output_file") if self._i18n else "Select Output File"
            path, _ = QFileDialog.getSaveFileName(self, caption, self.dest_edit.text())

        if path:
            self.dest_edit.setText(path)

    def on_mode_changed(self):
        self.src_edit.clear()
        self.dest_edit.clear()
        self.emit_paths()

    def emit_paths(self):
        mode = "directory" if self.radio_dir.isChecked() else "file"
        self.paths_changed.emit(self.src_edit.text(), self.dest_edit.text(), mode)
