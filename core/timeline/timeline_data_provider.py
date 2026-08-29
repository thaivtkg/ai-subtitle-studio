import uuid
import copy

class TimelineSegmentWrapper:
    """Đồng bộ hoàn hảo 2 chiều giữa Integer (Backend) và String (UI Table)"""
    def __init__(self, raw_dict, provider):
        self._raw = raw_dict
        self.provider = provider
        
        if 'id' not in self._raw:
            self._raw['id'] = str(uuid.uuid4())

        # Cứu hộ định dạng: Nếu file JSON lưu bằng start_ms (số), ta tự tạo bản chuỗi (start) cho UI
        if 'start_ms' in self._raw and 'start' not in self._raw:
            self._raw['start'] = self.provider._ms_to_time_str(self._raw['start_ms'])
        if 'end_ms' in self._raw and 'end' not in self._raw:
            self._raw['end'] = self.provider._ms_to_time_str(self._raw['end_ms'])

        # Ngược lại: Nếu UI sinh ra chuỗi (start) nhưng thiếu số (start_ms)
        if 'start' in self._raw and 'start_ms' not in self._raw:
            self._raw['start_ms'] = self.provider._time_str_to_ms(self._raw['start'])
        if 'end' in self._raw and 'end_ms' not in self._raw:
            self._raw['end_ms'] = self.provider._time_str_to_ms(self._raw['end'])

    @property
    def segment_id(self): return self._raw.get('id')
    
    @property
    def start_ms(self): return self._raw.get('start_ms', 0)
    
    @start_ms.setter
    def start_ms(self, val):
        val = int(max(0, val))
        self._raw['start_ms'] = val # Cập nhật cho Backend
        self._raw['start'] = self.provider._ms_to_time_str(val) # Cập nhật cho UI

    @property
    def end_ms(self): return self._raw.get('end_ms', 0)
    
    @end_ms.setter
    def end_ms(self, val):
        val = int(max(0, val))
        self._raw['end_ms'] = val
        self._raw['end'] = self.provider._ms_to_time_str(val)

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
        
        for seg_dict in editor_segments:
            wrapper = TimelineSegmentWrapper(seg_dict, self)
            self._segments.append(wrapper)
            
        self._duration_ms = duration_ms

    def sync_back_to_editor(self):
        if self._editor_dict_ref is None: 
            return
            
        self._segments.sort(key=lambda s: s.start_ms)
        self._editor_dict_ref.clear()
        
        for i, wrapper in enumerate(self._segments):
            raw = wrapper.get_raw_dict()
            raw['stt'] = str(i + 1)
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

    def create_split_segment(self, original_segment_id: str, split_ms: int):
        orig = self.get_segment(original_segment_id)
        if not orig: return None
        
        new_raw = copy.deepcopy(orig.get_raw_dict())
        new_raw['id'] = str(uuid.uuid4())
        new_raw['text'] = "" 
        
        new_wrapper = TimelineSegmentWrapper(new_raw, self)
        new_wrapper.start_ms = split_ms
        new_wrapper.end_ms = orig.end_ms
        
        return new_wrapper

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