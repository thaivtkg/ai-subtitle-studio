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
        elif type == "warning":
            icon_char = "⚠️"
            accent_color = Theme.WARNING
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

    def _display(self):
        if self.parent():
            parent_rect = self.parent().geometry()
            self.adjustSize() # Ép Qt tính toán kích thước thực trước khi lấy size
            toast_size = self.size()
            
            # [FIX] Dời vị trí sang Góc Dưới - Bên Phải (Cách lề phải 24px)
            x = parent_rect.x() + parent_rect.width() - toast_size.width() - 24
            # [FIX] Nâng lên 140px để nhảy vọt qua toàn bộ thanh Bottom Control Bar
            y = parent_rect.y() + parent_rect.height() - toast_size.height() - 140
            
            self.move(x, y)
            
        self.show()
        self.anim_in.start()
        self.timer.start(self.duration)

    def show_toast(self_or_first, *args, **kwargs):
        """Hỗ trợ gọi cả dạng instance (toast.show_toast()) lẫn class/helper (Toast.show_toast(parent, msg))."""
        if isinstance(self_or_first, Toast):
            self_or_first._display()
            return self_or_first
        if self_or_first is Toast:
            parent = args[0] if len(args) > 0 else kwargs.get("parent")
            message = args[1] if len(args) > 1 else kwargs.get("message", "")
        else:
            parent = self_or_first
            message = args[0] if len(args) > 0 else kwargs.get("message", "")
        duration = kwargs.get("duration", 3000)
        duration_ms = kwargs.get("duration_ms")
        dur = duration_ms if duration_ms is not None else duration
        toast = Toast(parent, message, "info", dur)
        toast._display()
        return toast

    def fade_out(self):
        self.timer.stop()
        self.anim_out.start()
        
    @classmethod
    def show_success(cls, parent, message, duration=3000, duration_ms=None):
        dur = duration_ms if duration_ms is not None else duration
        toast = cls(parent, message, "success", dur)
        toast._display()
        return toast

    @classmethod
    def show_error(cls, parent, message, duration=4000, duration_ms=None):
        dur = duration_ms if duration_ms is not None else duration
        toast = cls(parent, message, "error", dur)
        toast._display()
        return toast

    @classmethod
    def show_warning(cls, parent, message, duration=3000, duration_ms=None):
        dur = duration_ms if duration_ms is not None else duration
        toast = cls(parent, message, "warning", dur)
        toast._display()
        return toast

    @classmethod
    def show_info(cls, parent, message, duration=3000, duration_ms=None):
        dur = duration_ms if duration_ms is not None else duration
        toast = cls(parent, message, "info", dur)
        toast._display()
        return toast