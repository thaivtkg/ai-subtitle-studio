import bisect
import os

from PySide6.QtCore import QObject, Signal


class SubtitleController(QObject):
    # Phát tín hiệu mang theo (STT, Thời_gian_bắt_đầu, Nội_dung)
    subtitle_changed = Signal(int, int, str)
    subtitle_cleared = Signal()

    def __init__(self):
        super().__init__()
        # Cấu trúc list: [(start_ms, end_ms, stt, text), ...]
        self.subtitles = []
        self.start_times = []
        self.current_stt = None
        self.current_idx = -1
        self.last_ms = 0
        self.is_enabled = True  # Trạng thái của Checkbox "Show Subtitle"
        

    def load_srt(self, srt_path):
        self.subtitles.clear()
        self.start_times.clear() # Clear cache
        self.current_idx = -1
        self.subtitle_cleared.emit()

        if not srt_path:
            return

        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read().replace('\r\n', '\n')

            blocks = content.strip().split('\n\n')
            for block in blocks:
                lines = block.split('\n')
                if len(lines) >= 3:
                    stt = int(lines[0].strip('\ufeff').strip()) 
                    times = lines[1].split(' --> ')
                    start_ms = self.time_str_to_ms(times[0])
                    end_ms = self.time_str_to_ms(times[1])
                    text = '\n'.join(lines[2:])
                    self.subtitles.append((start_ms, end_ms, text, stt))

            self.subtitles.sort(key=lambda x: x[0])
            # Tính toán mảng start_times DUY NHẤT 1 LẦN ở đây (O(n))
            self.start_times = [s[0] for s in self.subtitles]

        except Exception as e:
            print(f"Error loading SRT: {e}")

    def sync_position(self, ms):
        self.last_ms = ms

        if not self.subtitles or not self.start_times:
            return

        # Tìm kiếm O(log n) cực nhẹ
        idx = bisect.bisect_right(self.start_times, ms) - 1

        if idx >= 0:
            start_ms, end_ms, text, stt = self.subtitles[idx]
            
            # Sửa boundary thành [start, end) để tránh overlap chính xác tại milisecond chuyển giao
            if start_ms <= ms < end_ms:
                if self.current_idx != idx:
                    self.current_idx = idx
                    display_text = text if self.is_enabled else ""
                    self.subtitle_changed.emit(stt, start_ms, display_text)
            else:
                if self.current_idx != -1:
                    self.current_idx = -1
                    self.subtitle_cleared.emit()
        else:
            if self.current_idx != -1:
                self.current_idx = -1
                self.subtitle_cleared.emit()

    def toggle_preview(self, state):
        self.is_enabled = state
        self.current_idx = -1
        self.sync_position(self.last_ms)

    def time_str_to_ms(self, time_str):
        try:
            time_str = time_str.strip()
            parts = time_str.replace(',', ':').split(':')
            if len(parts) == 4:
                h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                return (h * 3600 + m * 60 + s) * 1000 + ms
        except:
            return 0

    def update_live_data(self, parsed_data):
        """ Nhận dữ liệu đã sửa từ Editor và ép Overlay render lại ngay lập tức """
        self.subtitles = parsed_data

        self.subtitles = sorted(parsed_data, key=lambda x: x[0])
        
        # [Safety] Kiểm tra danh sách rỗng trước khi nội suy start_times
        if self.subtitles:
            self.start_times = [s[0] for s in self.subtitles]
        else:
            self.start_times = []
            
        # Ép Controller quên trạng thái cũ để bắt buộc vẽ lại khung hình hiện tại
        self.current_idx = -1 
        self.sync_position(self.last_ms)