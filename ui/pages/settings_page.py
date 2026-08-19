from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme


class SettingsCenterPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Left Column: Category Selector
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

        self.nav_list.addItem(QListWidgetItem("🤖 Whisper AI"))
        self.nav_list.addItem(QListWidgetItem("🎨 Subtitle Style"))
        self.nav_list.addItem(QListWidgetItem("🎬 Hardsub FFmpeg"))
        self.nav_list.addItem(QListWidgetItem("⚙️ General & UI"))
        layout.addWidget(self.nav_list)

        # Right Column: Stack of Setting Categories
        self.stack = QStackedWidget()

        # Category 0: AI Engine
        page_ai = QWidget()
        l_ai = QVBoxLayout(page_ai)
        card_ai = QFrame()
        card_ai.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 12px;")
        grid_ai = QGridLayout(card_ai)
        grid_ai.setSpacing(10)

        grid_ai.addWidget(QLabel("Whisper Model Size:"), 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItem("Large V3 Turbo (Khuyên dùng - Nhanh)", "large-v3-turbo")
        self.model_combo.addItem("Large V3 (Chuẩn gốc)", "large-v3")
        grid_ai.addWidget(self.model_combo, 0, 1)

        grid_ai.addWidget(QLabel("Compute Type:"), 1, 0)
        self.compute_combo = QComboBox()
        self.compute_combo.addItem("Float16 (RTX GPU)", "float16")
        self.compute_combo.addItem("Int8_Float16 (Tiết kiệm VRAM)", "int8_float16")
        grid_ai.addWidget(self.compute_combo, 1, 1)

        self.chk_vad = QCheckBox("Kích hoạt Silero VAD Filter")
        grid_ai.addWidget(self.chk_vad, 2, 0, 1, 2)

        l_ai.addWidget(card_ai)
        l_ai.addStretch()
        self.stack.addWidget(page_ai)

        # Category 1: Subtitle Style
        page_sub = QWidget()
        l_sub = QVBoxLayout(page_sub)
        card_sub = QFrame()
        card_sub.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 12px;")
        grid_sub = QGridLayout(card_sub)
        grid_sub.setSpacing(10)

        grid_sub.addWidget(QLabel("Font chữ mặc định:"), 0, 0)
        self.font_combo = QComboBox()
        for f in ["Arial", "Noto Sans JP", "Segoe UI", "Tahoma"]:
            self.font_combo.addItem(f, f)
        grid_sub.addWidget(self.font_combo, 0, 1)

        grid_sub.addWidget(QLabel("Cỡ chữ mặc định:"), 1, 0)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(12, 72)
        self.size_spin.setValue(28)
        grid_sub.addWidget(self.size_spin, 1, 1)

        l_sub.addWidget(card_sub)
        l_sub.addStretch()
        self.stack.addWidget(page_sub)

        # Category 2: Hardsub FFmpeg
        page_hs = QWidget()
        l_hs = QVBoxLayout(page_hs)
        card_hs = QFrame()
        card_hs.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 12px;")
        grid_hs = QGridLayout(card_hs)
        grid_hs.setSpacing(10)

        self.chk_hardsub_enable = QCheckBox("Bật tạo Hardsub tự động")
        self.chk_hardsub_enable.setChecked(True)
        grid_hs.addWidget(self.chk_hardsub_enable, 0, 0, 1, 2)

        l_hs.addWidget(card_hs)
        l_hs.addStretch()
        self.stack.addWidget(page_hs)

        # Category 3: General
        page_gen = QWidget()
        l_gen = QVBoxLayout(page_gen)
        card_gen = QFrame()
        card_gen.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 12px;")
        l_g = QVBoxLayout(card_gen)
        l_g.addWidget(QLabel(f"AI Subtitle Studio — Sprint 6 Architecture", styleSheet=f"color: {Theme.CYAN}; font-weight: bold;"))
        l_g.addWidget(QLabel(f"Theme: Deep Navy Dark Mode (Standard SaaS Desktop)", styleSheet=f"color: {Theme.TEXT_MUTED};"))
        l_gen.addWidget(card_gen)
        l_gen.addStretch()
        self.stack.addWidget(page_gen)

        layout.addWidget(self.stack, stretch=1)

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)  