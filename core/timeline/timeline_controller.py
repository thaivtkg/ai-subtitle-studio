from core.timeline.timeline_state import TimelineState, TimelineStateManager
from core.timeline.timeline_commands import (
    MoveSegmentCommand, ResizeStartCommand, ResizeEndCommand, 
    SplitSegmentCommand, MergeSegmentsCommand, DeleteSegmentCommand
)
from core.timeline.timeline_undo_manager import UndoRedoManager
from ui.timeline.subtitle_track import EditMode

class TimelineController:
    """Điều phối Tương tác UI -> Cập nhật State Machine -> Đẩy lệnh vào Artifact Store"""
    
    def __init__(self, project_service, ui_widget):
        self.project = project_service
        self.ui = ui_widget
        self.state_manager = TimelineStateManager()
        self.undo_manager = UndoRedoManager()

        # Ràng buộc tín hiệu Edit (Kéo thả & Resize)
        self.ui.container.track.edit_committed.connect(self.handle_edit_commit)
        
        # Ràng buộc tín hiệu Phím tắt cấu trúc
        self.ui.container.track.action_split_requested.connect(self.handle_split)
        self.ui.container.track.action_merge_requested.connect(self.handle_merge)
        self.ui.container.track.action_delete_requested.connect(self.handle_delete)
        self.ui.container.track.action_undo_requested.connect(self.handle_undo)
        self.ui.container.track.action_redo_requested.connect(self.handle_redo)

    # ==========================================
    # 1. XỬ LÝ CHỈNH SỬA KÉO THẢ (MOVE / RESIZE)
    # ==========================================
    def handle_edit_commit(self, segment_id: int, mode: EditMode, delta_ms: int):
        """Khóa FSM, xử lý Command và ép UI vẽ lại dữ liệu gốc"""
        if not self.state_manager.can_transition(TimelineState.COMMITTING):
            print("[Timeline] Từ chối thao tác: Đang trong tiến trình khóa.")
            self.ui.container.track.update() # Hủy Ghost render
            return

        self.state_manager.transition_to(TimelineState.COMMITTING)

        try:
            command = None
            if mode == EditMode.MOVE:
                command = MoveSegmentCommand(self.project, segment_id, delta_ms)
            elif mode == EditMode.RESIZE_LEFT: 
                command = ResizeStartCommand(self.project, segment_id, delta_ms)
            elif mode == EditMode.RESIZE_RIGHT:
                command = ResizeEndCommand(self.project, segment_id, delta_ms)

            if command and self.undo_manager.execute_command(command, self.state_manager):
                print(f"[Timeline] Đã commit lệnh {mode.name} (ID:{segment_id}, {delta_ms}ms)")
                self._refresh_ui()
            else:
                print(f"[Timeline] Lệnh {mode.name} bị Validator từ chối.")
                self.ui.container.track.update()
        finally:
            self.state_manager.transition_to(TimelineState.IDLE)

    # ==========================================
    # 2. XỬ LÝ PHÍM TẮT (SPLIT, MERGE, DELETE)
    # ==========================================
    def handle_split(self, segment_id: int):
        playhead_ms = self.ui.container.track.playhead_ms
        cmd = SplitSegmentCommand(self.project, segment_id, playhead_ms)
        self._execute_safe(cmd)

    def handle_merge(self, segment_ids: set):
        cmd = MergeSegmentsCommand(self.project, segment_ids)
        self._execute_safe(cmd)
        if cmd.target_segment:
            self.ui.container.track.selected_ids = {cmd.target_segment.id}

    def handle_delete(self, segment_ids: set):
        cmd = DeleteSegmentCommand(self.project, segment_ids)
        self._execute_safe(cmd)
        self.ui.container.track.selected_ids.clear()

    # ==========================================
    # 3. QUẢN LÝ LỊCH SỬ (UNDO / REDO)
    # ==========================================
    def handle_undo(self):
        if self.state_manager.can_transition(TimelineState.COMMITTING):
            self.state_manager.transition_to(TimelineState.COMMITTING)
            try:
                if self.undo_manager.undo():
                    self._refresh_ui()
            finally:
                self.state_manager.transition_to(TimelineState.IDLE)

    def handle_redo(self):
        if self.state_manager.can_transition(TimelineState.COMMITTING):
            self.state_manager.transition_to(TimelineState.COMMITTING)
            try:
                if self.undo_manager.redo():
                    self._refresh_ui()
            finally:
                self.state_manager.transition_to(TimelineState.IDLE)

    # ==========================================
    # 4. HÀM PHỤ TRỢ (HELPERS)
    # ==========================================
    def _execute_safe(self, command):
        """Hàm bọc (Wrapper) để kiểm tra FSM và thực thi lệnh an toàn"""
        if not self.state_manager.can_transition(TimelineState.COMMITTING):
            return
            
        self.state_manager.transition_to(TimelineState.COMMITTING)
        try:
            if self.undo_manager.execute_command(command, self.state_manager):
                self._refresh_ui()
        finally:
            self.state_manager.transition_to(TimelineState.IDLE)

    def _refresh_ui(self):
        """Tải lại toàn bộ dữ liệu từ Model lên View"""
        self.ui.load_project_data(self.project.get_duration_ms(), self.project.get_all_segments())