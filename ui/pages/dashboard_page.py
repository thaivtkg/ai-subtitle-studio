from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme
from ui.activity_log import ActivityLogModel, ActivityLogView


class DashboardPage(QWidget):
    navigate_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.activity_log_model = ActivityLogModel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        # 1. Cardless Typography Metrics (Zen Header)
        metrics_container = QWidget()
        m_layout = QHBoxLayout(metrics_container)
        m_layout.setContentsMargins(0, 0, 0, 8)
        m_layout.setSpacing(32)

        self.card_gpu_val, col_gpu = self._create_metric_col("GPU ENGINE", "Detecting...", Theme.CYAN)
        self.card_vram_val, col_vram = self._create_metric_col("VRAM ALLOCATION", "-- / -- GB", Theme.PRIMARY_PURPLE)
        self.card_cpu_val, col_cpu = self._create_metric_col("CPU LOAD", "0%", Theme.TEXT_PRIMARY)
        self.card_status_val, col_status = self._create_metric_col("SYSTEM STATUS", "Idle", Theme.SUCCESS)

        m_layout.addWidget(col_gpu)
        m_layout.addWidget(col_vram)
        m_layout.addWidget(col_cpu)
        m_layout.addWidget(col_status)
        m_layout.addStretch()
        layout.addWidget(metrics_container)

        # Subtle divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"border: none; background-color: {Theme.BORDER}; max-height: 1px;")
        layout.addWidget(divider)

        # 2. Pipeline Overview & Quick Access (Integrated Row)
        mid_container = QWidget()
        mid_layout = QHBoxLayout(mid_container)
        mid_layout.setContentsMargins(0, 4, 0, 4)
        mid_layout.setSpacing(24)

        # Pipeline progress left column
        pipeline_col = QVBoxLayout()
        pipeline_col.setSpacing(6)

        lbl_s_title = QLabel("⚡ Pipeline Overview")
        lbl_s_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {Theme.TEXT_PRIMARY}; border: none;")
        pipeline_col.addWidget(lbl_s_title)

        self.lbl_queue_overview = QLabel("Queue: 0 items loaded · Output: Default")
        self.lbl_queue_overview.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; border: none;")
        pipeline_col.addWidget(self.lbl_queue_overview)

        self.quick_progress = QProgressBar()
        self.quick_progress.setValue(0)
        self.quick_progress.setFixedHeight(4)
        self.quick_progress.setTextVisible(False)
        self.quick_progress.setStyleSheet(
            f"QProgressBar {{ background: {Theme.SURFACE_SOFT}; border: none; border-radius: 2px; }} "
            f"QProgressBar::chunk {{ background: {Theme.PRIMARY_GRADIENT}; border-radius: 2px; }}"
        )
        pipeline_col.addWidget(self.quick_progress)
        mid_layout.addLayout(pipeline_col, stretch=3)

        # Quick Actions right column (Ghost Buttons)
        actions_col = QVBoxLayout()
        actions_col.setSpacing(6)

        lbl_a_title = QLabel("🚀 Quick Navigation")
        lbl_a_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {Theme.TEXT_PRIMARY}; border: none;")
        actions_col.addWidget(lbl_a_title)

        actions_btn_row = QHBoxLayout()
        actions_btn_row.setSpacing(8)

        btn_go_workspace = QPushButton("🎬 Studio Workspace")
        btn_go_workspace.setFixedHeight(30)
        btn_go_workspace.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 4px 12px; font-weight: 600; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; border-color: {Theme.CYAN}; color: {Theme.CYAN}; }}"
        )
        btn_go_workspace.clicked.connect(lambda: self.navigate_requested.emit(1))
        actions_btn_row.addWidget(btn_go_workspace)

        btn_go_queue = QPushButton("📋 Task Queue")
        btn_go_queue.setFixedHeight(30)
        btn_go_queue.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 4px 12px; font-weight: 600; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; border-color: {Theme.CYAN}; color: {Theme.CYAN}; }}"
        )
        btn_go_queue.clicked.connect(lambda: self.navigate_requested.emit(2))
        actions_btn_row.addWidget(btn_go_queue)

        actions_col.addLayout(actions_btn_row)
        mid_layout.addLayout(actions_col, stretch=2)
        layout.addWidget(mid_container)

        # 3. Recent Activity Log Console (Clean, flat)
        log_frame = QFrame()
        log_frame.setStyleSheet(
            f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px;"
        )
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 10, 12, 10)
        log_layout.setSpacing(6)

        self.activity_log = ActivityLogView(self.activity_log_model)
        self.activity_level_filter = self.activity_log.level_filter
        self.activity_source_filter = self.activity_log.source_filter
        self.activity_technical_reports = self.activity_log.technical_reports_control
        self.activity_auto_scroll = self.activity_log.auto_scroll_control
        self.activity_clear_button = self.activity_log.clear_button
        log_layout.addWidget(self.activity_log)

        layout.addWidget(log_frame, stretch=1)

    def append_activity_log(self, raw):
        self.activity_log_model.append(raw)

    def clear_activity_log(self):
        self.activity_log_model.clear()

    def _create_metric_col(self, title, val, color):
        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(3)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(
            f"color: {Theme.TEXT_MUTED}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 0.5px; border: none;"
        )

        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(
            f"color: {color}; font-size: 19px; font-weight: 800; border: none;"
        )

        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return lbl_v, container

    def update_hardware(self, gpu, vram, cpu, status):
        self.card_gpu_val.setText(gpu)
        self.card_vram_val.setText(vram)
        self.card_cpu_val.setText(cpu)
        self.card_status_val.setText(status)
