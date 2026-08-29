from core.timeline.timeline_state import TimelineState, TimelineStateManager
from core.timeline.timeline_commands import (
    MoveSegmentCommand, ResizeStartCommand, ResizeEndCommand, 
    SplitSegmentCommand, MergeSegmentsCommand, DeleteSegmentCommand
)
from core.timeline.timeline_undo_manager import UndoRedoManager
from ui.timeline.subtitle_track import EditMode

class TimelineController:
    """Điều phối Tương tác UI -> Cập nhật State Machine -> Đẩy lệnh vào Artifact Store"""
    
    def __init__(self, project_service, ui_widget, data_provider):
        self.project = project_service
        self.ui = ui_widget
        self.data_provider = data_provider # Inject Interface
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
    def handle_edit_commit(self, segment_id: str, mode: EditMode, delta_ms: int):
        """Khóa FSM, xử lý Command và ép UI vẽ lại dữ liệu gốc"""
        if not self.state_manager.can_transition(TimelineState.COMMITTING):
            self.ui.container.track.update() # Hủy Ghost render
            return

        self.state_manager.transition_to(TimelineState.COMMITTING)

        try:
            command = None
            if mode == EditMode.MOVE:
                command = MoveSegmentCommand(self.project, self.data_provider, segment_id, delta_ms)
            elif mode == EditMode.RESIZE_LEFT: 
                command = ResizeStartCommand(self.project, self.data_provider, segment_id, delta_ms)
            elif mode == EditMode.RESIZE_RIGHT:
                command = ResizeEndCommand(self.project, self.data_provider, segment_id, delta_ms)

            if command and self.undo_manager.execute_command(command, self.state_manager):
                self._refresh_ui()
            else:
                self.ui.container.track.update()
        finally:
            self.state_manager.transition_to(TimelineState.IDLE)

    # ==========================================
    # 2. XỬ LÝ PHÍM TẮT (SPLIT, MERGE, DELETE)
    # ==========================================
    def handle_split(self, segment_id: str):
        playhead_ms = self.ui.container.track.playhead_ms
        cmd = SplitSegmentCommand(self.project, self.data_provider, segment_id, playhead_ms)
        self._execute_safe(cmd)

    def handle_merge(self, segment_ids: set):
        cmd = MergeSegmentsCommand(self.project, self.data_provider, segment_ids)
        self._execute_safe(cmd)
        if cmd.target_segment:
            self.ui.container.track.selected_ids = {cmd.target_segment.segment_id}

    def handle_delete(self, segment_ids: set):
        cmd = DeleteSegmentCommand(self.project, self.data_provider, segment_ids)
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
        """View cập nhật lại trạng thái và đồng bộ ngược về hệ thống file"""
        # 1. Yêu cầu giao diện Timeline tự vẽ lại các block
        self.ui.load_project_data(
            self.data_provider.get_duration_ms(), 
            self.data_provider.get_all_segments()
        )
        
        # 2. Ép đồng bộ dữ liệu chuẩn mực ngược về Subtitle Editor (Dạng Dict)
        self.data_provider.sync_back_to_editor()
        
        # 3. Yêu cầu Subtitle Editor (Bảng chữ) vẽ lại Table với dữ liệu mới
        # Truy xuất ngược lên MainWindow (Gui.py) thông qua widget hiện tại
        main_window = self.ui.window()
        if hasattr(main_window, 'sub_editor'):
            # Gọi hàm render_page() của SubtitleEditorWidget để load lại các hàng chữ
            main_window.sub_editor.render_page()
            
            # 4. Đánh dấu Project bị thay đổi để khi đóng app, phần mềm nhắc người dùng Ctrl+S
            if hasattr(main_window, 'project_service'):
                main_window.project_service.mark_dirty()