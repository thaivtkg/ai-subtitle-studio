import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QStyle,
    QStyleOptionButton,
    QScrollBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.pages.settings_page import SettingsCenterPage
from ui.theme import Theme


class SettingsTextClippingContracts(unittest.TestCase):
    HELPER_TEXT = "Chỉ dùng trong phiên hiện tại và tự tắt khi khởi động lại ứng dụng."
    VIEWPORTS = ((1135, 620), (620, 620))

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.app.setStyleSheet(Theme.get_global_stylesheet())

    def _settings_at_size(self, size, category=3):
        host = QWidget()
        host.setFixedSize(*size)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)

        page = SettingsCenterPage()
        layout.addWidget(page)
        host.show()
        page.nav_list.setCurrentRow(category)
        self.app.processEvents()
        return host, page, page.stack.widget(category)

    def _all_visible_settings_pages(self, page):
        for category in range(page.stack.count()):
            page.nav_list.setCurrentRow(category)
            self.app.processEvents()
            yield page.stack.widget(category)

    def _assert_page_has_sections(self, settings_page):
        sections = settings_page.findChildren(QWidget, "settings_section")
        self.assertTrue(
            sections,
            "Settings category has no semantic section",
        )
        return sections

    @staticmethod
    def _text_widgets(settings_section):
        widgets = []
        for widget_type in (QLabel, QCheckBox, QComboBox, QSpinBox, QLineEdit):
            widgets.extend(settings_section.findChildren(widget_type))
        return widgets

    @staticmethod
    def _widget_text(widget):
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return widget.text()

    def _assert_text_widgets_keep_minimum_height(self, section, viewport):
        for widget in self._text_widgets(section):
            text = self._widget_text(widget)
            with self.subTest(viewport=viewport, text=text):
                self.assertGreaterEqual(
                    widget.height(),
                    widget.minimumSizeHint().height(),
                    f"{type(widget).__name__} {text!r}: "
                    f"height={widget.height()}, "
                    f"minimumSizeHint={widget.minimumSizeHint().height()}, "
                    f"contentsRect={widget.contentsRect().getRect()}, "
                    f"geometry={widget.geometry().getRect()}",
                )

    def test_wide_viewport_preserves_text_control_minimum_heights(self):
        size = self.VIEWPORTS[0]
        host, page, _section = self._settings_at_size(size)
        self.addCleanup(host.close)

        for settings_page in self._all_visible_settings_pages(page):
            sections = self._assert_page_has_sections(settings_page)
            for section in sections:
                self._assert_text_widgets_keep_minimum_height(section, size)

    def test_narrow_viewport_preserves_text_control_minimum_heights(self):
        size = self.VIEWPORTS[1]
        host, page, _section = self._settings_at_size(size)
        self.addCleanup(host.close)

        for settings_page in self._all_visible_settings_pages(page):
            sections = self._assert_page_has_sections(settings_page)
            self.assertEqual(page.scroll_area.horizontalScrollBar().maximum(), 0)
            for section in sections:
                self._assert_text_widgets_keep_minimum_height(section, size)

    def test_widget_content_rect_can_display_its_font_metrics(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[0])
        self.addCleanup(host.close)

        for settings_page in self._all_visible_settings_pages(page):
            for section in self._assert_page_has_sections(settings_page):
                for widget in self._text_widgets(section):
                    metrics = QFontMetrics(widget.font())
                    text = self._widget_text(widget)
                    with self.subTest(text=text):
                        if isinstance(widget, QCheckBox) and not text:
                            option = QStyleOptionButton()
                            option.initFrom(widget)
                            option.rect = widget.rect()
                            indicator = widget.style().subElementRect(
                                QStyle.SubElement.SE_CheckBoxIndicator,
                                option,
                                widget,
                            )
                            self.assertTrue(
                                widget.contentsRect().contains(indicator),
                                f"Checkbox indicator {indicator.getRect()} is outside "
                                f"content rect {widget.contentsRect().getRect()}",
                            )
                            continue
                        self.assertGreaterEqual(
                            widget.contentsRect().height(),
                            metrics.height(),
                            f"{type(widget).__name__} {text!r}: "
                            f"content height={widget.contentsRect().height()}, "
                            f"font height={metrics.height()}, "
                            f"widget height={widget.height()}",
                        )

    def test_narrow_viewport_keeps_the_full_helper_text_readable(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[1])
        self.addCleanup(host.close)
        helper = next(
            label
            for settings_page in self._all_visible_settings_pages(page)
            for section in self._assert_page_has_sections(settings_page)
            for label in section.findChildren(QLabel)
            if label.text() == self.HELPER_TEXT
        )
        natural_width = QFontMetrics(helper.font()).horizontalAdvance(
            self.HELPER_TEXT
        )

        self.assertTrue(
            helper.wordWrap() or natural_width <= helper.contentsRect().width(),
            f"Helper text needs {natural_width}px but has "
            f"{helper.contentsRect().width()}px and wordWrap="
            f"{helper.wordWrap()}",
        )

    def test_overflow_is_scrollable_instead_of_compressing_the_settings_card(self):
        host, page, _section = self._settings_at_size((620, 300))
        self.addCleanup(host.close)
        self.assertGreater(page.scroll_area.verticalScrollBar().maximum(), 0)
        self.assertEqual(page.scroll_area.horizontalScrollBar().maximum(), 0)

    def test_text_children_stay_inside_their_semantic_section(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[0])
        self.addCleanup(host.close)

        for settings_page in self._all_visible_settings_pages(page):
            for section in self._assert_page_has_sections(settings_page):
                for widget in self._text_widgets(section):
                    text = self._widget_text(widget)
                    with self.subTest(text=text):
                        content = section.contentsRect()
                        origin = widget.mapTo(section, QPoint(0, 0))
                        geometry = QRect(origin, widget.size())
                        self.assertTrue(
                            content.contains(geometry),
                            f"{type(widget).__name__} {text!r} geometry "
                            f"{geometry.getRect()} escapes section content "
                            f"{content.getRect()}",
                        )

    def test_section_metadata_stacks_above_body_at_narrow_width(self):
        for size, compact in ((self.VIEWPORTS[0], False), (self.VIEWPORTS[1], True)):
            host, page, settings_page = self._settings_at_size(size, category=0)
            self.addCleanup(host.close)
            section = self._assert_page_has_sections(settings_page)[0]
            meta = section.findChild(QWidget, "settings_section_meta")
            body = section.findChild(QWidget, "settings_section_body")
            self.assertIsNotNone(meta)
            self.assertIsNotNone(body)
            self.app.processEvents()
            if compact:
                self.assertGreaterEqual(body.y(), meta.y() + meta.height())
            else:
                self.assertGreater(body.x(), meta.x())

    def test_wide_settings_content_is_bounded_and_left_aligned(self):
        host, page, _section = self._settings_at_size((1600, 900), category=0)
        self.addCleanup(host.close)

        self.assertLessEqual(page.stack.width(), 980)
        self.assertEqual(page.stack.x(), 0)

    def test_trailing_inputs_share_a_column_within_each_section(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[0], category=0)
        self.addCleanup(host.close)

        for category, controls in (
            (0, (page.model_combo, page.compute_combo, page.silence_spin)),
            (
                1,
                (
                    page.font_combo,
                    page.size_spin,
                    page.motion_preset_combo,
                    page.appear_combo,
                    page.disappear_combo,
                    page.text_effect_combo,
                ),
            ),
        ):
            page.nav_list.setCurrentRow(category)
            self.app.processEvents()
            section = self._assert_page_has_sections(page.stack.widget(category))[0]
            positions = [control.mapTo(section, QPoint(0, 0)).x() for control in controls]
            widths = [control.width() for control in controls]
            self.assertEqual(positions, [positions[0]] * len(positions))
            self.assertEqual(widths, [widths[0]] * len(widths))

    def test_settings_section_labels_are_vietnamese(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[0])
        self.addCleanup(host.close)

        self.assertEqual(
            [page.nav_list.item(index).text() for index in range(page.nav_list.count())],
            ["🤖 Whisper AI", "🎨 Kiểu phụ đề", "🎬 Hardsub FFmpeg", "⚙️ Chung & Giao diện"],
        )
        for category, expected in (
            (0, "Nhận dạng giọng nói và thiết lập xử lý."),
            (1, "Thiết lập mặc định cho hiển thị và chuyển động phụ đề."),
            (2, "Thiết lập xuất video và burn-in phụ đề."),
            (3, "Thiết lập giao diện và lưu project."),
        ):
            page.nav_list.setCurrentRow(category)
            self.app.processEvents()
            section = self._assert_page_has_sections(page.stack.widget(category))[0]
            labels = section.meta.findChildren(QLabel)
            self.assertEqual(labels[1].text(), expected)

        expected_controls = {
            0: {"Kích hoạt bộ lọc Silero VAD"},
            1: set(),
            2: {"Bật tạo Hardsub tự động"},
            3: {
                "Tự động lưu project",
                "Bật nhật ký gỡ lỗi",
                "Khôi phục",
                "Lưu chuẩn (Canonical Save)",
                "Chuyển project",
                "Trạng thái project",
                "Waveform",
                "Đồng bộ artifact",
            },
        }
        expected_rows = {
            0: {"Kích thước mô hình", "Kiểu tính toán", "Im lặng tối thiểu"},
            1: {
                "Font chữ mặc định",
                "Cỡ chữ mặc định",
                "Kiểu chuyển động",
                "Hiệu ứng xuất hiện",
                "Hiệu ứng biến mất",
                "Hiệu ứng chữ",
            },
            2: set(),
            3: {"Giao diện", "Độ trễ lưu"},
        }
        for category in range(page.stack.count()):
            page.nav_list.setCurrentRow(category)
            self.app.processEvents()
            sections = self._assert_page_has_sections(page.stack.widget(category))
            visible_copy = {
                widget.text()
                for widget_type in (QLabel, QCheckBox)
                for section in sections
                for widget in section.findChildren(widget_type)
            } | {
                checkbox.accessibleName()
                for section in sections
                for checkbox in section.findChildren(QCheckBox)
            }
            self.assertTrue(expected_controls[category] <= visible_copy)
            self.assertTrue(expected_rows[category] <= visible_copy)

    def test_checkbox_titles_and_helpers_share_the_normal_text_baseline(self):
        def label_x(section, text):
            labels = [label for label in section.findChildren(QLabel) if label.text() == text]
            self.assertEqual(len(labels), 1, f"Expected one text label for {text!r}")
            return labels[0].mapTo(section, QPoint(0, 0)).x()

        for size in self.VIEWPORTS:
            host, page, _section = self._settings_at_size(size, category=0)
            self.addCleanup(host.close)

            whisper = self._assert_page_has_sections(page.stack.widget(0))[0]
            whisper_title_x = label_x(whisper, "Kích thước mô hình")
            self.assertEqual(label_x(whisper, "Kích hoạt bộ lọc Silero VAD"), whisper_title_x)
            whisper_helper_x = label_x(whisper, "Chọn mô hình dùng để phiên âm.")
            self.assertEqual(
                label_x(whisper, "Tự động phát hiện các đoạn có giọng nói."),
                whisper_helper_x,
            )

            page.nav_list.setCurrentRow(3)
            self.app.processEvents()
            sections = self._assert_page_has_sections(page.stack.widget(3))
            general, debug = sections
            general_x = label_x(general, "Giao diện")
            for title in ("Tự động lưu project", "Độ trễ lưu"):
                self.assertEqual(label_x(general, title), general_x)
            debug_x = label_x(debug, "Bật nhật ký gỡ lỗi")
            for title in (
                "Khôi phục",
                "Lưu chuẩn (Canonical Save)",
                "Chuyển project",
                "Trạng thái project",
                "Waveform",
                "Đồng bộ artifact",
            ):
                self.assertEqual(label_x(debug, title), debug_x)

    def test_settings_checkboxes_keep_accessible_titles(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[0])
        self.addCleanup(host.close)

        checkboxes = [
            checkbox
            for section in page.sections
            for checkbox in section.findChildren(QCheckBox)
        ]
        self.assertEqual(len(checkboxes), 10)
        for checkbox in checkboxes:
            with self.subTest(title=checkbox.accessibleName()):
                self.assertEqual(checkbox.text(), "")
                self.assertTrue(checkbox.accessibleName())
                self.assertTrue(checkbox.property("settingsCheckbox"))

    def test_general_sections_share_meta_and_body_origins(self):
        for size, compact in ((self.VIEWPORTS[0], False), (self.VIEWPORTS[1], True)):
            host, page, _section = self._settings_at_size(size, category=3)
            self.addCleanup(host.close)
            page_widget = page.stack.widget(3)
            general, debug = self._assert_page_has_sections(page_widget)

            general_body_x = general.body.mapTo(page_widget, QPoint(0, 0)).x()
            debug_body_x = debug.body.mapTo(page_widget, QPoint(0, 0)).x()
            self.assertEqual(general_body_x, debug_body_x)

            def page_text_x(section, text):
                label = next(
                    label for label in section.findChildren(QLabel)
                    if label.text() == text
                )
                return label.mapTo(page_widget, QPoint(0, 0)).x()

            text_x = [
                page_text_x(general, "Giao diện"),
                page_text_x(general, "Tự động lưu project"),
                page_text_x(general, "Độ trễ lưu"),
                page_text_x(debug, "Bật nhật ký gỡ lỗi"),
                page_text_x(debug, "Khôi phục"),
            ]
            self.assertLessEqual(max(text_x) - min(text_x), 1)
            if compact:
                self.assertEqual(general.body.x(), 0)
                self.assertEqual(debug.body.x(), 0)

    def test_hardsub_checkbox_and_title_share_natural_row_height(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[0], category=2)
        self.addCleanup(host.close)
        section = self._assert_page_has_sections(page.stack.widget(2))[0]
        row = section._rows[0]
        checkbox = row._checkbox
        option = QStyleOptionButton()
        option.initFrom(checkbox)
        option.rect = checkbox.rect()
        indicator = checkbox.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox
        )
        indicator_center_y = checkbox.mapTo(section, indicator.center()).y()
        title_center_y = row._title_label.mapTo(section, row._title_label.rect().center()).y()

        self.assertLessEqual(abs(indicator_center_y - title_center_y), 3)
        minimum_content_height = max(
            checkbox.minimumSizeHint().height(),
            row._title_label.minimumSizeHint().height(),
        )
        self.assertGreaterEqual(row.height(), minimum_content_height)
        self.assertLessEqual(row.height(), row.sizeHint().height() + 3)

    def test_debug_section_has_space_on_both_sides_of_separator(self):
        host, page, _section = self._settings_at_size(self.VIEWPORTS[0], category=3)
        self.addCleanup(host.close)
        page_widget = page.stack.widget(3)
        general, debug = self._assert_page_has_sections(page_widget)
        separator = next(
            frame for frame in page_widget.findChildren(QFrame)
            if frame.frameShape() == QFrame.Shape.HLine
        )

        self.assertGreaterEqual(separator.y() - general.geometry().bottom(), 6)
        self.assertGreaterEqual(debug.y() - separator.geometry().bottom(), 6)


if __name__ == "__main__":
    unittest.main()
