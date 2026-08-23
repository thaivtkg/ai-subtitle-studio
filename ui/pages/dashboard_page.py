from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme


class DashboardPage(QWidget):
    navigate_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 1. Hardware Monitor Grid
        monitor_frame = QFrame()
        monitor_frame.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 8px;")
        grid = QGridLayout(monitor_frame)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(12)

        self.card_gpu_val, card_gpu = self._create_card("GPU ENGINE", "Detecting...", Theme.CYAN)
        self.card_vram_val, card_vram = self._create_card("VRAM ALLOCATION", "-- / -- GB", Theme.PRIMARY_PURPLE)
        self.card_cpu_val, card_cpu = self._create_card("CPU LOAD", "0%", Theme.CYAN)
        self.card_status_val, card_status = self._create_card("SYSTEM STATUS", "Idle", Theme.SUCCESS)

        grid.addWidget(card_gpu, 0, 0)
        grid.addWidget(card_vram, 0, 1)
        grid.addWidget(card_cpu, 1, 0)
        grid.addWidget(card_status, 1, 1)
        layout.addWidget(monitor_frame)

        # 2. Current Session & Quick Actions
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(14)

        # Session State Box
        session_box = QFrame()
        session_box.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px;")
        s_layout = QVBoxLayout(session_box)
        s_layout.setContentsMargins(14, 14, 14, 14)
        s_layout.setSpacing(10)

        lbl_s_title = QLabel("⚡ Current Pipeline Overview")
        lbl_s_title.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {Theme.TEXT_PRIMARY}; border: none;")
        lbl_s_title.setMinimumHeight(20)
        s_layout.addWidget(lbl_s_title)

        self.lbl_queue_overview = QLabel("Queue: 0 items loaded | Output: Default")
        self.lbl_queue_overview.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; border: none;")
        self.lbl_queue_overview.setMinimumHeight(20)
        s_layout.addWidget(self.lbl_queue_overview)

        self.quick_progress = QProgressBar()
        self.quick_progress.setValue(0)
        self.quick_progress.setFixedHeight(8)
        self.quick_progress.setTextVisible(False)  # [FIX] Ẩn text mặc định bị tràn và kẹt ở mép trái
        self.quick_progress.setStyleSheet(f"QProgressBar {{ background: {Theme.BG_APP}; border: none; border-radius: 4px; }} QProgressBar::chunk {{ background: {Theme.PRIMARY_GRADIENT}; border-radius: 4px; }}")
        s_layout.addWidget(self.quick_progress)
        mid_layout.addWidget(session_box, stretch=3)

        # Quick Actions
        actions_box = QFrame()
        actions_box.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px;")
        a_layout = QVBoxLayout(actions_box)
        a_layout.setContentsMargins(14, 14, 14, 14)
        a_layout.setSpacing(10)

        lbl_a_title = QLabel("🚀 Quick Access")
        lbl_a_title.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {Theme.TEXT_PRIMARY}; border: none;")
        lbl_a_title.setMinimumHeight(20)
        a_layout.addWidget(lbl_a_title)

        btn_go_workspace = QPushButton("🎬 Open Workspace")
        btn_go_workspace.setObjectName("btn_secondary")
        btn_go_workspace.setMinimumHeight(28)
        btn_go_workspace.clicked.connect(lambda: self.navigate_requested.emit(1))
        a_layout.addWidget(btn_go_workspace)

        btn_go_queue = QPushButton("📋 View Task Queue")
        btn_go_queue.setObjectName("btn_secondary")
        btn_go_queue.setMinimumHeight(28)
        btn_go_queue.clicked.connect(lambda: self.navigate_requested.emit(3))
        a_layout.addWidget(btn_go_queue)

        mid_layout.addWidget(actions_box, stretch=2)
        layout.addLayout(mid_layout)

        # 3. Recent Activity Log Console
        log_frame = QFrame()
        log_frame.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px;")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(14, 14, 14, 14)
        log_layout.setSpacing(8)

        lbl_log_title = QLabel("📜 Activity Stream")
        lbl_log_title.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {Theme.TEXT_MUTED}; border: none;")
        lbl_log_title.setMinimumHeight(18)
        log_layout.addWidget(lbl_log_title)

        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setPlaceholderText("Hệ thống sẵn sàng...")
        log_layout.addWidget(self.activity_log)

        layout.addWidget(log_frame, stretch=1)

    def _create_card(self, title, val, color):
        f = QFrame()
        f.setStyleSheet(f"background-color: {Theme.BG_APP}; border: 1px solid {Theme.BORDER}; border-radius: 6px;")
        l = QVBoxLayout(f)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(6)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; font-weight: bold; border: none;")
        lbl_t.setMinimumHeight(16)
        
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold; border: none;")
        lbl_v.setMinimumHeight(22)

        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return lbl_v, f

    def update_hardware(self, gpu, vram, cpu, status):
        self.card_gpu_val.setText(gpu)
        self.card_vram_val.setText(vram)
        self.card_cpu_val.setText(cpu)
        self.card_status_val.setText(status)