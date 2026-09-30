from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget
from core.timeline.gaps import find_timeline_gaps
from core.subtitle_generation.generation_range import (
    GenerationRange,
    GenerationRangeValidation,
    GenerationRangeStatus,
    validate_generation_range,
)
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
        self.start_range_edit = QLineEdit()
        self.start_range_edit.setPlaceholderText("HH:MM:SS,mmm")
        self.start_range_edit.setMaximumWidth(125)
        self.end_range_edit = QLineEdit()
        self.end_range_edit.setPlaceholderText("HH:MM:SS,mmm")
        self.end_range_edit.setMaximumWidth(125)
        self.range_duration = QLabel("--")
        self.range_validation = QLabel()
        self.range_validation.setWordWrap(True)
        self.generate_gap_button = QPushButton("Generate")
        self.generate_gap_button.setEnabled(False)
        self.play_segment_button = QPushButton("Play Segment")
        self.play_segment_button.setEnabled(False)
        self.play_segment_button.hide()
        gap_layout.addWidget(QLabel("Start"))
        gap_layout.addWidget(self.start_range_edit)
        gap_layout.addWidget(QLabel("End"))
        gap_layout.addWidget(self.end_range_edit)
        gap_layout.addWidget(QLabel("Duration"))
        gap_layout.addWidget(self.range_duration)
        gap_layout.addWidget(self.range_validation, stretch=1)
        gap_layout.addWidget(self.generate_gap_button)
        gap_layout.addWidget(self.play_segment_button)
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
    range_generation_requested = Signal(int, int)
    generation_range_selected = Signal()
    play_segment_requested = Signal()
    workflow_reset = Signal()
    timing_edit_started = Signal()

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
        self.generation_range = None
        self.range_validation = None
        self._generation_busy = False
        self._minimum_height_before_gap = None
        self.pixels_per_second = 100

        # --- CƠ CHẾ AUTO-SCROLL ---
        self.auto_scroll_enabled = True
        self._internal_scroll = False # Phân biệt cuộn do Code hay do User
        self.horizontalScrollBar().valueChanged.connect(self._on_user_scroll)
        self.container.track.gap_clicked.connect(self.select_gap)
        self.container.track.segment_clicked.connect(lambda *_: self.clear_gap_selection())
        self.container.start_range_edit.editingFinished.connect(self._on_manual_range_changed)
        self.container.end_range_edit.editingFinished.connect(self._on_manual_range_changed)
        self.container.generate_gap_button.clicked.connect(self._emit_range_generation)
        self.container.play_segment_button.clicked.connect(self.play_segment_requested.emit)

    @property
    def focused_segment(self):
        track = self.container.track
        if self.generation_range is not None or len(track.selected_ids) != 1:
            return None
        segment = next((s for s in track.segments if s.segment_id in track.selected_ids), None)
        if segment and 0 <= segment.start_ms < segment.end_ms <= self.duration_ms:
            return segment
        return None

    def refresh_segment_focus(self):
        segment = self.focused_segment
        focused = segment is not None
        self.container.start_range_edit.setReadOnly(focused)
        self.container.end_range_edit.setReadOnly(focused)
        self.container.play_segment_button.setVisible(focused)
        self.container.play_segment_button.setEnabled(focused)
        self.container.generate_gap_button.setVisible(not focused)
        if segment:
            self._show_range_row()
            self.container.start_range_edit.setText(self._format_ms(segment.start_ms))
            self.container.end_range_edit.setText(self._format_ms(segment.end_ms))
            self.container.range_duration.setText(self._format_ms(segment.end_ms - segment.start_ms))
            self.container.range_validation.setText("Kéo mép trái/phải để chỉnh thời gian.")
            self.container.waveform.set_selected_range(segment.start_ms, segment.end_ms)

    @staticmethod
    def _format_ms(value):
        seconds, milliseconds = divmod(value, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def select_gap(self, gap):
        if gap not in self.container.track.gaps:
            return
        self.clear_gap_selection()
        self.gap_selected.emit(gap)
        self.selected_gap = gap
        self.container.track.selected_gap = gap
        self.container.track.update()
        self._show_range_row()
        self._apply_generation_range(gap.start_ms, gap.end_ms, update_fields=True)

    def _show_range_row(self):
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
        self.workflow_reset.emit()
        self.container.waveform.clear_selected_range()
        self.selected_gap = None
        self.generation_range = None
        self.range_validation = None
        self.container.track.selected_gap = None
        self.container.track.update()
        self.container.start_range_edit.clear()
        self.container.end_range_edit.clear()
        self.container.range_duration.setText("--")
        self.container.range_validation.clear()
        self.container.generate_gap_button.setEnabled(False)
        self.container.generate_gap_button.show()
        self.container.play_segment_button.hide()
        self.container.play_segment_button.setEnabled(False)
        self.container.start_range_edit.setReadOnly(False)
        self.container.end_range_edit.setReadOnly(False)
        if self.duration_ms > 0:
            self._show_range_row()
        else:
            self.container.gap_row.hide()
        if self._minimum_height_before_gap is not None and self.duration_ms <= 0:
            self.setMinimumHeight(self._minimum_height_before_gap)
            self._minimum_height_before_gap = None

    def set_generation_range(self, start_ms, end_ms, *, update_fields=True):
        """Set the single transient range; waveform is only its visual projection."""
        self.clear_gap_selection()
        self.generation_range_selected.emit()
        self.container.track.set_selection(set())
        self.selected_gap = None
        self.container.track.selected_gap = None
        self.container.track.update()
        self._show_range_row()
        self._apply_generation_range(start_ms, end_ms, update_fields)

    def _apply_generation_range(self, start_ms, end_ms, update_fields):
        try:
            start_ms, end_ms = int(start_ms), int(end_ms)
        except (TypeError, ValueError, OverflowError):
            self.generation_range = None
            self.container.waveform.clear_selected_range()
            self._refresh_range_validation()
            return

        self.generation_range = GenerationRange(start_ms, end_ms)
        if update_fields:
            self.container.start_range_edit.setText(self._format_ms(start_ms))
            self.container.end_range_edit.setText(self._format_ms(end_ms))
        if 0 <= start_ms < end_ms <= self.duration_ms:
            self.container.waveform.set_selected_range(start_ms, end_ms)
        else:
            self.container.waveform.clear_selected_range()
        self._refresh_range_validation()

    def _on_manual_range_changed(self):
        from core.subtitle_generation.generation_range import parse_timecode_ms

        start_text = self.container.start_range_edit.text()
        end_text = self.container.end_range_edit.text()
        self.clear_gap_selection()
        self.generation_range_selected.emit()
        self.container.track.set_selection(set())
        self.container.start_range_edit.setText(start_text)
        self.container.end_range_edit.setText(end_text)
        self.selected_gap = None
        self.container.track.selected_gap = None
        self.container.track.update()
        self._show_range_row()
        try:
            start_ms = parse_timecode_ms(self.container.start_range_edit.text())
            end_ms = parse_timecode_ms(self.container.end_range_edit.text())
        except ValueError:
            self.generation_range = None
            self.container.waveform.clear_selected_range()
            self._refresh_range_validation(GenerationRangeStatus.INVALID_FORMAT)
            return
        self._apply_generation_range(start_ms, end_ms, update_fields=False)

    def _refresh_range_validation(self, forced_status=None):
        if self.focused_segment is not None:
            self.refresh_segment_focus()
            self.container.generate_gap_button.setEnabled(False)
            return
        if forced_status is not None:
            result = GenerationRangeValidation(forced_status)
        elif self.generation_range is None:
            result = validate_generation_range(None, None, self.duration_ms)
        else:
            result = validate_generation_range(
                self.generation_range.start_ms,
                self.generation_range.end_ms,
                self.duration_ms,
                self.container.track.segments,
            )
        self.range_validation = result
        self.container.range_duration.setText(
            self._format_ms(self.generation_range.duration_ms)
            if self.generation_range and self.generation_range.end_ms > self.generation_range.start_ms
            else "--"
        )
        messages = {
            GenerationRangeStatus.VALID: "",
            GenerationRangeStatus.NO_MEDIA: "Chưa có media hợp lệ.",
            GenerationRangeStatus.INVALID_FORMAT: "Định dạng thời gian không hợp lệ.",
            GenerationRangeStatus.OUT_OF_BOUNDS: "Thời gian vượt quá độ dài media.",
            GenerationRangeStatus.EMPTY_OR_REVERSED: "Khoảng thời gian không hợp lệ.",
            GenerationRangeStatus.OVERLAPS_SUBTITLE: "Khoảng đã chọn đang chứa phụ đề.",
        }
        self.container.range_validation.setText(messages[result.status])
        self.container.generate_gap_button.setEnabled(
            result.status == GenerationRangeStatus.VALID and not self._generation_busy
        )

    def _emit_range_generation(self):
        if self.generation_range and self.range_validation.status == GenerationRangeStatus.VALID:
            self.range_generation_requested.emit(
                self.generation_range.start_ms, self.generation_range.end_ms
            )

    def set_generation_busy(self, busy):
        self._generation_busy = bool(busy)
        self._refresh_range_validation()

    def set_range_segments(self, segments):
        """Refresh overlap validity after editor subtitle state changes."""
        if self.generation_range is not None:
            self.container.track.segments = segments
            self._refresh_range_validation()

    def _on_user_scroll(self, value):
        """Tự động tắt Auto-scroll nếu người dùng chủ động kéo thanh cuộn"""
        if not self._internal_scroll:
            self.auto_scroll_enabled = False

    def reset_auto_scroll(self):
        """Gọi hàm này khi người dùng bấm nút Play video để bật lại cuộn tự động"""
        self.auto_scroll_enabled = True

    def load_project_data(self, duration_ms: int, segments: list, peaks_normalized=None):
        self.clear_gap_selection()
        self.container.track.set_selection(set())
        self.duration_ms = duration_ms
        self.container.ruler.set_data(duration_ms)
        self.container.track.set_data(segments, duration_ms)
        self.container.track.set_gaps(find_timeline_gaps(duration_ms, segments))
        if peaks_normalized is not None:
            self.container.waveform.set_data(peaks_normalized, duration_ms)
        if duration_ms > 0:
            self._show_range_row()
        else:
            self.container.gap_row.hide()
            if self._minimum_height_before_gap is not None:
                self.setMinimumHeight(self._minimum_height_before_gap)
                self._minimum_height_before_gap = None

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
        self.container.track.set_selection(set())
        self.duration_ms = 0
        self.container.ruler.set_data(0)
        self.container.track.set_data([], 0)
        self.container.track.set_gaps([])
        self.container.waveform.set_data(None, 0)
        self.container.waveform.clear_selected_range()
        self.container.playhead.set_position(0)
        self.container.adjustSize()
