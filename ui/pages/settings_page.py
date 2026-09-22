from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QStyle,
    QStyleOptionButton,
    QSpinBox,
    QStackedWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme

SETTINGS_CONTENT_MAX_WIDTH = 980


def _text_block(title, description=None):
    block = QWidget()
    layout = QVBoxLayout(block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    title_label = QLabel(title)
    title_label.setWordWrap(True)
    title_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-weight: 600;")
    layout.addWidget(title_label)

    if description:
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        layout.addWidget(description_label)

    return block


class _SettingsRow(QWidget):
    def __init__(self, title=None, description=None, control=None, checkbox=None):
        super().__init__()
        self._control = control
        self._checkbox = checkbox
        self._shared_control_width = 0
        self._indicator_gutter_width = 0
        if control is not None:
            control.setMinimumHeight(control.minimumSizeHint().height())
        self._compact = None

        if checkbox is not None:
            title = checkbox.text()
            checkbox.setText("")
            checkbox.setAccessibleName(title)
            checkbox.setAccessibleDescription(description or "")
            checkbox.setProperty("settingsCheckbox", True)

        main = _text_block(title, description)
        self._title_label = main.findChild(QLabel)
        if checkbox is not None:
            self._title_label.setBuddy(checkbox)

        self._main = main
        self._gutter = QWidget()
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(16)
        self._layout.setVerticalSpacing(8)
        self._layout.setColumnStretch(1, 1)
        self._layout.setColumnStretch(2, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.set_compact(False)

    def set_compact(self, compact):
        if compact == self._compact:
            return
        self._compact = compact
        while self._layout.count():
            self._layout.takeAt(0)

        gutter = self._checkbox or self._gutter
        self._layout.addWidget(gutter, 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
        if compact:
            self._layout.addWidget(
                self._main, 0, 1, 1, 2, Qt.AlignmentFlag.AlignTop
            )
            if self._control is not None:
                self._layout.addWidget(
                    self._control, 1, 1, 1, 2, Qt.AlignmentFlag.AlignRight
                )
            self._layout.setColumnStretch(1, 1)
            self._layout.setColumnStretch(2, 0)
        else:
            self._layout.addWidget(
                self._main, 0, 1, alignment=Qt.AlignmentFlag.AlignTop
            )
            if self._control is not None:
                self._layout.addWidget(
                    self._control,
                    0,
                    2,
                    alignment=Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter,
                )
            self._layout.setColumnStretch(1, 1)
            self._layout.setColumnStretch(2, 0)

        self._apply_control_width()

    def set_indicator_gutter_width(self, width):
        self._indicator_gutter_width = width
        gutter = self._checkbox or self._gutter
        gutter.setFixedWidth(width)
        self._apply_control_width()

    def set_shared_control_width(self, width):
        self._shared_control_width = width
        self._apply_control_width()

    def _apply_control_width(self):
        if self._control is None or not self._shared_control_width:
            return
        width = self._shared_control_width
        if self._compact and self.width() > 0:
            available = self.width() - self._indicator_gutter_width
            available -= self._layout.horizontalSpacing()
            width = min(width, max(0, available))
        self._control.setFixedWidth(width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_control_width()


class _SettingsSection(QWidget):
    def __init__(self, title, description, rows):
        super().__init__()
        self.setObjectName("settings_section")
        self._compact = None

        self.meta = QWidget()
        self.meta.setObjectName("settings_section_meta")
        meta_layout = QVBoxLayout(self.meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"color: {Theme.CYAN}; font-weight: bold;")
        meta_layout.addWidget(title_label)
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        meta_layout.addWidget(description_label)
        meta_layout.addStretch(1)

        self.body = QWidget()
        self.body.setObjectName("settings_section_body")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)
        for row in rows:
            body_layout.addWidget(row)
        body_layout.addStretch(1)

        self._rows = rows
        checkboxes = [row._checkbox for row in rows if row._checkbox is not None]
        if checkboxes:
            checkbox = checkboxes[0]
            option = QStyleOptionButton()
            option.initFrom(checkbox)
            style = checkbox.style()
            gutter_width = style.pixelMetric(
                QStyle.PixelMetric.PM_IndicatorWidth, option, checkbox
            ) + style.pixelMetric(
                QStyle.PixelMetric.PM_CheckBoxLabelSpacing, option, checkbox
            )
        else:
            gutter_width = 0
        for row in rows:
            row.set_indicator_gutter_width(gutter_width)

        inputs = [
            row._control
            for row in rows
            if isinstance(row._control, (QComboBox, QSpinBox))
        ]
        if inputs:
            shared_width = max(control.sizeHint().width() for control in inputs)
            for row in rows:
                if row._control in inputs:
                    row.set_shared_control_width(shared_width)

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(20)
        self._layout.setVerticalSpacing(14)
        self._layout.setColumnStretch(0, 0)
        self._layout.setColumnStretch(1, 1)
        self._shared_meta_width = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.set_compact(False)

    def set_compact(self, compact):
        if compact == self._compact:
            return
        self._compact = compact
        self._layout.removeWidget(self.meta)
        self._layout.removeWidget(self.body)
        if compact:
            self._layout.setColumnMinimumWidth(0, 0)
            self._layout.addWidget(self.meta, 0, 0)
            self._layout.addWidget(self.body, 1, 0)
            self._layout.setColumnStretch(0, 1)
            self._layout.setColumnStretch(1, 0)
        else:
            self._layout.setColumnMinimumWidth(0, self._shared_meta_width)
            self._layout.addWidget(
                self.meta, 0, 0, 1, 1, Qt.AlignmentFlag.AlignTop
            )
            self._layout.addWidget(self.body, 0, 1)
            self._layout.setColumnStretch(0, 0)
            self._layout.setColumnStretch(1, 1)
        for row in self._rows:
            row.set_compact(compact)

    def set_shared_meta_width(self, width):
        self._shared_meta_width = width
        if not self._compact:
            self._layout.setColumnMinimumWidth(0, width)


class SettingsCenterPage(QWidget):
    RESPONSIVE_BREAKPOINT = 680

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px;
                outline: none;
            }}
            QListWidget::item {{
                color: {Theme.TEXT_SECONDARY};
                padding: 10px;
                border-radius: 4px;
                font-weight: 600;
            }}
            QListWidget::item:selected {{
                background-color: {Theme.SURFACE_SOFT};
                color: {Theme.CYAN};
                border-left: 3px solid {Theme.PRIMARY_PURPLE};
            }}
        """)
        for label in (
            "🤖 Whisper AI",
            "🎨 Kiểu phụ đề",
            "🎬 Hardsub FFmpeg",
            "⚙️ Chung & Giao diện",
        ):
            self.nav_list.addItem(QListWidgetItem(label))
        layout.addWidget(self.nav_list)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.stack.setMaximumWidth(SETTINGS_CONTENT_MAX_WIDTH)
        self.sections = []

        self.model_combo = QComboBox()
        self.model_combo.addItem("Large V3 Turbo (Khuyên dùng - Nhanh)", "large-v3-turbo")
        self.model_combo.addItem("Large V3 (Chuẩn gốc)", "large-v3")
        self.compute_combo = QComboBox()
        self.compute_combo.addItem("Float16 (RTX GPU)", "float16")
        self.compute_combo.addItem("Int8_Float16 (Tiết kiệm VRAM)", "int8_float16")
        self.chk_vad = QCheckBox("Kích hoạt bộ lọc Silero VAD")
        self.silence_spin = QSpinBox()
        self.silence_spin.setRange(100, 2000)
        self.silence_spin.setValue(500)
        self.silence_spin.setSingleStep(100)
        self._add_page((
            self._section(
                "Whisper AI",
                "Nhận dạng giọng nói và thiết lập xử lý.",
                (
                    self._row("Kích thước mô hình", "Chọn mô hình dùng để phiên âm.", self.model_combo),
                    self._row("Kiểu tính toán", "Chọn độ chính xác và thiết bị xử lý.", self.compute_combo),
                    self._checkbox_row(self.chk_vad, "Tự động phát hiện các đoạn có giọng nói."),
                    self._row("Im lặng tối thiểu", "Thời lượng im lặng tối thiểu, tính bằng mili giây.", self.silence_spin),
                ),
            ),
        ))

        self.font_combo = QComboBox()
        for font_name in ("Arial", "Noto Sans JP", "Segoe UI", "Tahoma"):
            self.font_combo.addItem(font_name, font_name)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(12, 72)
        self.size_spin.setValue(28)
        self.motion_preset_combo = QComboBox()
        self.motion_preset_combo.addItem("Standard (CrossFade + Fade)", "standard")
        self.motion_preset_combo.addItem("Minimal (Fade 120ms)", "minimal")
        self.motion_preset_combo.addItem("Dynamic (Rise & Highlight)", "dynamic")
        self.motion_preset_combo.addItem("Off (Tắt chuyển động)", "off")
        self.appear_combo = QComboBox()
        self.appear_combo.addItem("Fade (Mờ dần)", "fade")
        self.appear_combo.addItem("Rise (Trượt nhẹ lên)", "rise")
        self.appear_combo.addItem("Instant (Tức thì)", "instant")
        self.disappear_combo = QComboBox()
        self.disappear_combo.addItem("Fade (Mờ dần)", "fade")
        self.disappear_combo.addItem("Drop (Trượt nhẹ xuống)", "drop")
        self.disappear_combo.addItem("Instant (Tức thì)", "instant")
        self.text_effect_combo = QComboBox()
        self.text_effect_combo.addItem("Normal (Bình thường)", "normal")
        self.text_effect_combo.addItem("Reveal (Hiện từng chữ)", "reveal")
        self.text_effect_combo.addItem("Highlight (Karaoke)", "highlight")
        self._add_page((
            self._section(
                "Kiểu phụ đề",
                "Thiết lập mặc định cho hiển thị và chuyển động phụ đề.",
                (
                    self._row("Font chữ mặc định", "Font dùng mặc định cho phụ đề.", self.font_combo),
                    self._row("Cỡ chữ mặc định", "Kích thước chữ mặc định.", self.size_spin),
                    self._row("Kiểu chuyển động", "Chọn bộ hiệu ứng chuyển động.", self.motion_preset_combo),
                    self._row("Hiệu ứng xuất hiện", "Cách phụ đề xuất hiện.", self.appear_combo),
                    self._row("Hiệu ứng biến mất", "Cách phụ đề biến mất.", self.disappear_combo),
                    self._row("Hiệu ứng chữ", "Hiệu ứng áp dụng lên nội dung phụ đề.", self.text_effect_combo),
                ),
            ),
        ))

        self.chk_hardsub_enable = QCheckBox("Bật tạo Hardsub tự động")
        self.chk_hardsub_enable.setChecked(True)
        self._add_page((
            self._section(
                "Hardsub FFmpeg",
                "Thiết lập xuất video và burn-in phụ đề.",
                (self._checkbox_row(self.chk_hardsub_enable),),
            ),
        ))

        self.canonical_autosave_checkbox = QCheckBox("Tự động lưu project")
        self.canonical_autosave_checkbox.setChecked(True)
        self.canonical_autosave_delay_combo = QComboBox()
        for label, delay in (
            ("500 ms", 500),
            ("1 second", 1000),
            ("2 seconds", 2000),
            ("5 seconds", 5000),
        ):
            self.canonical_autosave_delay_combo.addItem(label, delay)
        self.chk_debug_logging_master = QCheckBox("Bật nhật ký gỡ lỗi")
        self.chk_debug_recovery = QCheckBox("Khôi phục")
        self.chk_debug_canonical_save = QCheckBox("Lưu chuẩn (Canonical Save)")
        self.chk_debug_project_switch = QCheckBox("Chuyển project")
        self.chk_debug_project_status = QCheckBox("Trạng thái project")
        self.chk_debug_waveform = QCheckBox("Waveform")
        self.chk_debug_artifact_sync = QCheckBox("Đồng bộ artifact")
        self._add_page((
            self._section(
                "Chung & Giao diện",
                "Thiết lập giao diện và lưu project.",
                (
                    self._row(
                        "Giao diện",
                        "Deep Navy Dark Mode (Standard SaaS Desktop)",
                    ),
                    self._checkbox_row(
                        self.canonical_autosave_checkbox,
                        "Tự động lưu các thay đổi của project.",
                    ),
                    self._row(
                        "Độ trễ lưu",
                        "Thời gian chờ trước khi tự động lưu.",
                        self.canonical_autosave_delay_combo,
                    ),
                ),
            ),
            self._section(
                "Nhật ký gỡ lỗi",
                "Chỉ dùng trong phiên hiện tại và tự tắt khi khởi động lại ứng dụng.",
                (
                    self._checkbox_row(
                        self.chk_debug_logging_master,
                        "Ghi nhật ký chẩn đoán cho các nhóm đã chọn.",
                    ),
                    self._checkbox_row(self.chk_debug_recovery, "Sự kiện vòng đời khôi phục."),
                    self._checkbox_row(self.chk_debug_canonical_save, "Sự kiện lưu project canonical."),
                    self._checkbox_row(self.chk_debug_project_switch, "Sự kiện chuyển đổi project."),
                    self._checkbox_row(self.chk_debug_project_status, "Sự kiện chuyển trạng thái đã lưu/chưa lưu."),
                    self._checkbox_row(self.chk_debug_waveform, "Sự kiện hoàn tất waveform."),
                    self._checkbox_row(self.chk_debug_artifact_sync, "Sự kiện đăng ký và đồng bộ artifact."),
                ),
            ),
        ))

        self.setStyleSheet(f"""
            QCheckBox[settingsCheckbox="true"]:disabled {{
                color: {Theme.TEXT_DISABLED};
            }}
            QCheckBox[settingsCheckbox="true"]::indicator:unchecked {{
                background-color: {Theme.SURFACE_SOFT};
                border: 1px solid {Theme.TEXT_MUTED};
                border-radius: 3px;
            }}
            QCheckBox[settingsCheckbox="true"]::indicator:unchecked:disabled {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.TEXT_DISABLED};
            }}
        """)

        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.scroll_area.setWidget(self.stack)
        layout.addWidget(self.scroll_area, stretch=1)
        self.scroll_area.viewport().installEventFilter(self)
        self._compact = None
        self._apply_responsive_layout(
            self.scroll_area.viewport().width() < self.RESPONSIVE_BREAKPOINT
        )

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

    def _row(self, title, description, control=None):
        return _SettingsRow(title, description, control=control)

    def _checkbox_row(self, checkbox, description=None):
        return _SettingsRow(description=description, checkbox=checkbox)

    def _section(self, title, description, rows):
        section = _SettingsSection(title, description, rows)
        self.sections.append(section)
        return section

    def _add_page(self, sections):
        shared_meta_width = max(section.meta.sizeHint().width() for section in sections)
        for section in sections:
            section.set_shared_meta_width(shared_meta_width)

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        for index, section in enumerate(sections):
            if index:
                page_layout.addSpacing(12)
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Plain)
                separator.setStyleSheet(f"color: {Theme.BORDER};")
                page_layout.addWidget(separator)
                page_layout.addSpacing(12)
            page_layout.addWidget(section)
        page_layout.addStretch(1)
        self.stack.addWidget(page)

    def _apply_responsive_layout(self, compact):
        if compact == self._compact:
            return
        self._compact = compact
        for section in self.sections:
            section.set_compact(compact)

    def eventFilter(self, watched, event):
        if (
            hasattr(self, "scroll_area")
            and watched is self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._apply_responsive_layout(
                event.size().width() < self.RESPONSIVE_BREAKPOINT
            )
        return super().eventFilter(watched, event)
