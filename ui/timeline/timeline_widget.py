from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from core.timeline.gaps import find_timeline_gaps
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
        self.gap_row = QWidget()
        gap_layout = QHBoxLayout(self.gap_row)
        gap_layout.setContentsMargins(8, 2, 8, 2)
        self.gap_details = QLabel()
        self.generate_gap_button = QPushButton("Generate")
        self.generate_gap_button.setEnabled(False)
        self.generate_gap_button.setToolTip("Generate sẽ khả dụng sau khi phạm vi tạo phụ đề được hỗ trợ.")
        gap_layout.addWidget(self.gap_details)
        gap_layout.addWidget(self.generate_gap_button)
        self.layout.addWidget(self.gap_row)
        self.gap_row.hide()
        self.layout.addStretch()

        self.playhead = PlayheadOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.playhead.resize(self.width(), self.height())

class TimelineWidget(QScrollArea):
    seek_requested = Signal(int)
    gap_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {Theme.BORDER};
                background-color: {Theme.BG_APP};
            }}
            QScrollBar:horizontal {{
                background: {Theme.SURFACE_SOFT};
                height: 14px;
                margin: 2px 4px;
                border-radius: 7px;
            }}
            QScrollBar::handle:horizontal {{
                background: {Theme.CYAN};
                min-width: 72px;
                border: 3px solid {Theme.SURFACE_SOFT};
                border-radius: 7px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {Theme.TEXT_PRIMARY};
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: {Theme.SURFACE_SOFT};
            }}
        """)

        self.container = TimelineContainer()
        self.setWidget(self.container)

        self.duration_ms = 0
        self.selected_gap = None
        self._minimum_height_before_gap = None
        self.pixels_per_second = 100

        # --- CƠ CHẾ AUTO-SCROLL ---
        self.auto_scroll_enabled = True
        self._internal_scroll = False # Phân biệt cuộn do Code hay do User
        self.horizontalScrollBar().valueChanged.connect(self._on_user_scroll)
        self.container.track.gap_clicked.connect(self.select_gap)
        self.container.track.segment_clicked.connect(lambda *_: self.clear_gap_selection())

    @staticmethod
    def _format_ms(value):
        seconds, milliseconds = divmod(value, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def select_gap(self, gap):
        if gap not in self.container.track.gaps:
            return
        self.gap_selected.emit(gap)
        self.selected_gap = gap
        self.container.track.selected_gap = gap
        self.container.track.update()
        self.container.waveform.set_selected_range(gap.start_ms, gap.end_ms)
        self.container.gap_details.setText(
            f"Start {self._format_ms(gap.start_ms)}  ·  End {self._format_ms(gap.end_ms)}"
            f"  ·  Duration {self._format_ms(gap.duration_ms)}"
        )
        self.container.gap_row.show()
        if self._minimum_height_before_gap is None:
            self._minimum_height_before_gap = self.minimumHeight()
        required_height = (
            self.container.ruler.minimumHeight()
            + self.container.waveform.minimumHeight()
            + self.container.track.minimumHeight()
            + self.container.gap_row.sizeHint().height()
            + self.horizontalScrollBar().sizeHint().height()
            + 2 * self.frameWidth()
        )
        self.setMinimumHeight(max(self._minimum_height_before_gap, required_height))

    def clear_gap_selection(self):
        if self.selected_gap is not None:
            self.container.waveform.clear_selected_range()
        self.selected_gap = None
        self.container.track.selected_gap = None
        self.container.track.update()
        self.container.gap_row.hide()
        if self._minimum_height_before_gap is not None:
            self.setMinimumHeight(self._minimum_height_before_gap)
            self._minimum_height_before_gap = None

    def _on_user_scroll(self, value):
        """Tự động tắt Auto-scroll nếu người dùng chủ động kéo thanh cuộn"""
        if not self._internal_scroll:
            self.auto_scroll_enabled = False

    def reset_auto_scroll(self):
        """Gọi hàm này khi người dùng bấm nút Play video để bật lại cuộn tự động"""
        self.auto_scroll_enabled = True

    def load_project_data(self, duration_ms: int, segments: list, peaks_normalized=None):
        self.clear_gap_selection()
        self.duration_ms = duration_ms
        self.container.ruler.set_data(duration_ms)
        self.container.track.set_data(segments, duration_ms)
        self.container.track.set_gaps(find_timeline_gaps(duration_ms, segments))
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

    def center_on_time(self, time_ms: int):
        if self.duration_ms <= 0:
            return
        time_ms = max(0, min(int(time_ms), self.duration_ms))
        self._center_on_x(int((time_ms / 1000.0) * self.pixels_per_second))

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
        self.clear_gap_selection()
        self.duration_ms = 0
        self.container.ruler.set_data(0)
        self.container.track.set_data([], 0)
        self.container.track.set_gaps([])
        self.container.waveform.set_data(None, 0)
        self.container.waveform.clear_selected_range()
        self.container.playhead.set_position(0)
        self.container.adjustSize()
