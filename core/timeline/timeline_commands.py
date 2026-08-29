import copy

class TimelineEditCommand:
    """Base Command: Áp dụng cơ chế Snapshot để đảm bảo Exact-state Undo/Redo"""
    def __init__(self, project_service, data_provider):
        self.project_service = project_service
        self.data_provider = data_provider
        self.before_states = {}
        self.after_states = {}
        self.added_ids = []
        self.removed_ids = []

    def _check_artifact(self):
        project = self.project_service.current_project
        if not project: return False
        art_id = None
        if hasattr(project.state, 'timing') and project.state.timing and hasattr(project.state.timing, 'timing_artifact_id'):
            art_id = project.state.timing.timing_artifact_id
        if not art_id: 
            art_id = project.state.active_artifact_id
        if not art_id: return False
        return self.project_service.artifact_store.get(art_id) is not None

    def _increment_revision(self):
        project = self.project_service.current_project
        art_id = None
        if hasattr(project.state, 'timing') and project.state.timing and hasattr(project.state.timing, 'timing_artifact_id'):
            art_id = project.state.timing.timing_artifact_id
        if not art_id: 
            art_id = project.state.active_artifact_id
        artifact = self.project_service.artifact_store.get(art_id)
        if artifact:
            artifact.revision += 1
        return True

    def _capture_state(self, segment_ids, state_dict):
        for sid in segment_ids:
            seg = self.data_provider.get_segment(sid)
            if seg:
                state_dict[sid] = copy.deepcopy(seg.get_raw_dict())

    def _restore_state(self, states_to_restore, ids_to_remove):
        for sid in ids_to_remove:
            seg = self.data_provider.get_segment(sid)
            if seg:
                self.data_provider.remove_segment(seg)

        for sid, raw_dict in states_to_restore.items():
            self.data_provider.restore_segment_from_raw(raw_dict)

    def undo(self):
        self._restore_state(self.before_states, self.added_ids)
        self._increment_revision()
        self.project_service.mark_dirty()

    def redo(self):
        self._restore_state(self.after_states, self.removed_ids)
        self._increment_revision()
        self.project_service.mark_dirty()

    def can_execute(self, context=None):
        return True

    def execute(self, context=None):
        raise NotImplementedError


class MoveSegmentCommand(TimelineEditCommand):
    def __init__(self, ps, dp, segment_id, delta_ms):
        super().__init__(ps, dp)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def execute(self, context=None):
        if not self._check_artifact(): raise RuntimeError("Lỗi Integrity: Không tìm thấy Timing Artifact.")
        self._capture_state([self.segment_id], self.before_states)
        
        seg = self.data_provider.get_segment(self.segment_id)
        seg.start_ms += self.delta_ms
        seg.end_ms += self.delta_ms
        
        self._capture_state([self.segment_id], self.after_states)
        self._increment_revision()
        self.project_service.mark_dirty()
        return True


class ResizeStartCommand(TimelineEditCommand):
    def __init__(self, ps, dp, segment_id, delta_ms):
        super().__init__(ps, dp)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def execute(self, context=None):
        if not self._check_artifact(): raise RuntimeError("Lỗi Integrity: Không tìm thấy Timing Artifact.")
        self._capture_state([self.segment_id], self.before_states)
        
        seg = self.data_provider.get_segment(self.segment_id)
        seg.start_ms += self.delta_ms
        
        self._capture_state([self.segment_id], self.after_states)
        self._increment_revision()
        self.project_service.mark_dirty()
        return True


class ResizeEndCommand(TimelineEditCommand):
    def __init__(self, ps, dp, segment_id, delta_ms):
        super().__init__(ps, dp)
        self.segment_id = segment_id
        self.delta_ms = delta_ms

    def execute(self, context=None):
        if not self._check_artifact(): raise RuntimeError("Lỗi Integrity: Không tìm thấy Timing Artifact.")
        self._capture_state([self.segment_id], self.before_states)
        
        seg = self.data_provider.get_segment(self.segment_id)
        seg.end_ms += self.delta_ms
        
        self._capture_state([self.segment_id], self.after_states)
        self._increment_revision()
        self.project_service.mark_dirty()
        return True


class SplitSegmentCommand(TimelineEditCommand):
    def __init__(self, ps, dp, segment_id, split_ms):
        super().__init__(ps, dp)
        self.segment_id = segment_id
        self.split_ms = split_ms

    def can_execute(self, context=None):
        seg = self.data_provider.get_segment(self.segment_id)
        if not seg: return False
        return (seg.start_ms + 50) < self.split_ms < (seg.end_ms - 50)

    def execute(self, context=None):
        if not self._check_artifact(): raise RuntimeError("Lỗi Integrity: Không tìm thấy Timing Artifact.")
        self._capture_state([self.segment_id], self.before_states)
        
        seg = self.data_provider.get_segment(self.segment_id)
        new_seg = self.data_provider.create_split_segment(self.segment_id, self.split_ms)
        
        # [BẢO VỆ] Chặn lỗi NoneType nếu tạo Segment thất bại
        if not new_seg:
            raise RuntimeError("Lỗi nội bộ: Không thể sinh ra đoạn khối cắt mới.")
            
        seg.end_ms = self.split_ms
        self.data_provider.add_segment(new_seg)
        
        self.added_ids = [new_seg.segment_id]
        self._capture_state([self.segment_id, new_seg.segment_id], self.after_states)
        self._increment_revision()
        self.project_service.mark_dirty()
        return True


class MergeSegmentsCommand(TimelineEditCommand):
    def __init__(self, ps, dp, segment_ids):
        super().__init__(ps, dp)
        self.segment_ids = list(segment_ids)
        self.target_id = None

    def can_execute(self, context=None):
        if len(self.segment_ids) < 2: return False
        segs = [self.data_provider.get_segment(sid) for sid in self.segment_ids]
        segs = sorted([s for s in segs if s], key=lambda x: x.start_ms)
        
        for i in range(len(segs) - 1):
            if segs[i + 1].start_ms - segs[i].end_ms > 500:
                return False
        return True

    def execute(self, context=None):
        if not self._check_artifact(): raise RuntimeError("Lỗi Integrity.")
        
        segs = [self.data_provider.get_segment(sid) for sid in self.segment_ids]
        segs = sorted([s for s in segs if s], key=lambda x: x.start_ms)
        self.segment_ids = [s.segment_id for s in segs]
        
        self._capture_state(self.segment_ids, self.before_states)
        
        target = segs[0]
        self.target_id = target.segment_id
        
        merged_text = target.text if target.text and target.text != "[ Chưa có nội dung ]" else ""
        for s in segs[1:]:
            valid_text = s.text if s.text and s.text != "[ Chưa có nội dung ]" else ""
            if valid_text:
                merged_text = (merged_text + " " + valid_text).strip()
                
        target.end_ms = segs[-1].end_ms
        target.text = merged_text if merged_text else "[ Chưa có nội dung ]"
        
        self.removed_ids = [s.segment_id for s in segs[1:]]
        for sid in self.removed_ids:
            self.data_provider.remove_segment(self.data_provider.get_segment(sid))
            
        self._capture_state([self.target_id], self.after_states)
        self._increment_revision()
        self.project_service.mark_dirty()
        
        # [BẢO VỆ] Lưu lại target segment để bôi đen trên UI sau khi gộp
        self.target_segment = target
        return True


class DeleteSegmentCommand(TimelineEditCommand):
    def __init__(self, ps, dp, segment_ids):
        super().__init__(ps, dp)
        self.segment_ids = list(segment_ids)

    def execute(self, context=None):
        if not self._check_artifact(): raise RuntimeError("Lỗi Integrity.")
        self._capture_state(self.segment_ids, self.before_states)
        
        for sid in self.segment_ids:
            seg = self.data_provider.get_segment(sid)
            if seg:
                self.data_provider.remove_segment(seg)
                
        self.removed_ids = self.segment_ids.copy()
        self._increment_revision()
        self.project_service.mark_dirty()
        return True