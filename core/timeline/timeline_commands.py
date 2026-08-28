import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from core.timeline.timeline_policies import TextMergePolicy


@dataclass
class SegmentSnapshot:
    """Đóng gói trạng thái bất biến (immutable) của một Segment tại một thời điểm"""
    id: int
    start_ms: int
    end_ms: int
    text: str

@dataclass
class StateChangeSnapshot:
    """Lưu trữ trạng thái Trước và Sau của một nhóm Segment để Undo/Redo"""
    before_states: List[SegmentSnapshot]
    after_states: List[SegmentSnapshot]

class TimelineEditCommand(ABC):
    """Hợp đồng (Contract) bắt buộc cho mọi thao tác chỉnh sửa Timeline"""
    
    def __init__(self, project_service):
        self.project_service = project_service
        self.snapshot = None

    @abstractmethod
    def can_execute(self, current_state: Any) -> bool:
        """Validation logic: Kiểm tra tính hợp lệ (VD: độ dài tối thiểu, overlap) trước khi chạy"""
        pass

    @abstractmethod
    def execute(self, context: Any) -> StateChangeSnapshot:
        """Thực thi logic, tạo Snapshot và cập nhật trực tiếp vào SubtitleSegment"""
        pass

    @abstractmethod
    def undo(self) -> None:
        """Hoàn tác bằng cách sử dụng self.snapshot.before_states đè lại ArtifactStore"""
        pass
        
    @abstractmethod
    def redo(self) -> None:
        """Làm lại bằng cách sử dụng self.snapshot.after_states"""
        pass

class MoveSegmentCommand(TimelineEditCommand):
    """Lệnh di chuyển tịnh tiến một Segment trên Timeline"""
    
    def __init__(self, project_service, segment_id: int, delta_ms: int):
        super().__init__(project_service)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def can_execute(self, current_state) -> bool:
        seg = self.project_service.get_segment(self.segment_id)
        if not seg:
            return False
        # Không cho phép kéo Segment vượt quá mốc 00:00.000
        if seg.start_ms + self.delta_ms < 0:
            return False
        return True

    def execute(self, context=None) -> StateChangeSnapshot:
        seg = self.project_service.get_segment(self.segment_id)
        
        # 1. Bắt Snapshot Trạng thái cũ (Before)
        before_snap = SegmentSnapshot(seg.id, seg.start_ms, seg.end_ms, seg.text)
        
        # 2. Cập nhật dữ liệu thực tế
        seg.start_ms += self.delta_ms
        seg.end_ms += self.delta_ms
        
        # 3. Bắt Snapshot Trạng thái mới (After)
        after_snap = SegmentSnapshot(seg.id, seg.start_ms, seg.end_ms, seg.text)
        
        self.snapshot = StateChangeSnapshot(before_states=[before_snap], after_states=[after_snap])
        
        # 4. Đánh dấu Project thay đổi và tăng Revision
        self.project_service.mark_dirty()
        return self.snapshot

    def undo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        before = self.snapshot.before_states[0]
        seg.start_ms = before.start_ms
        seg.end_ms = before.end_ms
        self.project_service.mark_dirty()

    def redo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        after = self.snapshot.after_states[0]
        seg.start_ms = after.start_ms
        seg.end_ms = after.end_ms
        self.project_service.mark_dirty()

class ResizeStartCommand(TimelineEditCommand):
    """Lệnh thay đổi thời điểm bắt đầu (Kéo cạnh trái)"""
    MIN_DURATION_MS = 100

    def __init__(self, project_service, segment_id: int, delta_ms: int):
        super().__init__(project_service)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def can_execute(self, current_state) -> bool:
        seg = self.project_service.get_segment(self.segment_id)
        if not seg: return False
        
        new_start = seg.start_ms + self.delta_ms
        # Không vượt quá mốc 0 và phải giữ khoảng cách 100ms với end_ms
        if new_start < 0 or new_start > seg.end_ms - self.MIN_DURATION_MS:
            return False
        return True

    def execute(self, context=None) -> StateChangeSnapshot:
        seg = self.project_service.get_segment(self.segment_id)
        before_snap = SegmentSnapshot(seg.id, seg.start_ms, seg.end_ms, seg.text)
        
        seg.start_ms += self.delta_ms
        
        after_snap = SegmentSnapshot(seg.id, seg.start_ms, seg.end_ms, seg.text)
        self.snapshot = StateChangeSnapshot(before_states=[before_snap], after_states=[after_snap])
        
        self.project_service.mark_dirty()
        return self.snapshot

    def undo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        seg.start_ms = self.snapshot.before_states[0].start_ms
        self.project_service.mark_dirty()

    def redo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        seg.start_ms = self.snapshot.after_states[0].start_ms
        self.project_service.mark_dirty()


class ResizeEndCommand(TimelineEditCommand):
    """Lệnh thay đổi thời điểm kết thúc (Kéo cạnh phải)"""
    MIN_DURATION_MS = 100

    def __init__(self, project_service, segment_id: int, delta_ms: int):
        super().__init__(project_service)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def can_execute(self, current_state) -> bool:
        seg = self.project_service.get_segment(self.segment_id)
        if not seg: return False
        
        new_end = seg.end_ms + self.delta_ms
        # End_ms phải lớn hơn start_ms ít nhất 100ms
        if new_end < seg.start_ms + self.MIN_DURATION_MS:
            return False
        return True

    def execute(self, context=None) -> StateChangeSnapshot:
        seg = self.project_service.get_segment(self.segment_id)
        before_snap = SegmentSnapshot(seg.id, seg.start_ms, seg.end_ms, seg.text)
        
        seg.end_ms += self.delta_ms
        
        after_snap = SegmentSnapshot(seg.id, seg.start_ms, seg.end_ms, seg.text)
        self.snapshot = StateChangeSnapshot(before_states=[before_snap], after_states=[after_snap])
        
        self.project_service.mark_dirty()
        return self.snapshot

    def undo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        seg.end_ms = self.snapshot.before_states[0].end_ms
        self.project_service.mark_dirty()

    def redo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        seg.end_ms = self.snapshot.after_states[0].end_ms
        self.project_service.mark_dirty()

class SplitSegmentCommand(TimelineEditCommand):
    """Lệnh tách 1 Segment thành 2 tại vị trí Playhead"""
    
    def __init__(self, project_service, segment_id: int, split_ms: int):
        super().__init__(project_service)
        self.segment_id = segment_id
        self.split_ms = split_ms
        self.new_segment = None
        self.original_end_ms = 0

    def can_execute(self, current_state) -> bool:
        seg = self.project_service.get_segment(self.segment_id)
        if not seg: return False
        # Vị trí cắt phải nằm gọn bên trong segment, cách viền ít nhất 50ms
        if self.split_ms <= seg.start_ms + 50 or self.split_ms >= seg.end_ms - 50:
            return False
        return True

    def execute(self, context=None):
        seg = self.project_service.get_segment(self.segment_id)
        self.original_end_ms = seg.end_ms
        
        # Cắt segment hiện tại
        seg.end_ms = self.split_ms
        
        # Tạo segment mới (Nửa bên phải, text rỗng)
        from core.models import SubtitleSegment # Import model nội bộ
        new_id = int(time.time() * 1000) # Fake ID duy nhất
        self.new_segment = SubtitleSegment(new_id, self.split_ms, self.original_end_ms, "")
        
        # Chèn vào mảng và sort
        segments = self.project_service.get_all_segments()
        segments.append(self.new_segment)
        segments.sort(key=lambda s: s.start_ms)
        
        self.project_service.mark_dirty()
        return None

    def undo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        seg.end_ms = self.original_end_ms
        
        segments = self.project_service.get_all_segments()
        segments.remove(self.new_segment)
        self.project_service.mark_dirty()

    def redo(self) -> None:
        seg = self.project_service.get_segment(self.segment_id)
        seg.end_ms = self.split_ms
        
        segments = self.project_service.get_all_segments()
        segments.append(self.new_segment)
        segments.sort(key=lambda s: s.start_ms)
        self.project_service.mark_dirty()


class MergeSegmentsCommand(TimelineEditCommand):
    """Lệnh gộp nhiều Segments liền kề thành 1"""
    
    def __init__(self, project_service, segment_ids: set):
        super().__init__(project_service)
        self.segment_ids = list(segment_ids)
        self.deleted_segments = []
        self.target_segment = None
        self.original_end_ms = 0
        self.original_text = ""

    def can_execute(self, current_state) -> bool:
        return len(self.segment_ids) >= 2

    def execute(self, context=None):
        segments = self.project_service.get_all_segments()
        # Lọc ra các segments được chọn và sort theo thời gian
        to_merge = sorted([s for s in segments if s.id in self.segment_ids], key=lambda s: s.start_ms)
        
        self.target_segment = to_merge[0]
        self.original_end_ms = self.target_segment.end_ms
        self.original_text = self.target_segment.text
        
        self.deleted_segments = to_merge[1:]
        
        # Áp dụng chính sách Text Merge
        combined_text = TextMergePolicy.execute([s.text for s in to_merge])
        
        # Kéo dài segment đầu tiên và gán text mới
        self.target_segment.end_ms = to_merge[-1].end_ms
        self.target_segment.text = combined_text
        
        # Xóa các segment thừa
        for s in self.deleted_segments:
            segments.remove(s)
            
        self.project_service.mark_dirty()
        return None

    def undo(self) -> None:
        self.target_segment.end_ms = self.original_end_ms
        self.target_segment.text = self.original_text
        
        segments = self.project_service.get_all_segments()
        for s in self.deleted_segments:
            segments.append(s)
        segments.sort(key=lambda s: s.start_ms)
        self.project_service.mark_dirty()

    def redo(self) -> None:
        self.execute() # Thực thi lại logic y hệt


class DeleteSegmentCommand(TimelineEditCommand):
    """Lệnh xóa (các) Segment"""
    
    def __init__(self, project_service, segment_ids: set):
        super().__init__(project_service)
        self.segment_ids = segment_ids
        self.deleted_segments = []

    def can_execute(self, current_state) -> bool:
        return len(self.segment_ids) > 0

    def execute(self, context=None):
        segments = self.project_service.get_all_segments()
        self.deleted_segments = [s for s in segments if s.id in self.segment_ids]
        
        for s in self.deleted_segments:
            segments.remove(s)
            
        self.project_service.mark_dirty()
        return None

    def undo(self) -> None:
        segments = self.project_service.get_all_segments()
        for s in self.deleted_segments:
            segments.append(s)
        segments.sort(key=lambda s: s.start_ms)
        self.project_service.mark_dirty()

    def redo(self) -> None:
        self.execute()