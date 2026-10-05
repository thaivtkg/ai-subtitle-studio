import math
from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QMouseEvent, QPen, QPainterPath, QPixmap, QImage
from PySide6.QtWidgets import QWidget

LIQUID_GLASS = {
    "nav_width": 64,
    "nav_radius": 32,
    "active_width": 50,
    "active_height": 50,
    "active_radius": 25,
    "item_gap": 8,
    
    "diffusion_alpha": 0.13,
    "tint_idle": 0.08,
    "tint_active": 0.19,
    "saturation": 1.10,
    
    "refraction_y": 1.5,
    
    "dark_edge_width": 1.0,
    "dark_edge_alpha": 60,  # 0-255 scale (~24%)
    
    "specular_width": 1.2,
    "specular_alpha": 130,  # ~50%
    "inner_glow_alpha": 28, # ~11%
    
    "shadow_y": 5,
    "shadow_blur": 20,
    "shadow_alpha": 40,     # ~16%
    
    "hover_scale": 1.015,
    "press_scale": 0.985,
}

class LiquidNavWidget(QWidget):
    tab_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # API Contract: Phục hồi đủ 7 Tab khớp NAV_TO_STACK của Gui.py
        self.tabs = [
            {"icon": "📊", "id": 0, "tooltip": "Dashboard"},
            {"icon": "🎬", "id": 1, "tooltip": "Studio Workspace"},
            {"icon": "📋", "id": 3, "tooltip": "Queue & Output"},
            {"icon": "📦", "id": 4, "tooltip": "Draft Center"},
            {"icon": "🚀", "id": 5, "tooltip": "Export Center"},
            {"icon": "⚙️", "id": 6, "tooltip": "Settings"},
            {"icon": "❓", "id": 7, "tooltip": "Help"}
        ]
        
        self.tab_height = LIQUID_GLASS["active_height"] + LIQUID_GLASS["item_gap"]
        
        self.setFixedWidth(LIQUID_GLASS["nav_width"])
        self.setFixedHeight(len(self.tabs) * self.tab_height + 20)
        self.setMouseTracking(True)
        
        self.current_index = 0
        self._target_y = self._get_tab_y(0)
        
        # Spring Variables
        self._blob_y = self._target_y
        self._blob_vel = 0.0
        
        self._highlight_y = self._target_y
        self._highlight_vel = 0.0
        
        self._scale = 1.0
        self._scale_vel = 0.0
        self._target_scale = 1.0
        
        self._specular_alpha = LIQUID_GLASS["tint_idle"]
        self._specular_vel = 0.0
        self._target_specular = LIQUID_GLASS["tint_idle"]
        
        self._is_dragging = False
        
        # Background Cache
        self._blurred_bg = None
        self._tint_color = QColor(139, 92, 246)
        
        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self._update_physics)
        self.physics_timer.start(16)

        # API Contract: Proxy widgets cho Tour Anchors & Gui.py
        self.btn_map = {}
        for i, tab in enumerate(self.tabs):
            proxy = QWidget(self)
            proxy.setGeometry(0, self._get_tab_y(i), LIQUID_GLASS["nav_width"], LIQUID_GLASS["active_height"])
            self.btn_map[tab["id"]] = proxy
        self.btn_map[2] = self.btn_map.get(3, self.btn_map.get(2))

    def set_active_tab(self, page_id: int):
        """API Hotfix: Chuyển tab từ xa cho Gui.py"""
        for idx, tab in enumerate(self.tabs):
            if tab["id"] == page_id or (page_id in (2, 3) and tab["id"] in (2, 3)):
                self.current_index = idx
                self._target_y = self._get_tab_y(idx)
                break

    def _get_tab_y(self, index):
        return 10 + index * self.tab_height

    def _update_background_cache(self):
        if not self.parentWidget(): return
        
        self.hide()
        raw_bg = self.parentWidget().grab(self.geometry())
        self.show()
        
        img = raw_bg.toImage()
        if img.isNull(): return
        
        small = img.scaled(img.width() // 8, img.height() // 8, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self._blurred_bg = QPixmap.fromImage(small.scaled(img.width(), img.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        
        center_color = small.pixelColor(small.width() // 2, small.height() // 2)
        self._tint_color = QColor(
            min(255, int(center_color.red() * 0.8 + 50)),
            min(255, int(center_color.green() * 0.8 + 50)),
            min(255, int(center_color.blue() * 0.8 + 60))
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(100, self._update_background_cache)

    def _update_physics(self):
        stiffness = 0.15
        damping = 0.65
        
        f_y = (self._target_y - self._blob_y) * stiffness
        self._blob_vel = (self._blob_vel + f_y) * damping
        self._blob_y += self._blob_vel
        
        f_hy = (self._target_y - self._highlight_y) * (stiffness * 0.6)
        self._highlight_vel = (self._highlight_vel + f_hy) * (damping * 0.9)
        self._highlight_y += self._highlight_vel
        
        f_s = (self._target_scale - self._scale) * 0.2
        self._scale_vel = (self._scale_vel + f_s) * 0.7
        self._scale += self._scale_vel
        
        f_a = (self._target_specular - self._specular_alpha) * 0.2
        self._specular_vel = (self._specular_vel + f_a) * 0.7
        self._specular_alpha += self._specular_vel

        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._target_scale = LIQUID_GLASS["press_scale"]
            self._target_specular = LIQUID_GLASS["tint_active"]
            self._target_y = max(10, min(self.height() - LIQUID_GLASS["active_height"], event.pos().y() - LIQUID_GLASS["active_height"]/2))

    def mouseMoveEvent(self, event: QMouseEvent):
        if getattr(self, "_is_dragging", False):
            self._target_y = max(10, min(self.height() - LIQUID_GLASS["active_height"], event.pos().y() - LIQUID_GLASS["active_height"]/2))

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            self._target_scale = LIQUID_GLASS["hover_scale"] if self.underMouse() else 1.0
            
            idx = round((self._target_y - 10) / self.tab_height)
            idx = max(0, min(len(self.tabs) - 1, idx))
            self.current_index = idx
            self._target_y = self._get_tab_y(idx)
            self.tab_changed.emit(self.tabs[idx]["id"])

    def enterEvent(self, event):
        self._target_scale = LIQUID_GLASS["hover_scale"]
        self._target_specular = LIQUID_GLASS["tint_active"]
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._is_dragging:
            self._target_scale = 1.0
            self._target_specular = LIQUID_GLASS["tint_idle"]
            self._target_y = self._get_tab_y(self.current_index)
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pad_x = (self.width() - LIQUID_GLASS["active_width"]) / 2
        center_y = self._blob_y + (LIQUID_GLASS["active_height"] / 2)
        center_x = self.width() / 2
        
        painter.translate(center_x, center_y)
        painter.scale(self._scale, self._scale)
        painter.translate(-center_x, -center_y)

        blob_rect = QRectF(pad_x, self._blob_y, LIQUID_GLASS["active_width"], LIQUID_GLASS["active_height"])
        
        path = QPainterPath()
        path.addRoundedRect(blob_rect, LIQUID_GLASS["active_radius"], LIQUID_GLASS["active_radius"])

        # 1. Background Blur & Refraction
        if self._blurred_bg:
            painter.save()
            painter.setClipPath(path)
            source_rect = QRectF(blob_rect.x(), blob_rect.y() - LIQUID_GLASS["refraction_y"], blob_rect.width(), blob_rect.height())
            painter.drawPixmap(blob_rect, self._blurred_bg, source_rect)
            painter.restore()

        # 2. Context-aware Tint
        painter.save()
        painter.setClipPath(path)
        tint_alpha = int(self._specular_alpha * 255)
        painter.fillPath(path, QColor(self._tint_color.red(), self._tint_color.green(), self._tint_color.blue(), tint_alpha))
        painter.restore()

        # 3. Inner Glow
        painter.save()
        inner_pen = QPen(QColor(255, 255, 255, LIQUID_GLASS["inner_glow_alpha"]))
        inner_pen.setWidthF(1.0)
        painter.setPen(inner_pen)
        painter.drawPath(path)
        painter.restore()

        # 4. Darkened Edge (Viền tối chặn sáng đáy)
        dark_grad = QLinearGradient(blob_rect.topLeft(), blob_rect.bottomLeft())
        dark_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        dark_grad.setColorAt(0.7, QColor(0, 0, 0, int(LIQUID_GLASS["dark_edge_alpha"] * 0.3)))
        dark_grad.setColorAt(1.0, QColor(0, 0, 0, LIQUID_GLASS["dark_edge_alpha"]))
        
        painter.save()
        dark_pen = QPen(dark_grad, LIQUID_GLASS["dark_edge_width"])
        painter.setPen(dark_pen)
        painter.drawPath(path)
        painter.restore()

        # 5. Specular Highlight (Vệt sáng phản quang trễ pha)
        spec_grad = QLinearGradient(blob_rect.left(), self._highlight_y, blob_rect.right(), self._highlight_y + LIQUID_GLASS["active_height"])
        spec_grad.setColorAt(0.0, QColor(255, 255, 255, LIQUID_GLASS["specular_alpha"]))
        spec_grad.setColorAt(0.35, QColor(255, 255, 255, int(LIQUID_GLASS["specular_alpha"] * 0.1)))
        spec_grad.setColorAt(0.4, QColor(255, 255, 255, 0))
        
        painter.save()
        spec_pen = QPen(spec_grad, LIQUID_GLASS["specular_width"])
        painter.setPen(spec_pen)
        painter.drawPath(path)
        painter.restore()

        # 6. Icons & Text
        painter.resetTransform()
        font = painter.font()
        font.setPointSize(14)
        painter.setFont(font)
        
        for i, tab in enumerate(self.tabs):
            item_y = self._get_tab_y(i)
            rect = QRectF(0, item_y, self.width(), LIQUID_GLASS["active_height"])
            
            dist = abs(self._blob_y - item_y)
            is_active = dist < (LIQUID_GLASS["active_height"] / 2)
            
            if is_active:
                painter.setPen(QColor(255, 255, 255, 255))
            else:
                painter.setPen(QColor(156, 163, 175, 180))
                
            painter.drawText(rect, Qt.AlignCenter, tab["icon"])
