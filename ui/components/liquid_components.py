from PySide6.QtCore import Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient
from PySide6.QtWidgets import QPushButton, QFrame, QGraphicsDropShadowEffect

from ui.core.design_tokens import ColorToken, RadiusToken


class LiquidButton(QPushButton):
    """Control dạng Liquid Glass Button.

    Sử dụng QVariantAnimation (120ms) cho tương tác mượt mà.
    Tuân thủ P0: Secondary là 8px Rounded Rectangle, Primary action có thể là Pill.
    """
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DESTRUCTIVE = "destructive"

    def __init__(self, text="", variant=SECONDARY, is_pill=False, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.is_pill = is_pill or (variant == self.PRIMARY and "Start" in text)

        if variant == self.PRIMARY:
            # Indigo / Purple Brand Identity (Legacy #6366F1)
            self.bg_normal = QColor(99, 102, 241, 200)
            self.bg_hover = QColor(129, 140, 248, 230)
            self.bg_pressed = QColor(79, 70, 229, 240)
            self.border_base = QColor(99, 102, 241, 180)
            self.border_top = QColor(165, 180, 252, 220)
            self.text_color = QColor(255, 255, 255)
        elif variant == self.DESTRUCTIVE:
            # Danger Red (#EF4444)
            self.bg_normal = QColor(239, 68, 68, 40)
            self.bg_hover = QColor(239, 68, 68, 70)
            self.bg_pressed = QColor(220, 38, 38, 90)
            self.border_base = QColor(239, 68, 68, 80)
            self.border_top = QColor(252, 165, 165, 140)
            self.text_color = QColor(248, 113, 113)
        else:
            # SECONDARY: Surface Elevated / Glass Subtle
            self.bg_normal = QColor(30, 37, 54, 180)
            self.bg_hover = QColor(38, 46, 64, 230)
            self.bg_pressed = QColor(21, 26, 39, 220)
            self.border_base = QColor(255, 255, 255, 16)
            self.border_top = QColor(255, 255, 255, 45)
            self.text_color = QColor(248, 250, 252)

        self._current_bg = QColor(self.bg_normal)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.valueChanged.connect(self._on_animate)

        self.setStyleSheet("background: transparent; border: none;")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)

    def _on_animate(self, value):
        self._current_bg = value
        self.update()

    def _animate_to(self, target_color):
        self._anim.stop()
        self._anim.setStartValue(self._current_bg)
        self._anim.setEndValue(target_color)
        self._anim.start()

    def enterEvent(self, event):
        if self.isEnabled():
            self._animate_to(self.bg_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.isEnabled():
            self._animate_to(self.bg_normal)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.isEnabled():
            self._animate_to(self.bg_pressed)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isEnabled():
            self._animate_to(self.bg_hover if self.underMouse() else self.bg_normal)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = (rect.height() / 2.0) if self.is_pill else float(RadiusToken.CONTROL)

        # 1. Background
        painter.setBrush(self._current_bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        # 2. Specular Edge Lighting
        pen_gradient = QLinearGradient(0, 0, 0, rect.height())
        pen_gradient.setColorAt(0.0, self.border_top)
        pen_gradient.setColorAt(0.4, self.border_base)
        pen_gradient.setColorAt(1.0, self.border_base)

        pen = QPen(pen_gradient, 1)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, radius, radius)

        # 3. Label Text
        painter.setPen(self.text_color)
        if not self.isEnabled():
            painter.setOpacity(0.4)
        painter.drawText(rect, Qt.AlignCenter, self.text())


class ContentSurface(QFrame):
    """VẬT LIỆU ĐẶC (Content Layer)
    Sử dụng cho: Workspace, Settings Content, Timeline.
    Ưu tiên Readability, không có kính. (P0 Rule)
    """
    def __init__(self, parent=None, elevated=False):
        super().__init__(parent)
        self.setProperty("class", "ContentElevated" if elevated else "ContentSurface")


class GlassPanel(QFrame):
    """VẬT LIỆU KÍNH (Functional Glass Layer)
    Sử dụng cho: Sidebar, Toolbar, Popover.
    """
    def __init__(self, parent=None, menu_style=False):
        super().__init__(parent)
        self.setProperty("class", "GlassMenu" if menu_style else "GlassPanel")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.setGraphicsEffect(shadow)
