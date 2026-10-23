import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect

from ui.theme import Theme

class WaveformView(QWidget):
    """[S8-T09] Widget vẽ Sóng âm tối ưu hiệu năng với Viewport Culling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(75)  # Chiều cao cố định cho track sóng âm
        self.waveform_data = None
        self.duration_ms = 0
        self.pixels_per_second = 100  # Hệ số Zoom mặc định (100px = 1 giây)
        self.chunk_ms = 10            # Độ phân giải (Đồng bộ với WaveformService)
        self._selected_range_ms = None
        self.heatmap_enabled = True
        self.visual_gain = 1.0

        # Cờ tối ưu hóa: Báo cho Qt biết ta sẽ tự vẽ toàn bộ nền để tránh vẽ 2 lần (Overdraw)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def _calculate_visual_gain(self, peaks: np.ndarray) -> float:
        """Khuếch đại hiển thị tự động (Auto-gain) cho audio giọng nói âm lượng nhỏ."""
        if peaks is None or len(peaks) == 0:
            return 1.0
        try:
            abs_peaks = np.abs(peaks)
            amp_95 = float(np.percentile(abs_peaks, 95))
            if amp_95 < 0.4:
                return float(min(4.0, 0.75 / max(amp_95, 0.03)))
            return 1.0
        except Exception:
            return 1.0

    def get_heatmap_color(self, min_peak: float, max_peak: float) -> QColor:
        if not getattr(self, "heatmap_enabled", True):
            return QColor(Theme.PRIMARY_PURPLE)
        amp = (max_peak - min_peak) / 2.0
        # Peak amplitude: > 0.75 (> -14 dB) is loud (Cam Đỏ), < 0.15 (< -26 dB) is whisper (Xanh Ngọc)
        if amp >= 0.75:
            return QColor(239, 68, 68)  # Cam Đỏ
        elif amp <= 0.15:
            return QColor(6, 182, 212)  # Xanh Ngọc
        else:
            return QColor(16, 185, 129)  # Xanh Lục

    def set_data(self, peaks_normalized: np.ndarray, duration_ms: int):
        """Nhận dữ liệu từ WaveformService và render"""
        self.waveform_data = peaks_normalized
        self.duration_ms = duration_ms
        self.visual_gain = self._calculate_visual_gain(peaks_normalized)
        self.update_geometry_size()
        self.update()

    def set_zoom(self, pixels_per_second: int):
        """Cập nhật hệ số Zoom và yêu cầu vẽ lại"""
        self.pixels_per_second = max(10, min(pixels_per_second, 1000))
        self.update_geometry_size()
        self.update()

    def set_selected_range(self, start_ms: int, end_ms: int) -> None:
        try:
            start_ms = max(0, int(start_ms))
            end_ms = max(0, int(end_ms))
        except (TypeError, ValueError):
            self.clear_selected_range()
            return

        if self.duration_ms > 0:
            start_ms = min(start_ms, self.duration_ms)
            end_ms = min(end_ms, self.duration_ms)

        if end_ms <= start_ms:
            self.clear_selected_range()
            return

        self._selected_range_ms = (start_ms, end_ms)
        self.update()

    def clear_selected_range(self) -> None:
        self._selected_range_ms = None
        self.update()

    def _ms_to_x(self, ms: int) -> int:
        return int((ms / 1000.0) * self.pixels_per_second)

    def _selected_range_rect(self):
        if self._selected_range_ms is None:
            return None

        start_ms, end_ms = self._selected_range_ms
        x1 = self._ms_to_x(start_ms)
        x2 = self._ms_to_x(end_ms)
        return QRect(x1, 1, max(1, x2 - x1), max(1, self.height() - 2))

    def update_geometry_size(self):
        """Tính toán và thiết lập chiều dài thực tế của Widget dựa trên độ dài Audio và Zoom"""
        total_width = int((self.duration_ms / 1000.0) * self.pixels_per_second)
        self.setMinimumWidth(total_width)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Bật Antialiasing để nét vẽ bo tròn mềm mại chuẩn Studio NLE
        painter.setRenderHint(QPainter.Antialiasing, True) 

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

        # --- BAR SPACING & AUTO-GAIN VISUAL SCALING ---
        # Nhóm mẫu âm thanh theo cột rời rạc (bar_width=2px, gap=1px -> bước 3px)
        bar_peaks = {}
        for i, (min_peak, max_peak) in enumerate(visible_chunks):
            chunk_idx = start_idx + i
            raw_x = self._ms_to_x(chunk_idx * self.chunk_ms)
            bar_x = (raw_x // 3) * 3
            
            if bar_x not in bar_peaks:
                bar_peaks[bar_x] = [min_peak, max_peak]
            else:
                if min_peak < bar_peaks[bar_x][0]: bar_peaks[bar_x][0] = min_peak
                if max_peak > bar_peaks[bar_x][1]: bar_peaks[bar_x][1] = max_peak

        gain = getattr(self, "visual_gain", 1.0)
        for bar_x, (min_peak, max_peak) in bar_peaks.items():
            pen = QPen(self.get_heatmap_color(min_peak, max_peak), 2)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)

            scaled_min = max(-1.0, min(1.0, min_peak * gain))
            scaled_max = max(-1.0, min(1.0, max_peak * gain))
            y_min = int(center_y - (scaled_min * half_height))
            y_max = int(center_y - (scaled_max * half_height))
            if abs(y_max - y_min) < 2:
                y_min = int(center_y - 1)
                y_max = int(center_y + 1)
            painter.drawLine(bar_x, y_min, bar_x, y_max)

        selected_rect = self._selected_range_rect()
        if selected_rect is not None:
            # Dim the outside region
            dim_color = QColor(Theme.BG_APP)
            dim_color.setAlpha(180)
            painter.setPen(Qt.NoPen)
            painter.setBrush(dim_color)
            
            # Left dim
            if selected_rect.left() > 0:
                painter.drawRect(0, 0, selected_rect.left(), self.height())
            # Right dim
            if selected_rect.right() < self.width():
                painter.drawRect(selected_rect.right(), 0, self.width() - selected_rect.right(), self.height())
            
            selection_fill = QColor(Theme.CYAN)
            selection_fill.setAlpha(30)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(selection_fill)
            painter.drawRoundedRect(selected_rect, 3, 3)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(Theme.CYAN), 2))
            painter.drawRoundedRect(selected_rect, 3, 3)
            
            # Draw Floating Tooltip for Waveform
            start_ms, end_ms = self._selected_range_ms
            dur = int(end_ms - start_ms)
            tt_text = f"{start_ms/1000:.3f}s - {end_ms/1000:.3f}s ({dur}ms)"
            from PySide6.QtGui import QFont
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tt_fm = painter.fontMetrics()
            tt_width = tt_fm.horizontalAdvance(tt_text) + 12
            
            # Position at top-left of the selected range, inside the view
            tt_x = selected_rect.left()
            tt_y = 5
            
            # Adjust if tooltip goes out of bounds
            if tt_x + tt_width > self.width():
                tt_x = self.width() - tt_width
            if tt_x < 0:
                tt_x = 0
                
            tt_rect = QRect(tt_x, tt_y, tt_width, 18)
            
            # Draw Badge
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(Theme.SURFACE_ELEVATED))
            painter.drawRoundedRect(tt_rect, 4, 4)
            
            painter.setPen(QColor(Theme.CYAN))
            painter.drawText(tt_rect, Qt.AlignCenter, tt_text)
