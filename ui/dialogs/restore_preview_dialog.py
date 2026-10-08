from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame
)

class RestorePreviewDialog(QDialog):
    def __init__(self, current_count: int, target_count: int, manual_edits_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rollback Preview")
        self.setMinimumWidth(300)
        
        self.current_count = current_count
        self.target_count = target_count
        self.manual_edits_count = manual_edits_count
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel(f"<b>Current:</b> {self.current_count} subtitles"))
        layout.addWidget(QLabel(f"<b>Target:</b> {self.target_count} subtitles"))
        
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line1)
        
        diff = self.current_count - self.target_count
        if diff > 0:
            layout.addWidget(QLabel(f"<b>Will remove:</b> {diff} generated changes"))
        elif diff < 0:
            layout.addWidget(QLabel(f"<b>Will restore:</b> {-diff} generated changes"))
        else:
            layout.addWidget(QLabel(f"<b>No changes in count.</b>"))
            
        lbl_manual = QLabel(f"<b>Manual edits detected:</b> {self.manual_edits_count}")
        if self.manual_edits_count > 0:
            lbl_manual.setStyleSheet("color: red; font-weight: bold;")
            warning = QLabel("⚠ Rollback sẽ ghi đè các chỉnh sửa thủ công này.")
            warning.setStyleSheet("color: red; font-style: italic;")
            warning.setWordWrap(True)
            layout.addWidget(lbl_manual)
            layout.addWidget(warning)
        else:
            layout.addWidget(lbl_manual)
            
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_rollback = QPushButton("Rollback")
        self.btn_rollback.setProperty("variant", "danger")
        self.btn_rollback.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_rollback)
        layout.addLayout(btn_layout)
