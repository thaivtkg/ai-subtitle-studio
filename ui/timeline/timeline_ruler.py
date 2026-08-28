from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QRect

from ui.theme import Theme

class TimeRuler(QWidget):
    """[S8-T04] Thanh đo thời gian thích ứng tự động (Adaptive Time Ruler)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)  # Chiều cao cố định của Ruler
        self.duration_ms = 0
        self.pixels_per_second = 100

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)

        # Định nghĩa các mốc thời gian logic của con người (tính bằng giây)
        self.logical_intervals = [
            0.1, 0.2, 0.5,       # Zoom cận cảnh (mili-giây)
            1.0, 2.0, 5.0, 10.0, # Zoom bình thường
            30.0, 60.0, 120.0,   # Zoom xa (từng phút)
            300.0, 600.0, 1800.0 # Toàn cảnh
        ]

    def set_data(self, duration_ms: int):
        self.duration_ms = duration_ms
        self.update_geometry_size()
        self.update()

    def set_zoom(self, pixels_per_second: int):
        self.pixels_per_second = max(10, min(pixels_per_second, 1000))
        self.update_geometry_size()
        self.update()

    def update_geometry_size(self):
        total_width = int((self.duration_ms / 1000.0) * self.pixels_per_second)
        self.setMinimumWidth(total_width)

    def format_time(self, seconds: float) -> str:
        """Định dạng số giây thành chuỗi thời gian dễ đọc"""
        m = int(seconds // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 10)) # Lấy 1 chữ số thập phân (100ms)
        
        if ms > 0:
            return f"{m:02d}:{s:02d}.{ms}"
        return f"{m:02d}:{s:02d}"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # 1. Vẽ nền Ruler
        rect = event.rect()
        painter.fillRect(rect, QColor(Theme.SURFACE_ELEVATED))
        
        # Vẽ viền dưới phân cách
        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        painter.drawLine(rect.left(), self.height() - 1, rect.right(), self.height() - 1)

        if self.duration_ms <= 0:
            return

        # --- TÍNH TOÁN KHOẢNG CÁCH THÍCH ỨNG (ADAPTIVE INTERVAL) ---
        # Đảm bảo khoảng cách tối thiểu giữa 2 chữ số luôn là 70 pixel để không bị đè nhau
        min_pixels_between_labels = 70
        min_seconds_needed = min_pixels_between_labels / self.pixels_per_second
        
        # Tìm mốc thời gian logic nhỏ nhất thỏa mãn khoảng cách 70px
        interval_sec = 60.0 
        for interval in self.logical_intervals:
            if interval >= min_seconds_needed:
                interval_sec = interval
                break

        # --- VIEWPORT CULLING ---
        start_x = rect.left()
        end_x = rect.right()

        start_time_sec = max(0.0, start_x / self.pixels_per_second)
        end_time_sec = min(self.duration_ms / 1000.0, end_x / self.pixels_per_second)

        # Làm tròn thời gian bắt đầu vẽ về bội số của interval_sec
        first_tick_sec = (int(start_time_sec // interval_sec)) * interval_sec

        # Cấu hình cọ vẽ
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        text_pen = QPen(QColor(Theme.TEXT_SECONDARY))
        tick_pen = QPen(QColor(Theme.BORDER))

        # 2. Vòng lặp vẽ vạch và chữ
        current_sec = first_tick_sec
        while current_sec <= end_time_sec:
            x = int(current_sec * self.pixels_per_second)
            
            # Vẽ vạch (Tick)
            painter.setPen(tick_pen)
            painter.drawLine(x, self.height() - 8, x, self.height())
            
            # Vẽ Text Thời gian
            painter.setPen(text_pen)
            time_str = self.format_time(current_sec)
            
            # Căn lề trái cho mốc 0, căn giữa cho các mốc khác
            text_rect = QRect(x - 30, 2, 60, 20)
            if current_sec == 0:
                text_rect = QRect(x + 2, 2, 60, 20)
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, time_str)
            else:
                painter.drawText(text_rect, Qt.AlignCenter, time_str)

            current_sec += interval_sec
            
            # Dự phòng tránh vòng lặp vô hạn nếu float precision có vấn đề
            if interval_sec <= 0: break