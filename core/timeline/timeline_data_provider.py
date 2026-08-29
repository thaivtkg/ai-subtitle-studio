import uuid
from dataclasses import dataclass

# Định nghĩa Object chuẩn thay thế để tránh lỗi import chéo từ các module cũ
@dataclass
class SubtitleSegment:
    segment_id: str
    start_ms: int
    end_ms: int
    text: str

class TimelineDataProvider:
    """[Fix 8.5] Bộ chuyển đổi hai chiều (Two-way Adapter) giữa RAM Timeline và RAM Editor"""
    
    def __init__(self):
        self._segments = []
        self._duration_ms = 0
        self._editor_dict_ref = None # Lưu tham chiếu danh sách gốc của SubEditor

    def load_runtime_data(self, editor_segments: list, duration_ms: int):
        self._editor_dict_ref = editor_segments
        self._segments = []
        
        for seg_dict in editor_segments:
            # 1. Chuyển đổi định dạng giờ của Editor (HH:MM:SS,MMM) sang Mili-giây (int)
            start_ms = self._time_str_to_ms(seg_dict.get('start', '00:00:00,000'))
            end_ms = self._time_str_to_ms(seg_dict.get('end', '00:00:00,000'))
            
            # 2. Tạo hoặc ánh xạ UUID
            seg_id = str(seg_dict.get('id', uuid.uuid4()))
            seg_dict['id'] = seg_id # Gắn ngược ID lại vào dict để tiện tra cứu
            
            text = seg_dict.get('text', '')
            
            # 3. Nạp vào bộ nhớ của Timeline
            self._segments.append(SubtitleSegment(
                segment_id=seg_id, 
                start_ms=start_ms, 
                end_ms=end_ms, 
                text=text
            ))
            
        self._duration_ms = duration_ms

    def sync_back_to_editor(self):
        """[Fix 8.6] Bơm dữ liệu ngược từ Timeline về Table Editor để lưu File (Persistence)"""
        if self._editor_dict_ref is None: 
            return
            
        self._editor_dict_ref.clear()
        
        # Sort lại timeline segments theo thứ tự thời gian trước khi nhồi ngược về Editor
        sorted_segs = sorted(self._segments, key=lambda s: s.start_ms)
        
        for i, seg in enumerate(sorted_segs):
            self._editor_dict_ref.append({
                'stt': str(i + 1),
                'id': seg.segment_id,
                'start': self._ms_to_time_str(seg.start_ms),
                'end': self._ms_to_time_str(seg.end_ms),
                'text': seg.text,
                'status': 'draft' # Đánh dấu là draft để hệ thống biết đã qua chỉnh sửa
            })

    # --- Các hàm cung cấp Data cho View ---
    def get_all_segments(self) -> list:
        return self._segments

    def get_segment(self, segment_id: str):
        for seg in self._segments:
            if seg.segment_id == segment_id:
                return seg
        return None

    def get_duration_ms(self) -> int:
        return self._duration_ms

    def add_segment(self, segment):
        self._segments.append(segment)

    def remove_segment(self, segment):
        if segment in self._segments:
            self._segments.remove(segment)

    # --- Utility: Chuyển đổi qua lại giữa Chuỗi (SRT) và Mili-giây ---
    def _time_str_to_ms(self, time_str: str) -> int:
        try:
            h_m_s, ms = time_str.split(',')
            h, m, s = h_m_s.split(':')
            return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
        except Exception:
            return 0

    def _ms_to_time_str(self, ms: int) -> str:
        ms = max(0, ms)
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        msec = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{msec:03d}"