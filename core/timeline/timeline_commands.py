import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from core.timeline.timeline_policies import TextMergePolicy

@dataclass
class SegmentSnapshot:
    """Đóng gói trạng thái bất biến (immutable)"""
    segment_id: str
    start_ms: int
    end_ms: int
    text: str

@dataclass
class StateChangeSnapshot:
    before_states: List[SegmentSnapshot]
    after_states: List[SegmentSnapshot]

class TimelineEditCommand(ABC):
    def __init__(self, project_service, data_provider):
        self.project_service = project_service
        self.data_provider = data_provider
        self.snapshot = None

    @abstractmethod
    def can_execute(self, current_state: Any) -> bool:
        pass

    @abstractmethod
    def execute(self, context: Any) -> StateChangeSnapshot:
        pass

    def _increment_revision(self):
        project = self.project_service.current_project
        if project and project.state.active_artifact_id:
            artifact = self.project_service.artifact_store.get(project.state.active_artifact_id)
            if artifact:
                artifact.revision += 1

    def undo(self) -> None:
        if self.snapshot and self.snapshot.before_states:
            for snap in self.snapshot.before_states:
                seg = self.data_provider.get_segment(snap.segment_id)
                if seg:
                    seg.start_ms = snap.start_ms
                    seg.end_ms = snap.end_ms
                    seg.text = snap.text
        self._increment_revision()
        self.project_service.mark_dirty()

    def redo(self) -> None:
        if self.snapshot and self.snapshot.after_states:
            for snap in self.snapshot.after_states:
                seg = self.data_provider.get_segment(snap.segment_id)
                if seg:
                    seg.start_ms = snap.start_ms
                    seg.end_ms = snap.end_ms
                    seg.text = snap.text
        self._increment_revision()
        self.project_service.mark_dirty()   

class MoveSegmentCommand(TimelineEditCommand):
    def __init__(self, project_service, data_provider, segment_id: str, delta_ms: int):
        super().__init__(project_service, data_provider)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def can_execute(self, current_state) -> bool:
        seg = self.data_provider.get_segment(self.segment_id)
        if not seg: return False
        if seg.start_ms + self.delta_ms < 0: return False
        return True

    def execute(self, context=None) -> StateChangeSnapshot:
        seg = self.data_provider.get_segment(self.segment_id)
        before_snap = SegmentSnapshot(seg.segment_id, seg.start_ms, seg.end_ms, seg.text)
        
        seg.start_ms += self.delta_ms
        seg.end_ms += self.delta_ms
        
        after_snap = SegmentSnapshot(seg.segment_id, seg.start_ms, seg.end_ms, seg.text)
        self.snapshot = StateChangeSnapshot(before_states=[before_snap], after_states=[after_snap])
        
        self._increment_revision()
        self.project_service.mark_dirty()
        return self.snapshot

class ResizeStartCommand(TimelineEditCommand):
    MIN_DURATION_MS = 100

    def __init__(self, project_service, data_provider, segment_id: str, delta_ms: int):
        super().__init__(project_service, data_provider)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def can_execute(self, current_state) -> bool:
        seg = self.data_provider.get_segment(self.segment_id)
        if not seg: return False
        new_start = seg.start_ms + self.delta_ms
        if new_start < 0 or new_start > seg.end_ms - self.MIN_DURATION_MS: return False
        return True

    def execute(self, context=None) -> StateChangeSnapshot:
        seg = self.data_provider.get_segment(self.segment_id)
        before_snap = SegmentSnapshot(seg.segment_id, seg.start_ms, seg.end_ms, seg.text)
        
        seg.start_ms += self.delta_ms
        
        after_snap = SegmentSnapshot(seg.segment_id, seg.start_ms, seg.end_ms, seg.text)
        self.snapshot = StateChangeSnapshot(before_states=[before_snap], after_states=[after_snap])
        
        self._increment_revision()
        self.project_service.mark_dirty()
        return self.snapshot

class ResizeEndCommand(TimelineEditCommand):
    MIN_DURATION_MS = 100

    def __init__(self, project_service, data_provider, segment_id: str, delta_ms: int):
        super().__init__(project_service, data_provider)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def can_execute(self, current_state) -> bool:
        seg = self.data_provider.get_segment(self.segment_id)
        if not seg: return False
        new_end = seg.end_ms + self.delta_ms
        if new_end < seg.start_ms + self.MIN_DURATION_MS: return False
        return True

    def execute(self, context=None) -> StateChangeSnapshot:
        seg = self.data_provider.get_segment(self.segment_id)
        before_snap = SegmentSnapshot(seg.segment_id, seg.start_ms, seg.end_ms, seg.text)
        
        seg.end_ms += self.delta_ms
        
        after_snap = SegmentSnapshot(seg.segment_id, seg.start_ms, seg.end_ms, seg.text)
        self.snapshot = StateChangeSnapshot(before_states=[before_snap], after_states=[after_snap])
        
        self._increment_revision()
        self.project_service.mark_dirty()
        return self.snapshot

class SplitSegmentCommand(TimelineEditCommand):
    def __init__(self, project_service, data_provider, segment_id: str, split_ms: int):
        super().__init__(project_service, data_provider)
        self.segment_id = segment_id
        self.split_ms = split_ms
        self.new_segment = None
        self.original_end_ms = 0

    def can_execute(self, current_state) -> bool:
        seg = self.data_provider.get_segment(self.segment_id)
        if not seg: return False
        if self.split_ms <= seg.start_ms + 50 or self.split_ms >= seg.end_ms - 50: return False
        return True

    def execute(self, context=None):
        seg = self.data_provider.get_segment(self.segment_id)
        self.original_end_ms = seg.end_ms
        seg.end_ms = self.split_ms
        
        # Tạo object phụ đề mới với ID xịn thay vì dùng time()
        from core.subtitle_model import SubtitleSegment 
        new_id = str(uuid.uuid4())
        self.new_segment = SubtitleSegment(segment_id=new_id, start_ms=self.split_ms, end_ms=self.original_end_ms, text="")
        
        self.data_provider.add_segment(self.new_segment)
        self._increment_revision()
        self.project_service.mark_dirty()
        return None

    def undo(self) -> None:
        seg = self.data_provider.get_segment(self.segment_id)
        seg.end_ms = self.original_end_ms
        self.data_provider.remove_segment(self.new_segment)
        self._increment_revision()
        self.project_service.mark_dirty()

    def redo(self) -> None:
        seg = self.data_provider.get_segment(self.segment_id)
        seg.end_ms = self.split_ms
        self.data_provider.add_segment(self.new_segment)
        self._increment_revision()
        self.project_service.mark_dirty()

class MergeSegmentsCommand(TimelineEditCommand):
    def __init__(self, project_service, data_provider, segment_ids: set):
        super().__init__(project_service, data_provider)
        self.segment_ids = list(segment_ids)
        self.deleted_segments = []
        self.target_segment = None
        self.original_end_ms = 0
        self.original_text = ""

    def can_execute(self, current_state) -> bool:
        if len(self.segment_ids) < 2: return False
        
        # Validation [Fix 8.7 & 8.8]: Chặn gộp các Segment không liền kề
        segments = self.data_provider.get_all_segments()
        to_merge = sorted([s for s in segments if s.segment_id in self.segment_ids], key=lambda s: s.start_ms)
        
        # Nếu danh sách trả ra không đủ số lượng đã chọn (do lỗi ID ảo)
        if len(to_merge) != len(self.segment_ids): return False

        # Quét kiểm tra khoảng cách giữa các segment. Nếu cách xa hơn 5000ms (5 giây) -> Cấm gộp.
        for i in range(len(to_merge) - 1):
            gap = to_merge[i+1].start_ms - to_merge[i].end_ms
            if gap > 5000 or gap < -500: # Cấm khoảng trống lớn hơn 5s hoặc bị đè lên nhau > 500ms
                return False
                
        return True 

    def execute(self, context=None):
        segments = self.data_provider.get_all_segments()
        to_merge = sorted([s for s in segments if s.segment_id in self.segment_ids], key=lambda s: s.start_ms)
        
        if not to_merge: return None
        
        self.target_segment = to_merge[0]
        self.original_end_ms = self.target_segment.end_ms
        self.original_text = self.target_segment.text
        self.deleted_segments = to_merge[1:]
        
        combined_text = TextMergePolicy.execute([s.text for s in to_merge])
        self.target_segment.end_ms = to_merge[-1].end_ms
        self.target_segment.text = combined_text
        
        for s in self.deleted_segments:
            self.data_provider.remove_segment(s)
            
        self._increment_revision()
        self.project_service.mark_dirty()
        return None

    def undo(self) -> None:
        self.target_segment.end_ms = self.original_end_ms
        self.target_segment.text = self.original_text
        for s in self.deleted_segments:
            self.data_provider.add_segment(s)
        self._increment_revision()
        self.project_service.mark_dirty()

    def redo(self) -> None:
        self.execute()

class DeleteSegmentCommand(TimelineEditCommand):
    def __init__(self, project_service, data_provider, segment_ids: set):
        super().__init__(project_service, data_provider)
        self.segment_ids = segment_ids
        self.deleted_segments = []

    def can_execute(self, current_state) -> bool:
        return len(self.segment_ids) > 0

    def execute(self, context=None):
        segments = self.data_provider.get_all_segments()
        self.deleted_segments = [s for s in segments if s.segment_id in self.segment_ids]
        
        for s in self.deleted_segments:
            self.data_provider.remove_segment(s)
            
        self._increment_revision()
        self.project_service.mark_dirty()
        return None

    def undo(self) -> None:
        for s in self.deleted_segments:
            self.data_provider.add_segment(s)
        self._increment_revision()
        self.project_service.mark_dirty()

    def redo(self) -> None:
        self.execute()