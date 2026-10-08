from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QRadioButton, QButtonGroup, QFrame
)
from PySide6.QtCore import Qt
from core.subtitle_generation.range_validation import RangeValidationResult, RangeErrorCode, ConflictStrategy

class PreviewRangeDialog(QDialog):
    def __init__(self, start_text: str, end_text: str, result: RangeValidationResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Range Preview")
        self.setMinimumWidth(350)
        
        self.start_text = start_text
        self.end_text = end_text
        self.result = result
        self.selected_strategy = ConflictStrategy.FILL_GAPS_ONLY
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        lbl_range = QLabel(f"<b>Range:</b> {self.start_text} → {self.end_text}")
        layout.addWidget(lbl_range)
        
        duration_sec = self.result.duration_ms / 1000
        mins, secs = divmod(duration_sec, 60)
        lbl_duration = QLabel(f"<b>Duration:</b> {int(mins)}m {int(secs)}s")
        layout.addWidget(lbl_duration)
        
        # Separator
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line1)
        
        # Metrics
        layout.addWidget(QLabel(f"<b>Existing subtitles:</b> {self.result.existing_subtitles_count}"))
        
        lbl_overlap = QLabel(f"<b>Overlap:</b> {self.result.overlapping_count}")
        if self.result.overlapping_count > 0:
            lbl_overlap.setStyleSheet("color: orange;")
        layout.addWidget(lbl_overlap)
        
        lbl_manual = QLabel(f"<b>Manual edits:</b> {self.result.manual_edits_count}")
        if self.result.manual_edits_count > 0:
            lbl_manual.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(lbl_manual)
        
        lbl_gen = QLabel(f"<b>Generated data:</b> {self.result.generated_data_count}")
        layout.addWidget(lbl_gen)
        
        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)
        
        # Strategy
        layout.addWidget(QLabel("<b>Strategy:</b>"))
        
        self.bg_strategy = QButtonGroup(self)
        
        self.rb_fill = QRadioButton("Fill Gaps Only (Default)")
        self.rb_fill.setChecked(True)
        self.bg_strategy.addButton(self.rb_fill, 1)
        layout.addWidget(self.rb_fill)
        
        self.rb_replace = QRadioButton("Replace Overlap")
        self.bg_strategy.addButton(self.rb_replace, 2)
        layout.addWidget(self.rb_replace)
        
        self.rb_cancel = QRadioButton("Cancel")
        self.bg_strategy.addButton(self.rb_cancel, 3)
        layout.addWidget(self.rb_cancel)
        
        # Warning
        if self.result.status.name == "RANGE_TOO_LONG_WARNING":
            lbl_long = QLabel(f"⚠ Khoảng generate rất dài ({self.result.duration_ms//60000} phút) và sẽ được chia thành nhiều batch.")
            lbl_long.setStyleSheet("color: orange;")
            lbl_long.setWordWrap(True)
            layout.addWidget(lbl_long)

        if self.result.manual_edits_count > 0:
            lbl_warning = QLabel(f"⚠ {self.result.manual_edits_count} manual edits nằm trong vùng. Replace Overlap sẽ xóa chúng.")
            lbl_warning.setStyleSheet("color: red; font-style: italic;")
            lbl_warning.setWordWrap(True)
            layout.addWidget(lbl_warning)
            
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel_dialog = QPushButton("Cancel")
        self.btn_cancel_dialog.clicked.connect(self.reject)
        
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setDefault(True)
        self.btn_generate.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_cancel_dialog)
        btn_layout.addWidget(self.btn_generate)
        layout.addLayout(btn_layout)
        
        self.bg_strategy.idToggled.connect(self._on_strategy_changed)
        
    def _on_strategy_changed(self, btn_id, checked):
        if not checked:
            return
        if btn_id == 1:
            self.selected_strategy = ConflictStrategy.FILL_GAPS_ONLY
        elif btn_id == 2:
            self.selected_strategy = ConflictStrategy.REPLACE_OVERLAP
        elif btn_id == 3:
            self.selected_strategy = ConflictStrategy.CANCEL
