from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme


class AIGenerationPanel(QWidget):
    start_requested = Signal()
    cancel_requested = Signal()
    retry_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "READY"  # READY, PROCESSING, PAUSED, COMPLETED, ERROR

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Status Banner
        self.status_card = QFrame()
        self.status_card.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-left: 4px solid {Theme.SUCCESS}; border-radius: 6px;")
        s_layout = QHBoxLayout(self.status_card)
        s_layout.setContentsMargins(14, 10, 14, 10)

        self.lbl_status = QLabel("● AI ENGINE STATUS: READY")
        self.lbl_status.setStyleSheet(f"font-weight: bold; color: {Theme.SUCCESS}; font-size: 13px; border: none;")
        s_layout.addWidget(self.lbl_status)
        s_layout.addStretch()

        self.lbl_batch_stat = QLabel("Progress: 0 / 0 segments")
        self.lbl_batch_stat.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px; border: none;")
        s_layout.addWidget(self.lbl_batch_stat)
        layout.addWidget(self.status_card)

        # Generation Configuration Form
        cfg_frame = QFrame()
        cfg_frame.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 14px;")
        grid = QGridLayout(cfg_frame)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Generation Pipeline:", styleSheet=f"color: {Theme.TEXT_MUTED}; font-weight: bold;"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Full Pipeline (Whisper AI Text Generation)", "full")
        self.mode_combo.addItem("Timing Only Draft (Fast VAD / Timestamp Split)", "timing")
        grid.addWidget(self.mode_combo, 0, 1)

        grid.addWidget(QLabel("AI Batch Size (Segments):", styleSheet=f"color: {Theme.TEXT_MUTED}; font-weight: bold;"), 1, 0)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 50)
        self.batch_spin.setValue(5)
        grid.addWidget(self.batch_spin, 1, 1)

        grid.addWidget(QLabel("Context Prompt / Glossary:", styleSheet=f"color: {Theme.TEXT_MUTED}; font-weight: bold;"), 2, 0)
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText("Nhập ngữ cảnh, thuật ngữ đặc biệt để AI nhận diện chuẩn xác...")
        grid.addWidget(self.prompt_edit, 2, 1)

        layout.addWidget(cfg_frame)

        # Progress Monitor
        prog_frame = QFrame()
        prog_frame.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 12px;")
        p_layout = QVBoxLayout(prog_frame)
        p_layout.setSpacing(8)

        self.lbl_step_info = QLabel("Chờ bắt đầu tác vụ...")
        self.lbl_step_info.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; border: none;")
        p_layout.addWidget(self.lbl_step_info)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setStyleSheet(f"QProgressBar {{ background: {Theme.BG_APP}; border: none; border-radius: 5px; }} QProgressBar::chunk {{ background: {Theme.PRIMARY_GRADIENT}; border-radius: 5px; }}")
        p_layout.addWidget(self.progress_bar)
        layout.addWidget(prog_frame)

        layout.addStretch()

        # Action Button Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_retry = QPushButton("🔄 Thử lại")
        self.btn_retry.setObjectName("btn_secondary")
        self.btn_retry.setEnabled(False)
        self.btn_retry.clicked.connect(self.retry_requested.emit)
        btn_row.addWidget(self.btn_retry)

        self.btn_cancel = QPushButton("Hủy tác vụ")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        btn_row.addWidget(self.btn_cancel)

        self.btn_start = QPushButton("▶ Bắt đầu xử lý AI")
        self.btn_start.setObjectName("btn_primary")
        self.btn_start.clicked.connect(self.start_requested.emit)
        btn_row.addWidget(self.btn_start, stretch=1)

        layout.addLayout(btn_row)

    def set_state(self, state_name, msg=None):
        self.state = state_name.upper()
        if self.state == "PROCESSING":
            self.lbl_status.setText("● AI ENGINE: ĐANG XỬ LÝ...")
            self.status_card.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-left: 4px solid {Theme.WARNING}; border-radius: 6px;")
            self.lbl_status.setStyleSheet(f"font-weight: bold; color: {Theme.WARNING}; font-size: 13px; border: none;")
            self.btn_start.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.btn_retry.setEnabled(False)
        elif self.state == "ERROR":
            self.lbl_status.setText("● AI ENGINE: LỖI TIẾN TRÌNH")
            self.status_card.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-left: 4px solid {Theme.DANGER}; border-radius: 6px;")
            self.lbl_status.setStyleSheet(f"font-weight: bold; color: {Theme.DANGER}; font-size: 13px; border: none;")
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.btn_retry.setEnabled(True)
        elif self.state == "COMPLETED":
            self.lbl_status.setText("● AI ENGINE: HOÀN TẤT")
            self.status_card.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-left: 4px solid {Theme.SUCCESS}; border-radius: 6px;")
            self.lbl_status.setStyleSheet(f"font-weight: bold; color: {Theme.SUCCESS}; font-size: 13px; border: none;")
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.btn_retry.setEnabled(False)
        else:
            self.lbl_status.setText("● AI ENGINE: READY")
            self.status_card.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-left: 4px solid {Theme.SUCCESS}; border-radius: 6px;")
            self.lbl_status.setStyleSheet(f"font-weight: bold; color: {Theme.SUCCESS}; font-size: 13px; border: none;")
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.btn_retry.setEnabled(False)

        if msg:
            self.lbl_step_info.setText(msg)