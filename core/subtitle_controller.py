import bisect
import os
from PySide6.QtCore import QObject, Signal


class SubtitleController(QObject):
    # Phát tín hiệu mang theo (STT, Thời_gian_bắt_đầu, Nội_dung)
    subtitle_changed = Signal(str, int, str)
    subtitle_cleared = Signal()

    def __init__(self):
        super().__init__()
        # Cấu trúc list: [(start_ms, end_ms, stt, text), ...]
        self.subtitles = []
        self.current_stt = None
        self.is_enabled = True  # Trạng thái của Checkbox "Show Subtitle"

    def load_srt(self, srt_path):
        """ Đọc file SRT và nạp vào bộ nhớ để chuẩn bị Binary Search """
        self.subtitles.clear()
        self.current_stt = None
        self.subtitle_cleared.emit()

        if not srt_path or not os.path.exists(srt_path):
            return

        with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        blocks = content.strip().split("\n\n")
        for block in blocks:
            lines = block.split("\n")
            if len(lines) >= 3:
                stt = lines[0]
                time_range = lines[1].split(" --> ")
                if len(time_range) == 2:
                    start_ms = self._time_str_to_ms(time_range[0])
                    end_ms = self._time_str_to_ms(time_range[1])
                    # Nối các dòng text lại bằng \n, giữ nguyên định dạng nhiều dòng
                    text = "\n".join(lines[2:])
                    self.subtitles.append((start_ms, end_ms, stt, text))

        # Đảm bảo mảng luôn được sắp xếp theo thời gian bắt đầu để Binary Search hoạt động
        self.subtitles.sort(key=lambda x: x[0])

    def sync_position(self, ms):
        """ Hàm này sẽ được gọi mỗi khi Video Player bắn sự kiện positionChanged """
        if not self.is_enabled or not self.subtitles:
            if self.current_stt is not None:
                self.current_stt = None
                self.subtitle_cleared.emit()
            return

        # 1. Trích xuất mảng thời gian bắt đầu
        starts = [s[0] for s in self.subtitles]

        # 2. Binary Search: Tìm vị trí index có start_ms <= ms
        idx = bisect.bisect_right(starts, ms) - 1

        if idx >= 0:
            start_ms, end_ms, stt, text = self.subtitles[idx]
            # 3. Kiểm tra xem ms hiện tại có nằm trong khoảng [start, end] không
            if start_ms <= ms <= end_ms:
                # Nếu có và khác dòng đang hiển thị -> Phát tín hiệu cập nhật
                if self.current_stt != stt:
                    self.current_stt = stt
                    self.subtitle_changed.emit(stt, start_ms, text)
                return

        # 4. Nếu ms rơi vào khoảng trống (giữa 2 câu) -> Xóa màn hình
        if self.current_stt is not None:
            self.current_stt = None
            self.subtitle_cleared.emit()

    def toggle_preview(self, state):
        self.is_enabled = state
        if not state:
            self.current_stt = None
            self.subtitle_cleared.emit()

    def _time_str_to_ms(self, time_str):
        try:
            parts = time_str.strip().replace(',', ':').split(':')
            h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            return (h * 3600 + m * 60 + s) * 1000 + ms
        except Exception:
            return 0