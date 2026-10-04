import sys
from PySide6.QtCore import Qt, QTimer, QRectF, QObject, QEvent, QPoint
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QTabBar, QListWidget

class LiquidOverlayWidget(QWidget):
    def __init__(self, target):
        super().__init__(target.parentWidget())
        self.target = target
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # Bắt target phải theo dõi chuột
        self.target.setMouseTracking(True)
        if hasattr(self.target, "viewport"):
            self.target.viewport().setMouseTracking(True)
            self.target.viewport().installEventFilter(self)
        else:
            self.target.installEventFilter(self)
            
        self._hover_pos = -100
        self._target_pos = -100
        self._alpha = 0.0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_physics)
        self.timer.start(16)
        self.raise_()
        
    def _update_physics(self):
        if self._target_pos >= 0:
            self._hover_pos += (self._target_pos - self._hover_pos) * 0.25
            self._alpha += (50 - self._alpha) * 0.2
        else:
            self._alpha += (0 - self._alpha) * 0.2
            
        if abs(self._target_pos - self._hover_pos) > 0.5 or self._alpha > 1:
            self.setGeometry(self.target.geometry())
            self.raise_()
            self.update()
            
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            # Lấy tọa độ X cho Tab ngang, Y cho Menu dọc
            if isinstance(self.target, QTabBar):
                self._target_pos = event.position().x()
            else:
                self._target_pos = event.position().y()
        elif event.type() == QEvent.Leave:
            self._target_pos = -100
        elif event.type() == QEvent.Resize:
            self.setGeometry(self.target.geometry())
        return False
        
    def paintEvent(self, event):
        if self._alpha > 1:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(255, 255, 255, int(self._alpha)))
            painter.setPen(Qt.NoPen)
            
            if isinstance(self.target, QTabBar):
                tab_idx = self.target.tabAt(QPoint(int(self._hover_pos), self.target.height() // 2))
                w = self.target.tabRect(tab_idx).width() if tab_idx >= 0 else 80
                rect = QRectF(self._hover_pos - w / 2, 4, w, self.height() - 8)
                painter.drawRoundedRect(rect, 8, 8)
            elif hasattr(self.target, "itemAt"):
                item = self.target.itemAt(self.width() // 2, int(self._hover_pos))
                if item:
                    item_rect = self.target.visualItemRect(item)
                    h = item_rect.height()
                    rect = QRectF(4, self._hover_pos - h / 2, self.width() - 8, h)
                    painter.drawRoundedRect(rect, 8, 8)

