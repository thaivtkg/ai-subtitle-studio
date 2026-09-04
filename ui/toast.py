from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFrame

from ui.theme import Theme

class Toast(QWidget):
    def __init__(self, parent, message, type="success", duration=3000):
        super().__init__(parent)
        
        # Cấu hình cửa sổ nổi trong suốt
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # Layout chính của cửa sổ nổi
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # [FIX] Bọc nội dung vào QFrame để giữ được màu nền khi bật WA_TranslucentBackground
        self.container = QFrame()
        content_layout = QHBoxLayout(self.container)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(10)

        if type == "success":
            icon_char = "✅"
            accent_color = Theme.SUCCESS
        elif type == "error":
            icon_char = "❌"
            accent_color = Theme.DANGER
        else:
            icon_char = "ℹ️"
            accent_color = Theme.CYAN

        # Ép CSS trực tiếp cho Container
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE_ELEVATED};
                border: 1px solid {Theme.BORDER};
                border-left: 4px solid {accent_color};
                border-radius: 6px;
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                border: none;
                background: transparent;
            }}
        """)

        lbl_icon = QLabel(icon_char)
        lbl_icon.setStyleSheet(f"color: {accent_color}; font-size: 14px;")
        
        lbl_msg = QLabel(message)
        
        content_layout.addWidget(lbl_icon)
        content_layout.addWidget(lbl_msg)
        
        main_layout.addWidget(self.container)
        
        self.duration = duration
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fade_out)
        
        self.anim_in = QPropertyAnimation(self, b"windowOpacity")
        self.anim_in.setDuration(250)
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(1.0)
        self.anim_in.setEasingCurve(QEasingCurve.OutQuad)

        self.anim_out = QPropertyAnimation(self, b"windowOpacity")
        self.anim_out.setDuration(350)
        self.anim_out.setStartValue(1.0)
        self.anim_out.setEndValue(0.0)
        self.anim_out.setEasingCurve(QEasingCurve.InQuad)
        
        self.anim_out.finished.connect(self.close)
        self.anim_out.finished.connect(self.deleteLater)

    def show_toast(self):
        if self.parent():
            parent_rect = self.parent().geometry()
            self.adjustSize() # Ép Qt tính toán kích thước thực trước khi lấy size
            toast_size = self.size()

            for toast in self.parent().findChildren(Toast):
                if toast is self:
                    continue
                toast.timer.stop()
                toast.anim_in.stop()
                toast.anim_out.stop()
                toast.close()
                toast.deleteLater()
            
            # [FIX] Dời vị trí sang Góc Dưới - Bên Phải (Cách lề phải 24px)
            x = parent_rect.x() + parent_rect.width() - toast_size.width() - 24
            # [FIX] Nâng lên 140px để nhảy vọt qua toàn bộ thanh Bottom Control Bar
            y = parent_rect.y() + parent_rect.height() - toast_size.height() - 140

            self.move(x, y)
            
        self.show()
        self.anim_in.start()
        self.timer.start(self.duration)

    def fade_out(self):
        self.timer.stop()
        self.anim_out.start()
        
    @classmethod
    def show_success(cls, parent, message, duration=3000):
        toast = cls(parent, message, "success", duration)
        toast.show_toast()

    @classmethod
    def show_error(cls, parent, message, duration=4000):
        toast = cls(parent, message, "error", duration)
        toast.show_toast()
        
    @classmethod
    def show_info(cls, parent, message, duration=3000):
        toast = cls(parent, message, "info", duration)
        toast.show_toast()
