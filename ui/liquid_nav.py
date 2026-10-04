from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QPoint, QEvent
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QMouseEvent, QPen, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from ui.core.design_tokens import RadiusToken


class LiquidNavWidget(QWidget):
    """
    Thanh điều hướng Sidebar với hiệu ứng trượt Liquid Glass (Hooke's Law Spring Physics).
    Phân bổ khoảng cách thoáng đãng, icon to rõ, chống hiện tượng ghost-hover ra ngoài vùng nút.
    """

    tab_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(56)
        self.setMouseTracking(True)

        self.primary_tabs = [
            (0, "📊", "Dashboard"),
            (1, "🎬", "Studio Workspace"),
            (3, "📋", "Queue & Output"),
            (4, "📦", "Draft Center"),
            (5, "🚀", "Export Center"),
        ]
        self.system_tabs = [
            (6, "⚙", "Settings Center"),
            (7, "❓", "Help Center"),
        ]

        self.btn_map = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)  # Dàn đều khoảng cách giữa các icon
        layout.setAlignment(Qt.AlignHCenter)

        for idx, icon, tooltip in self.primary_tabs:
            btn = self._create_tab_button(idx, icon, tooltip)
            layout.addWidget(btn, alignment=Qt.AlignHCenter)
            self.btn_map[idx] = btn

        layout.addStretch(1)

        for idx, icon, tooltip in self.system_tabs:
            btn = self._create_tab_button(idx, icon, tooltip)
            layout.addWidget(btn, alignment=Qt.AlignHCenter)
            self.btn_map[idx] = btn

        # Compatibility alias: 2 -> Queue (3)
        self.btn_map[2] = self.btn_map[3]

        self.current_index = 0
        self._blob_height = 44.0
        self._blob_y = 26.0
        self._target_y = 26.0
        self._velocity_y = 0.0
        self._velocity_h = 0.0

        # Hover state
        self._hover_y = -100.0
        self._hover_target_y = -100.0
        self._hover_alpha = 0.0

        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self._update_physics)
        self.physics_timer.start(16)

    def _create_tab_button(self, idx: int, icon: str, tooltip: str) -> QPushButton:
        btn = QPushButton(icon, self)
        btn.setObjectName(f"nav_btn_{idx}")
        btn.setFixedSize(48, 44)  # Nút to hơn và rõ nét hơn
        btn.setFont(QFont("Segoe UI Emoji", 15))
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("variant", "liquid-nav-btn")
        btn.setProperty("active", "false")
        btn.installEventFilter(self)
        btn.clicked.connect(lambda checked=False, p=idx: self._on_btn_clicked(p))
        return btn

    def eventFilter(self, watched, event):
        # Chỉ kích hoạt hover pill khi chuột thực sự nằm trên một nút điều hướng
        if event.type() == QEvent.Enter:
            self._hover_target_y = float(watched.y() + (watched.height() / 2.0))
        elif event.type() == QEvent.Leave:
            self._hover_target_y = -100.0
        return super().eventFilter(watched, event)

    def _on_btn_clicked(self, idx: int):
        self.set_active_tab(idx)
        self.tab_changed.emit(idx)

    def _get_button_center_y(self, idx: int) -> float:
        btn = self.btn_map.get(idx)
        if btn and btn.height() > 0:
            center = float(btn.y() + (btn.height() / 2.0))
            if center > 0:
                return center
        # Fallback estimation before layout is painted
        for i, (tab_id, _, _) in enumerate(self.primary_tabs):
            if tab_id == idx:
                return float(i * 58 + 26)
        for i, (tab_id, _, _) in enumerate(self.system_tabs):
            if tab_id == idx:
                return float(self.height() - (len(self.system_tabs) - i) * 58 + 26)
        return 26.0

    def set_active_tab(self, page_id: int):
        self.current_index = page_id
        target = self._get_button_center_y(page_id)
        if target > 0:
            self._target_y = target

        for i, btn in self.btn_map.items():
            is_active = (i == page_id or (page_id == 2 and i == 3))
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def leaveEvent(self, event):
        self._hover_target_y = -100.0
        super().leaveEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._sync_target_pos)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_target_pos()

    def _sync_target_pos(self):
        target = self._get_button_center_y(self.current_index)
        if target > 0:
            self._target_y = target
            if abs(self._blob_y - 26.0) < 1.0:
                self._blob_y = target

    def _update_physics(self):
        btn = self.btn_map.get(self.current_index)
        if btn and btn.height() > 0:
            target = float(btn.y() + (btn.height() / 2.0))
            if target > 0 and abs(target - self._target_y) > 0.5:
                self._target_y = target

        # Hệ Lò Xo đàn hồi có kiểm soát (Restrained Hooke's Law Spring Physics)
        spring_k = 0.20
        damping = 0.70

        force_y = (self._target_y - self._blob_y) * spring_k
        self._velocity_y = (self._velocity_y + force_y) * damping
        self._blob_y += self._velocity_y

        # Độ co giãn theo vận tốc (Squash & Stretch)
        target_height = 44.0 + min(6.0, abs(self._velocity_y) * 0.7)
        force_h = (target_height - self._blob_height) * spring_k
        self._velocity_h = (self._velocity_h + force_h) * damping
        self._blob_height += self._velocity_h

        # Hover tracking
        if self._hover_target_y >= 0:
            self._hover_y += (self._hover_target_y - self._hover_y) * 0.28
            self._hover_alpha += (40.0 - self._hover_alpha) * 0.22
        else:
            self._hover_alpha += (0.0 - self._hover_alpha) * 0.22

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        radius = float(RadiusToken.CONTROL)  # 8px Control Geometry

        # 1. Hover Pill (Bóng mờ trượt chính xác theo nút đang hover)
        if self._hover_alpha > 1:
            hover_rect = QRectF(4, self._hover_y - 22, 48, 44)
            painter.setBrush(QColor(255, 255, 255, int(self._hover_alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(hover_rect, radius, radius)

        # 2. Active Liquid Glass Blob (Khối kính lỏng đàn hồi trượt theo tab chọn)
        blob_rect = QRectF(
            4,
            self._blob_y - (self._blob_height / 2.0),
            48,
            self._blob_height,
        )
        grad = QLinearGradient(blob_rect.topLeft(), blob_rect.bottomRight())
        grad.setColorAt(0.0, QColor(99, 102, 241, 160))  # Legacy Indigo
        grad.setColorAt(1.0, QColor(56, 189, 248, 120))  # Cyan/Sky
        painter.setBrush(grad)

        pen = QPen(QColor(165, 180, 252, 140))  # Viền kính mờ
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawRoundedRect(blob_rect, radius, radius)
