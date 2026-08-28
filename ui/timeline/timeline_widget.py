from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from ui.timeline.subtitle_track import SubtitleTrack
from ui.timeline.timeline_ruler import TimeRuler
from ui.timeline.waveform_view import WaveformView

from ui.theme import Theme


class PlayheadOverlay(QWidget):
    """[S8-T06] Lớp phủ trong suốt chỉ dùng để vẽ Kim thời gian, tối ưu Overdraw"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # Xuyên chuột, không chặn click
        self.playhead_x = 0

    def set_position(self, x: int):
        self.playhead_x = x
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        # Vẽ kim đỏ nổi bật
        pen = QPen(QColor(Theme.DANGER))
        pen.setWidth(2)
        painter.setPen(pen)
        
        painter.drawLine(self.playhead_x, 0, self.playhead_x, self.height())

class TimelineContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Khởi tạo các Component cốt lõi
        self.ruler = TimeRuler()
        self.waveform = WaveformView()
        self.track = SubtitleTrack()  # <--- THÊM TRACK
        
        self.layout.addWidget(self.ruler)
        self.layout.addWidget(self.waveform)
        self.layout.addWidget(self.track) # <--- ĐẨY VÀO LAYOUT
        self.layout.addStretch()

        self.playhead = PlayheadOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.playhead.resize(self.width(), self.height())

class TimelineWidget(QScrollArea):
    seek_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea {{ border: 1px solid {Theme.BORDER}; background-color: {Theme.BG_APP}; }}")

        self.container = TimelineContainer()
        self.setWidget(self.container)

        self.duration_ms = 0
        self.pixels_per_second = 100

        # --- CƠ CHẾ AUTO-SCROLL ---
        self.auto_scroll_enabled = True
        self._internal_scroll = False # Phân biệt cuộn do Code hay do User
        self.horizontalScrollBar().valueChanged.connect(self._on_user_scroll)

    def _on_user_scroll(self, value):
        """Tự động tắt Auto-scroll nếu người dùng chủ động kéo thanh cuộn"""
        if not self._internal_scroll:
            self.auto_scroll_enabled = False

    def reset_auto_scroll(self):
        """Gọi hàm này khi người dùng bấm nút Play video để bật lại cuộn tự động"""
        self.auto_scroll_enabled = True

    def load_project_data(self, duration_ms: int, segments: list, peaks_normalized=None):
        self.duration_ms = duration_ms
        self.container.ruler.set_data(duration_ms)
        self.container.track.set_data(segments, duration_ms)
        if peaks_normalized is not None:
            self.container.waveform.set_data(peaks_normalized, duration_ms)

    def set_zoom(self, pixels_per_second: int):
        self.pixels_per_second = pixels_per_second
        self.container.ruler.set_zoom(pixels_per_second)
        self.container.waveform.set_zoom(pixels_per_second)
        self.container.track.set_zoom(pixels_per_second)
        self.container.adjustSize()

    def update_playhead(self, playhead_ms: int):
        """[S8-T33] Cập nhật vị trí kim và tự động cuộn màn hình"""
        x = int((playhead_ms / 1000.0) * self.pixels_per_second)
        self.container.playhead.set_position(x)
        self.container.track.update_playhead(playhead_ms)

        if self.auto_scroll_enabled:
            self._center_on_x(x)

    def _center_on_x(self, x: int):
        """Tính toán khoảng cách để đưa Playhead ra giữa màn hình hiển thị"""
        self._internal_scroll = True
        viewport_width = self.viewport().width()
        target_scroll = x - (viewport_width // 2)
        
        # Đảm bảo không cuộn lố giới hạn
        max_scroll = self.horizontalScrollBar().maximum()
        target_scroll = max(0, min(target_scroll, max_scroll))
        
        self.horizontalScrollBar().setValue(target_scroll)
        self._internal_scroll = False

    def mousePressEvent(self, event):
        """User click vào Timeline -> Chuyển tọa độ thành Time (ms) và phát tín hiệu Seek"""
        # Lấy tọa độ click tương đối với mặt cuộn bên trong
        click_x = event.pos().x() + self.horizontalScrollBar().value()
        target_ms = int((click_x / self.pixels_per_second) * 1000.0)
        target_ms = max(0, min(target_ms, self.duration_ms))
        self.seek_requested.emit(target_ms)
        super().mousePressEvent(event)
        
    def clear(self):
        """Xóa trắng Timeline khi không có Video"""
        self.duration_ms = 0
        self.container.ruler.set_data(0)
        self.container.track.set_data([], 0)
        self.container.waveform.set_data(None, 0)
        self.container.playhead.set_position(0)
        self.container.adjustSize()