from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QLabel, QFrame
)
from PySide6.QtCore import Qt

class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Stats
        stats_layout = QHBoxLayout()
        self.lbl_pending = QLabel("Pending: 0")
        self.lbl_success = QLabel("Success: 0")
        self.lbl_failed = QLabel("Failed: 0")
        
        # Style the labels
        for lbl in [self.lbl_pending, self.lbl_success, self.lbl_failed]:
            lbl.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
            lbl.setAlignment(Qt.AlignCenter)
            # Make the text a bit bigger/bold for readability
            font = lbl.font()
            font.setBold(True)
            lbl.setFont(font)
            stats_layout.addWidget(lbl)
            
        self.layout.addLayout(stats_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.layout.addWidget(self.progress_bar)

        # Log/Status Area
        self.log_label = QLabel("Ready")
        self.log_label.setWordWrap(True)
        self.layout.addWidget(self.log_label)

    def update_progress(self, pending, success, failed, total, current_task_name=""):
        self.lbl_pending.setText(f"Pending: {pending}")
        self.lbl_success.setText(f"Success: {success}")
        self.lbl_failed.setText(f"Failed: {failed}")
        
        processed = success + failed
        
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(processed)
            percent = int((processed / total) * 100)
            self.progress_bar.setFormat(f"{percent}% ({processed}/{total})")
        else:
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("0%")

        if current_task_name:
            self.log_label.setText(f"Last Processed: {current_task_name}")

    def reset(self):
        self.update_progress(0, 0, 0, 0)
        self.log_label.setText("Ready")
        self.progress_bar.setValue(0)

    def set_status(self, text):
        self.log_label.setText(text)