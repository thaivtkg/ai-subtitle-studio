import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)

from ui.pages.settings_page import SettingsCenterPage
from ui.theme import Theme


class SettingsTextClippingContracts(unittest.TestCase):
    HELPER_TEXT = "Debug logs are session-only and reset when the app restarts."
    VIEWPORTS = ((1135, 620), (620, 620))

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.app.setStyleSheet(Theme.get_global_stylesheet())

    def _settings_at_size(self, size):
        host = QWidget()
        host.setFixedSize(*size)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)

        page = SettingsCenterPage()
        layout.addWidget(page)
        host.show()
        page.nav_list.setCurrentRow(3)
        self.app.processEvents()
        return host, page, page.stack.widget(3)

    @staticmethod
    def _text_widgets(settings_section):
        widgets = []
        for widget_type in (QLabel, QCheckBox, QComboBox):
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
        host, _page, section = self._settings_at_size(size)
        self.addCleanup(host.close)

        self._assert_text_widgets_keep_minimum_height(section, size)

    def test_narrow_viewport_preserves_text_control_minimum_heights(self):
        size = self.VIEWPORTS[1]
        host, _page, section = self._settings_at_size(size)
        self.addCleanup(host.close)

        self._assert_text_widgets_keep_minimum_height(section, size)

    def test_widget_content_rect_can_display_its_font_metrics(self):
        host, _page, section = self._settings_at_size(self.VIEWPORTS[0])
        self.addCleanup(host.close)

        for widget in self._text_widgets(section):
            metrics = QFontMetrics(widget.font())
            text = self._widget_text(widget)
            with self.subTest(text=text):
                self.assertGreaterEqual(
                    widget.contentsRect().height(),
                    metrics.height(),
                    f"{type(widget).__name__} {self._widget_text(widget)!r}: "
                    f"content height={widget.contentsRect().height()}, "
                    f"font height={metrics.height()}, "
                    f"widget height={widget.height()}",
                )

    def test_narrow_viewport_keeps_the_full_helper_text_readable(self):
        host, _page, section = self._settings_at_size(self.VIEWPORTS[1])
        self.addCleanup(host.close)
        helper = next(
            label
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
        host, page, section = self._settings_at_size(self.VIEWPORTS[1])
        self.addCleanup(host.close)
        card = section.findChild(QFrame)
        active_vertical_scroll = any(
            scrollbar.isVisible()
            and scrollbar.orientation().value == 2
            and scrollbar.maximum() > scrollbar.minimum()
            for scrollbar in page.findChildren(QScrollBar)
        )

        self.assertTrue(
            active_vertical_scroll
            or card.height() >= card.minimumSizeHint().height(),
            f"Settings need {card.minimumSizeHint().height()}px vertically, "
            f"card received {card.height()}px, and no active vertical "
            "scroll range is available",
        )

    def test_text_children_stay_inside_their_card_content_rect(self):
        host, _page, section = self._settings_at_size(self.VIEWPORTS[0])
        self.addCleanup(host.close)
        card = section.findChild(QFrame)
        content = card.contentsRect()

        for widget in self._text_widgets(section):
            with self.subTest(text=self._widget_text(widget)):
                geometry = widget.geometry()
                self.assertGreaterEqual(geometry.left(), content.left())
                self.assertGreaterEqual(geometry.top(), content.top())
                self.assertLessEqual(geometry.right(), content.right())
                self.assertLessEqual(geometry.bottom(), content.bottom())


if __name__ == "__main__":
    unittest.main()
