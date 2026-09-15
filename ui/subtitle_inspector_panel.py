from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QCheckBox,
    QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QColorDialog,
    QFontComboBox, QGroupBox,
)
from PySide6.QtCore import QSignalBlocker, Signal, Qt, Slot
from PySide6.QtGui import QColor
from ui.theme import Theme


class SubtitleInspectorPanel(QWidget):
    """Pure UI inspector for subtitle overlay styling."""

    style_changed = Signal(dict)
    preview_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_color = QColor(255, 255, 255)
        self.outline_color = QColor(0, 0, 0)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        self.chk_preview = QCheckBox("Hiển thị Preview Phụ đề")
        self.chk_preview.setChecked(True)
        layout.addWidget(self.chk_preview)

        style_group = QGroupBox("🎨 Subtitle Style")
        form_layout = QFormLayout(style_group)
        form_layout.setSpacing(10)

        self.cmb_font = QFontComboBox()
        self.cmb_font.setEditable(False)
        form_layout.addRow("Font chữ:", self.cmb_font)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(10, 150)
        self.spin_size.setValue(40)
        form_layout.addRow("Cỡ chữ:", self.spin_size)

        self.btn_text_color = QPushButton()
        self.btn_text_color.setCursor(Qt.PointingHandCursor)
        self._update_color_button(self.btn_text_color, self.text_color)
        form_layout.addRow("Màu chữ:", self.btn_text_color)

        self.spin_outline = QSpinBox()
        self.spin_outline.setRange(0, 20)
        self.spin_outline.setValue(2)
        form_layout.addRow("Độ dày viền:", self.spin_outline)

        self.btn_outline_color = QPushButton()
        self.btn_outline_color.setCursor(Qt.PointingHandCursor)
        self._update_color_button(self.btn_outline_color, self.outline_color)
        form_layout.addRow("Màu viền:", self.btn_outline_color)

        self.cmb_position = QComboBox()
        self.cmb_position.addItems(["Top", "Center", "Bottom", "Custom"])
        self.cmb_position.setCurrentText("Bottom")
        form_layout.addRow("Vị trí:", self.cmb_position)

        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(0.0, 100.0)
        self.spin_x.setDecimals(1)
        self.spin_x.setSuffix(" %")
        self.spin_x.setValue(50.0)
        form_layout.addRow("X:", self.spin_x)

        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(0.0, 100.0)
        self.spin_y.setDecimals(1)
        self.spin_y.setSuffix(" %")
        self.spin_y.setValue(85.0)
        form_layout.addRow("Y:", self.spin_y)

        self.chk_position_edit = QCheckBox("Position Edit Mode")
        form_layout.addRow(self.chk_position_edit)

        layout.addWidget(style_group)
        layout.addStretch()
        self.setStyleSheet(
            f"""
            QDoubleSpinBox {{
                background-color: {Theme.BG_APP};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px 18px 6px 10px;
            }}
            QDoubleSpinBox:hover {{
                border-color: {Theme.CYAN};
            }}
            QDoubleSpinBox:focus {{
                border-color: {Theme.PRIMARY_PURPLE};
            }}
            QDoubleSpinBox:disabled {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_DISABLED};
                border-color: {Theme.BORDER};
            }}
            QDoubleSpinBox::up-button,
            QDoubleSpinBox::down-button {{
                background-color: {Theme.SURFACE_SOFT};
                border: none;
                width: 16px;
            }}
            QDoubleSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover {{
                background-color: {Theme.BORDER};
            }}
            """
        )

    def _update_color_button(self, btn: QPushButton, color: QColor):
        btn.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #555; "
            "border-radius: 4px; min-height: 24px;"
        )

    def _connect_signals(self):
        self.chk_preview.toggled.connect(self.preview_toggled.emit)
        self.cmb_font.currentFontChanged.connect(self._on_style_changed)
        self.spin_size.valueChanged.connect(self._on_style_changed)
        self.spin_outline.valueChanged.connect(self._on_style_changed)
        self.cmb_position.currentIndexChanged.connect(self._on_style_changed)
        self.spin_x.editingFinished.connect(self._on_style_changed)
        self.spin_y.editingFinished.connect(self._on_style_changed)
        self.chk_position_edit.toggled.connect(self._on_style_changed)
        self.btn_text_color.clicked.connect(self._choose_text_color)
        self.btn_outline_color.clicked.connect(self._choose_outline_color)

    @Slot()
    def _choose_text_color(self):
        color = self._choose_color(self.text_color, "Chọn màu chữ")
        if color.isValid():
            self.text_color = color
            self._update_color_button(self.btn_text_color, color)
            self._on_style_changed()

    @Slot()
    def _choose_outline_color(self):
        color = self._choose_color(self.outline_color, "Chọn màu viền")
        if color.isValid():
            self.outline_color = color
            self._update_color_button(self.btn_outline_color, color)
            self._on_style_changed()

    def _choose_color(self, initial: QColor, title: str) -> QColor:
        dialog = QColorDialog(initial, self)
        dialog.setWindowTitle(title)
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        dialog.setStyleSheet(
            f"""
            QColorDialog, QDialog {{ background: {Theme.BG_APP}; color: {Theme.TEXT_PRIMARY}; }}
            QColorDialog QLabel {{ color: {Theme.TEXT_SECONDARY}; }}
            QColorDialog QLineEdit, QColorDialog QSpinBox {{
                background: {Theme.SURFACE}; color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER}; border-radius: 5px; padding: 5px;
            }}
            QColorDialog QPushButton {{
                background: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER}; border-radius: 5px; padding: 6px 14px;
            }}
            QColorDialog QPushButton:hover {{ border-color: {Theme.CYAN}; color: {Theme.CYAN}; }}
            """
        )
        return dialog.currentColor() if dialog.exec() else QColor()

    @Slot()
    def _on_style_changed(self, *args):
        self.style_changed.emit(self.get_current_style())

    def get_current_style(self) -> dict:
        return {
            "font_name": self.cmb_font.currentFont().family(),
            "font_size": self.spin_size.value(),
            "font_color": self.text_color.name(),
            "outline_color": self.outline_color.name(),
            "outline_width": self.spin_outline.value(),
            "position": self.cmb_position.currentText().lower(),
            "x": self.spin_x.value() / 100.0,
            "y": self.spin_y.value() / 100.0,
            "position_edit_mode": self.chk_position_edit.isChecked(),
        }

    def set_placement_state(self, mode, x, y, emit=False):
        mode = str(mode).lower()
        mode_text = {"top": "Top", "center": "Center", "bottom": "Bottom", "custom": "Custom"}.get(mode, "Bottom")
        blockers = [
            QSignalBlocker(self.cmb_position),
            QSignalBlocker(self.spin_x),
            QSignalBlocker(self.spin_y),
        ]
        self.cmb_position.setCurrentText(mode_text)
        self.spin_x.setValue(max(0.0, min(100.0, float(x) * 100.0)))
        self.spin_y.setValue(max(0.0, min(100.0, float(y) * 100.0)))
        del blockers
        if emit:
            self._on_style_changed()

    def emit_current_style(self):
        """Emit the current style snapshot after the panel is connected."""
        self._on_style_changed()
