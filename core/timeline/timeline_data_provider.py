import uuid

class TimelineSegmentWrapper:
    """[Fix Blocker 3 & 4] Lớp bọc an toàn, vừa cung cấp API Object cho Timeline, vừa bảo toàn Dictionary gốc (Metadata, Status)"""
    def __init__(self, raw_dict, provider):
        self._raw = raw_dict
        self.provider = provider
        
        # Bổ sung ID duy nhất nếu chưa có
        if 'id' not in self._raw:
            self._raw['id'] = str(uuid.uuid4())

    @property
    def segment_id(self): return self._raw.get('id')
    
    @property
    def start_ms(self): return self.provider._time_str_to_ms(self._raw.get('start', '00:00:00,000'))
    @start_ms.setter
    def start_ms(self, val): self._raw['start'] = self.provider._ms_to_time_str(val)

    @property
    def end_ms(self): return self.provider._time_str_to_ms(self._raw.get('end', '00:00:00,000'))
    @end_ms.setter
    def end_ms(self, val): self._raw['end'] = self.provider._ms_to_time_str(val)

    @property
    def text(self): return self._raw.get('text', '')
    @text.setter
    def text(self, val): self._raw['text'] = val

    @property
    def status(self): return self._raw.get('status', 'draft')
    @status.setter
    def status(self, val): self._raw['status'] = val

    def get_raw_dict(self):
        return self._raw


class TimelineDataProvider:
    def __init__(self):
        self._segments = []
        self._duration_ms = 0
        self._editor_dict_ref = None

    def load_runtime_data(self, editor_segments: list, duration_ms: int):
        self._editor_dict_ref = editor_segments
        self._segments = []
        
        # Bọc trực tiếp list gốc, không copy sang object mới
        for seg_dict in editor_segments:
            wrapper = TimelineSegmentWrapper(seg_dict, self)
            self._segments.append(wrapper)
            
        self._duration_ms = duration_ms

    def sync_back_to_editor(self):
        """[Fix Blocker 4] Chỉ cần sắp xếp lại mảng gốc, KHÔNG ghi đè làm mất Metadata hay Status"""
        if self._editor_dict_ref is None: 
            return
            
        # Sắp xếp lại _segments theo thời gian
        self._segments.sort(key=lambda s: s.start_ms)
        
        # Cập nhật số thứ tự (STT) cho đúng
        self._editor_dict_ref.clear()
        for i, wrapper in enumerate(self._segments):
            raw = wrapper.get_raw_dict()
            raw['stt'] = str(i + 1)
            # Khởi tạo mặc định nếu trạng thái bị trống
            if 'status' not in raw:
                raw['status'] = 'draft'
            self._editor_dict_ref.append(raw)

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