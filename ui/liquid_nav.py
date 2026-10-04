from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QMouseEvent, QPen, QFont
from PySide6.QtWidgets import QWidget

from ui.core.design_tokens import ColorToken, RadiusToken


class LiquidNavWidget(QWidget):
    """Thanh điều hướng chính của Sidebar với phản hồi vật lý đàn hồi tinh tế (P0)."""

    tab_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = [
            {"icon": "📊", "id": 0, "tooltip": "Dashboard"},
            {"icon": "🎬", "id": 1, "tooltip": "Studio Workspace"},
            {"icon": "📋", "id": 2, "tooltip": "Queue & Output"},
            {"icon": "📦", "id": 3, "tooltip": "Draft Center"},
            {"icon": "🚀", "id": 4, "tooltip": "Export Center"},
            {"icon": "⚙️", "id": 5, "tooltip": "Settings Center"},
            {"icon": "❓", "id": 6, "tooltip": "Help Center"},
        ]

        self.tab_height = 42
        self.setFixedHeight(len(self.tabs) * self.tab_height)
        self.setFixedWidth(56)
        self.setMouseTracking(True)

        self.current_index = 0
        self._blob_height = 32.0
        self._blob_y = self._get_tab_center(0)
        self._target_y = self._blob_y
        self._is_dragging = False
        self._velocity_y = 0.0
        self._velocity_h = 0.0

        # Hover state
        self._hover_y = -100.0
        self._hover_target_y = -100.0
        self._hover_alpha = 0.0

        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self._update_physics)
        self.physics_timer.start(16)

    def _get_tab_center(self, index: int) -> float:
        return (index * self.tab_height) + (self.tab_height / 2.0)

    def _update_physics(self):
        # Hệ Lò Xo đàn hồi có kiểm soát (Restrained Spring Physics)
        # k: sức căng, damping: lực cản ma sát tránh rung lắc quá mức
        spring_k = 0.18
        damping = 0.72

        force_y = (self._target_y - self._blob_y) * spring_k
        self._velocity_y = (self._velocity_y + force_y) * damping
        self._blob_y += self._velocity_y

        # Độ co giãn theo vận tốc (Squash & Stretch có giới hạn)
        target_height = 32.0 + min(6.0, abs(self._velocity_y) * 0.8)
        force_h = (target_height - self._blob_height) * spring_k
        self._velocity_h = (self._velocity_h + force_h) * damping
        self._blob_height += self._velocity_h

        # Hover tracking
        if hasattr(self, '_hover_target_y') and self._hover_target_y >= 0:
            self._hover_y += (self._hover_target_y - self._hover_y) * 0.25
            self._hover_alpha += (40.0 - self._hover_alpha) * 0.2
        elif hasattr(self, '_hover_alpha'):
            self._hover_alpha += (0.0 - self._hover_alpha) * 0.2

        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            idx = int(event.pos().y() // self.tab_height)
            idx = max(0, min(len(self.tabs) - 1, idx))
            self.current_index = idx
            self._target_y = self._get_tab_center(idx)
            self.tab_changed.emit(self.tabs[idx]["id"])

    def mouseMoveEvent(self, event: QMouseEvent):
        self._hover_target_y = event.pos().y()

    def leaveEvent(self, event):
        self._hover_target_y = -100.0
        super().leaveEvent(event)

    def set_active_tab(self, page_id: int):
        for idx, tab in enumerate(self.tabs):
            if tab["id"] == page_id:
                self.current_index = idx
                self._target_y = self._get_tab_center(idx)
                break

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        radius = float(RadiusToken.CONTROL)  # 8px Control Geometry

        # 1. Hover Pill (Bóng mờ trượt nhẹ theo chuột)
        if self._hover_alpha > 1:
            hover_rect = QRectF(4, self._hover_y - 16, self.width() - 8, 32)
            painter.setBrush(QColor(255, 255, 255, int(self._hover_alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(hover_rect, radius, radius)

        # 2. Active Indicator (Khối chọn chính, phối màu Legacy Indigo / Cyan)
        blob_rect = QRectF(
            4,
            self._blob_y - (self._blob_height / 2.0),
            self.width() - 8,
            self._blob_height,
        )
        grad = QLinearGradient(blob_rect.topLeft(), blob_rect.bottomRight())
        grad.setColorAt(0.0, QColor(99, 102, 241, 160))  # Indigo
        grad.setColorAt(1.0, QColor(56, 189, 248, 120))  # Sky/Cyan
        painter.setBrush(grad)

        pen = QPen(QColor(165, 180, 252, 120))  # Viền kính mờ
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawRoundedRect(blob_rect, radius, radius)

        # 3. Icons
        font = QFont("Segoe UI Emoji", 15)
        painter.setFont(font)
        for i, tab in enumerate(self.tabs):
            rect = QRectF(0, i * self.tab_height, self.width(), self.tab_height)
            is_active = (i == self.current_index)
            painter.setPen(QColor(248, 250, 252, 255 if is_active else 150))
            painter.drawText(rect, Qt.AlignCenter, tab["icon"])
