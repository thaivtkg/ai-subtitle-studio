import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect

from ui.theme import Theme

class WaveformView(QWidget):
    """[S8-T09] Widget vẽ Sóng âm tối ưu hiệu năng với Viewport Culling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)  # Chiều cao cố định cho track sóng âm
        self.waveform_data = None
        self.duration_ms = 0
        self.pixels_per_second = 100  # Hệ số Zoom mặc định (100px = 1 giây)
        self.chunk_ms = 10            # Độ phân giải (Đồng bộ với WaveformService)

        # Cờ tối ưu hóa: Báo cho Qt biết ta sẽ tự vẽ toàn bộ nền để tránh vẽ 2 lần (Overdraw)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def set_data(self, peaks_normalized: np.ndarray, duration_ms: int):
        """Nhận dữ liệu từ WaveformService và render"""
        self.waveform_data = peaks_normalized
        self.duration_ms = duration_ms
        self.update_geometry_size()
        self.update()

    def set_zoom(self, pixels_per_second: int):
        """Cập nhật hệ số Zoom và yêu cầu vẽ lại"""
        self.pixels_per_second = max(10, min(pixels_per_second, 1000))
        self.update_geometry_size()
        self.update()

    def update_geometry_size(self):
        """Tính toán và thiết lập chiều dài thực tế của Widget dựa trên độ dài Audio và Zoom"""
        total_width = int((self.duration_ms / 1000.0) * self.pixels_per_second)
        self.setMinimumWidth(total_width)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Tắt Antialiasing để nét vẽ sắc sảo hơn và render siêu tốc
        painter.setRenderHint(QPainter.Antialiasing, False) 

        # 1. Vẽ phông nền
        rect = event.rect()
        painter.fillRect(rect, QColor(Theme.BG_APP))

        # 1. Nếu chưa có Video (duration = 0)
        if self.duration_ms <= 0:
            painter.setPen(QColor(Theme.TEXT_MUTED))
            painter.drawText(rect, Qt.AlignCenter, "Chưa nạp Video")
            return

        # 2. Nếu có Video nhưng mảng sóng âm chưa load xong
        if self.waveform_data is None or len(self.waveform_data) == 0:
            painter.setPen(QColor(Theme.TEXT_MUTED))
            painter.drawText(rect, Qt.AlignCenter, "Đang khởi tạo sóng âm...")
            return

        # Cấu hình màu cọ vẽ Sóng âm
        pen = QPen(QColor(Theme.PRIMARY_PURPLE))
        pen.setWidth(1)
        painter.setPen(pen)

        height = self.height()
        center_y = height / 2.0
        half_height = height / 2.0

        # --- KỸ THUẬT VIEWPORT CULLING ---
        # Chỉ quét và vẽ các Index nằm gọn trong event.rect() (Vùng người dùng đang nhìn)
        start_x = rect.left()
        end_x = rect.right()

        # Quy đổi Pixel -> Thời gian (ms)
        start_ms = (start_x / self.pixels_per_second) * 1000.0
        end_ms = (end_x / self.pixels_per_second) * 1000.0

        # Quy đổi Thời gian -> Index trong mảng Numpy
        start_idx = max(0, int(start_ms / self.chunk_ms))
        end_idx = min(len(self.waveform_data) - 1, int(end_ms / self.chunk_ms) + 1)

        if start_idx > end_idx:
            return

        # Slicing mảng numpy để lấy đúng khúc cần vẽ
        visible_chunks = self.waveform_data[start_idx:end_idx + 1]

        # 2. Bắt đầu vòng lặp vẽ
        last_x = -1
        for i, (min_peak, max_peak) in enumerate(visible_chunks):
            chunk_idx = start_idx + i
            
            # Tính tọa độ X trên UI
            x = int((chunk_idx * self.chunk_ms / 1000.0) * self.pixels_per_second)
            
            # Khử Overdraw: Nếu tọa độ x trùng với x trước đó (do Zoom quá nhỏ), bỏ qua vẽ đè
            if x == last_x:
                continue
            last_x = x

            # Tính tọa độ Y: Map giá trị float [-1.0, 1.0] sang tọa độ pixel
            y_min = int(center_y - (min_peak * half_height))
            y_max = int(center_y - (max_peak * half_height))
            
            painter.drawLine(x, y_min, x, y_max)