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
    apply_recommended_config = Signal(str, str)

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

        # 2.5 Hardware & Model Compatibility Card
        self.hw_container = QFrame()
        self.hw_container.setStyleSheet(
            f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; "
            f"border-radius: 8px;"
        )
        hw_layout = QHBoxLayout(self.hw_container)
        hw_layout.setContentsMargins(14, 10, 14, 10)
        hw_layout.setSpacing(16)

        hw_info_col = QVBoxLayout()
        hw_info_col.setSpacing(4)
        lbl_hw_title = QLabel("🛡️ Tương thích cấu hình & Đề xuất AI")
        lbl_hw_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {Theme.TEXT_PRIMARY}; border: none;")
        hw_info_col.addWidget(lbl_hw_title)

        self.lbl_hw_recommendation = QLabel("Đang kiểm tra cấu hình...")
        self.lbl_hw_recommendation.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; border: none;")
        hw_info_col.addWidget(self.lbl_hw_recommendation)
        hw_layout.addLayout(hw_info_col, stretch=1)

        # Buttons
        hw_btn_layout = QHBoxLayout()
        hw_btn_layout.setSpacing(8)

        self.btn_auto_test = QPushButton("⚡ Test tự động")
        self.btn_auto_test.setFixedHeight(30)
        self.btn_auto_test.setToolTip("Tự động kiểm tra cấu hình máy và cập nhật đề xuất")
        self.btn_auto_test.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.CYAN}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 4px 12px; font-weight: 600; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {Theme.SURFACE}; border-color: {Theme.CYAN}; }}"
        )
        self.btn_auto_test.clicked.connect(self._run_auto_test)
        hw_btn_layout.addWidget(self.btn_auto_test)

        self.btn_manual_test = QPushButton("🔍 Test thủ công")
        self.btn_manual_test.setFixedHeight(30)
        self.btn_manual_test.setToolTip("Mở bảng kiểm tra chi tiết các tính năng và model hỗ trợ")
        self.btn_manual_test.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 4px 12px; font-weight: 600; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {Theme.SURFACE}; border-color: {Theme.PRIMARY_PURPLE}; color: {Theme.PRIMARY_PURPLE}; }}"
        )
        self.btn_manual_test.clicked.connect(self._open_manual_test)
        hw_btn_layout.addWidget(self.btn_manual_test)

        hw_layout.addLayout(hw_btn_layout)
        layout.addWidget(self.hw_container)

        # 3. Recent Activity Log Console (Clean, flat)
        log_frame = QFrame()
        log_frame.setObjectName("DashboardLogFrame")
        log_frame.setStyleSheet(
            f"QFrame#DashboardLogFrame {{ background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; }}"
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

        # Initial auto detection
        self._run_auto_test(log_to_activity=False)

    def _run_auto_test(self, log_to_activity: bool = True):
        from core.services.hardware_checker import HardwareChecker
        profile = HardwareChecker.detect()
        self._update_hw_profile_ui(profile)
        if log_to_activity:
            self.append_activity_log(
                f"[HARDWARE] Test tự động: {profile.gpu_name} ({profile.total_vram_gb} GB VRAM) · "
                f"Đánh giá: {profile.stability_rating} · Đề xuất: {profile.recommended_model} ({profile.recommended_compute})"
            )

    def _open_manual_test(self):
        from ui.dialogs.hardware_check_dialog import HardwareCheckDialog
        from core.services.hardware_checker import HardwareChecker
        profile = HardwareChecker.detect()
        dialog = HardwareCheckDialog(self, profile=profile)
        dialog.apply_recommended.connect(self.apply_recommended_config)
        dialog.exec()

    def _update_hw_profile_ui(self, profile):
        status_color = (
            Theme.SUCCESS
            if "Mượt" in profile.stability_rating
            else (Theme.CYAN if "Ổn" in profile.stability_rating else Theme.WARNING)
        )
        gpu_label = profile.gpu_name if profile.has_cuda else "CPU Mode"
        self.lbl_hw_recommendation.setText(
            f"✅ <b>{gpu_label}</b> ({profile.total_vram_gb} GB) · "
            f"Đánh giá: <span style='color: {status_color}; font-weight: 700;'>{profile.stability_rating}</span> · "
            f"Gợi ý: <b style='color: {Theme.CYAN};'>{profile.recommended_model} ({profile.recommended_compute})</b>"
        )

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
