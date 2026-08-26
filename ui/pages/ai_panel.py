from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QLineEdit, QProgressBar
)
from ui.theme import Theme

class AIGenerationPanel(QWidget):
    # [S7.1-E] Thêm các Signal chuyên biệt cho Timing Batch
    start_requested = Signal()
    continue_requested = Signal() 
    cancel_requested = Signal()
    retry_requested = Signal()

    def __init__(self):
        super().__init__()
        self.state = "IDLE"
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        # Reduced margins and spacing for a tighter look
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- TOP CONTROLS ---
        ctrl_layout = QHBoxLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("⏱ Timing Batch (Lưu Checkpoint)", "timing")
        self.mode_combo.addItem("📝 Fill Text (Điền chữ AI)", "fill_text")
        
        lbl_batch = QLabel("Batch Size:")
        self.batch_combo = QComboBox()
        self.batch_combo.addItems(["5", "10", "20"])
        self.batch_combo.setCurrentText("10")
        
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 100)
        self.batch_spin.setValue(10)
        self.batch_spin.hide() # Ẩn đi, chỉ dùng cho chế độ Text

        ctrl_layout.addWidget(QLabel("Chế độ:"))
        ctrl_layout.addWidget(self.mode_combo)
        ctrl_layout.addWidget(lbl_batch)
        ctrl_layout.addWidget(self.batch_combo)
        ctrl_layout.addWidget(self.batch_spin)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # --- PROMPT ---
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setMinimumHeight(36) # Cho ô text to ra một chút
        self.prompt_edit.setPlaceholderText("Gợi ý ngữ cảnh, tên riêng, thuật ngữ cho AI...")
        layout.addWidget(self.prompt_edit)

        # [FIX UX] Thêm lò xo đẩy mọi thứ xuống đáy
        layout.addStretch()

        # --- STATUS & PROGRESS ---
        status_layout = QHBoxLayout()
        self.lbl_step_info = QLabel("Sẵn sàng.")
        self.lbl_step_info.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-weight: bold;")
        
        self.lbl_checkpoint_info = QLabel("Chưa có Checkpoint")
        self.lbl_checkpoint_info.setStyleSheet(f"color: {Theme.CYAN}; font-weight: bold;")
        self.lbl_batch_stat = self.lbl_checkpoint_info 
        
        status_layout.addWidget(self.lbl_step_info)
        status_layout.addStretch()
        status_layout.addWidget(self.lbl_checkpoint_info)
        layout.addLayout(status_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # --- ACTION BUTTONS ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8) # Giảm khoảng cách giữa các nút
        
        # [FIX UX] Đồng bộ kích thước các nút
        self.btn_start = QPushButton("▶ Start Mới")
        self.btn_start.setMinimumSize(110, 32)
        self.btn_start.setObjectName("btn_primary")
        self.btn_start.clicked.connect(self.start_requested.emit)
        
        self.btn_continue = QPushButton("⏭ Continue")
        self.btn_continue.setMinimumSize(110, 32)
        self.btn_continue.setObjectName("btn_success")
        self.btn_continue.clicked.connect(self.continue_requested.emit)
        
        self.btn_retry = QPushButton("↻ Retry")
        self.btn_retry.setMinimumSize(110, 32)
        self.btn_retry.setObjectName("btn_warning")
        self.btn_retry.clicked.connect(self.retry_requested.emit)
        self.btn_retry.hide()
        
        self.btn_cancel = QPushButton("■ Cancel")
        self.btn_cancel.setMinimumSize(110, 32)
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        self.btn_cancel.setEnabled(False)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_continue)
        btn_layout.addWidget(self.btn_retry)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch() # Đẩy các nút sang trái gọn gàng
        
        layout.addLayout(btn_layout)
        
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

    def _on_mode_changed(self, text):
        if self.mode_combo.currentData() == "timing":
            self.batch_combo.show()
            self.batch_spin.hide()
            self.btn_continue.show()
        else:
            self.batch_combo.hide()
            self.batch_spin.show()
            self.btn_continue.hide()

    def set_state(self, state, msg=""):
        self.state = state
        if msg:
            self.lbl_step_info.setText(msg)
            
        is_running = state in ["PROCESSING", "RUNNING"]
        self.btn_start.setEnabled(not is_running)
        self.btn_continue.setEnabled(not is_running)
        self.btn_cancel.setEnabled(is_running)
        self.batch_combo.setEnabled(not is_running)
        self.mode_combo.setEnabled(not is_running)
        
        if state == "FAILED":
            self.btn_retry.show()
            self.btn_continue.hide()
        else:
            self.btn_retry.hide()
            
            # Chỉ hiện nút Continue nếu đang ở chế độ Timing
            if self.mode_combo.currentData() == "timing":
                self.btn_continue.show()
