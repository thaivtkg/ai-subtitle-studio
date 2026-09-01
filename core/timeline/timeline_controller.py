from PySide6.QtCore import QEvent, QObject, Qt

from core.timeline.timeline_commands import (
    DeleteSegmentCommand,
    MergeSegmentsCommand,
    MoveSegmentCommand,
    ResizeEndCommand,
    ResizeStartCommand,
    SplitSegmentCommand,
)
from core.timeline.timeline_state import TimelineState, TimelineStateManager
from core.timeline.timeline_undo_manager import UndoRedoManager
from core.subtitle_editing.commands.timeline_adapter import TimelineCommandAdapter
from ui.timeline.subtitle_track import EditMode
from ui.toast import Toast


class TimelineController(QObject):
    """Điều phối Tương tác UI -> Cập nhật State Machine -> Đẩy lệnh vào Artifact Store"""
    
    def __init__(self, project_service, ui_widget, data_provider, undo_manager=None, selection_controller=None):
        super().__init__()
        self.project = project_service
        self.ui = ui_widget
        self.data_provider = data_provider 
        self.state_manager = TimelineStateManager()
        self.undo_manager = undo_manager or UndoRedoManager()
        self.selection_controller = selection_controller

        self.ui.setFocusPolicy(Qt.StrongFocus)
        if hasattr(self.ui.container, 'waveform'):
            self.ui.container.waveform.setFocusPolicy(Qt.StrongFocus)
        if hasattr(self.ui.container, 'ruler'):
            self.ui.container.ruler.setFocusPolicy(Qt.StrongFocus)
            
        self.ui.container.track.edit_committed.connect(self.handle_edit_commit)
        
        self.ui.installEventFilter(self)
        if hasattr(self.ui.container, 'ruler'):
            self.ui.container.ruler.installEventFilter(self)
        if hasattr(self.ui.container, 'waveform'):
            self.ui.container.waveform.installEventFilter(self)
        self.ui.container.track.installEventFilter(self)

        if self.selection_controller:
            self.selection_controller.selection_changed.connect(self.sync_selection)

    def sync_selection(self, index, segment_id, source=None):
        track = self.ui.container.track
        ids = {segment_id} if segment_id and any(s.segment_id == segment_id for s in track.segments) else set()
        if not ids and 0 <= index < len(track.segments):
            ids = {track.segments[index].segment_id}
        track.selected_ids = ids
        track.update()

    # --- TÍNH NĂNG MỚI: ĐỒNG BỘ TỪ BẢNG CHỮ LÊN TIMELINE ---
    def sync_from_editor(self, ms: int):
        """Đồng bộ từ Bảng chữ lên Timeline: Bôi đen khối phụ đề và tự động cuộn Timeline tới đó"""
        track = self.ui.container.track
        found_id = None
        for seg in track.segments:
            if seg.start_ms - 50 <= ms <= seg.end_ms + 50:
                found_id = seg.segment_id
                break
        
        if found_id:
            track.selected_ids = {found_id}
        else:
            track.selected_ids.clear()
            
        track.update()

        # Tự động cuộn thanh Scroll của Timeline
        from PySide6.QtWidgets import QScrollArea
        scroll_area = self.ui if isinstance(self.ui, QScrollArea) else self.ui.findChild(QScrollArea)
        if scroll_area:
            x = track._ms_to_x(ms)
            scrollbar = scroll_area.horizontalScrollBar()
            viewport_width = scroll_area.viewport().width()
            target_scroll = x - (viewport_width // 2) # Tính toán đưa khối ra giữa màn hình
            target_scroll = max(0, min(target_scroll, scrollbar.maximum()))
            scrollbar.setValue(target_scroll)
    # -------------------------------------------------------

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                obj.setFocus() 
                if obj in (self.ui.container.ruler, self.ui.container.waveform):
                    self._do_seek(event.pos().x(), event.modifiers())
                    return True 
        elif event.type() == QEvent.MouseMove and (event.buttons() & Qt.LeftButton):
            if obj in (self.ui.container.ruler, self.ui.container.waveform):
                self._do_seek(event.pos().x(), event.modifiers())
                return True
        elif event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            if key == Qt.Key_T:
                self._trigger_split()
                return True
            elif key == Qt.Key_M:
                self._trigger_merge()
                return True
            elif key == Qt.Key_Delete:
                self._trigger_delete()
                return True
            elif key == Qt.Key_Z:
                if modifiers == Qt.ControlModifier:
                    self.handle_undo()
                    return True
                elif modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
                    self.handle_redo()
                    return True
        return super().eventFilter(obj, event)

    def _do_seek(self, x, modifiers=Qt.NoModifier):
        pixels_per_sec = self.ui.container.track.pixels_per_second
        target_ms = int((x / pixels_per_sec) * 1000.0)
        target_ms = max(0, target_ms) 
        
        if hasattr(self.ui, 'seek_requested'):
            self.ui.seek_requested.emit(target_ms)
        if hasattr(self.ui, 'update_playhead'):
            self.ui.update_playhead(target_ms)

        if modifiers != Qt.ControlModifier:
            track = self.ui.container.track
            found_seg = None
            for seg in track.segments:
                if seg.start_ms <= target_ms <= seg.end_ms:
                    found_seg = seg
                    break
            
            if found_seg:
                track.selected_ids = {found_seg.segment_id}
            else:
                track.selected_ids.clear()
            track.update()

    def _trigger_split(self):
        track = self.ui.container.track
        target_id = track.hovered_id if track.hovered_id != "" else (list(track.selected_ids)[0] if track.selected_ids else "")
        playhead = track.playhead_ms
        
        if not target_id:
            for seg in track.segments:
                if getattr(seg, 'start_ms', 0) <= playhead <= getattr(seg, 'end_ms', 0):
                    target_id = seg.segment_id
                    break
                    
        if target_id: 
            cmd = SplitSegmentCommand(self.project, self.data_provider, target_id, playhead)
            if cmd.can_execute(None):
                self._execute_safe(cmd)
            else:
                Toast.show_info(self.ui.window(), "Không thể cắt quá sát 2 mép của khối phụ đề (Cần cách lề 50ms)!")
        else:
            Toast.show_info(self.ui.window(), "Chưa chọn khối phụ đề hoặc kim không nằm trên phụ đề nào để cắt.")

    def _trigger_merge(self):
        track = self.ui.container.track
        if len(track.selected_ids) >= 2: 
            cmd = MergeSegmentsCommand(self.project, self.data_provider, track.selected_ids)
            if cmd.can_execute(None):
                self._execute_safe(cmd)
                if hasattr(cmd, 'target_segment') and cmd.target_segment:
                    self.ui.container.track.selected_ids = {cmd.target_segment.segment_id}
            else:
                Toast.show_info(self.ui.window(), "Chỉ có thể gộp các khối phụ đề đứng cạnh nhau!")
        else:
            Toast.show_info(self.ui.window(), "Hãy giữ Ctrl và Click chuột chọn ít nhất 2 khối để gộp.")

    def _trigger_delete(self):
        track = self.ui.container.track
        if track.selected_ids: 
            cmd = DeleteSegmentCommand(self.project, self.data_provider, track.selected_ids)
            if cmd.can_execute(None):
                self._execute_safe(cmd)
                self.ui.container.track.selected_ids.clear()
        else:
            Toast.show_info(self.ui.window(), "Chưa chọn khối phụ đề nào để xóa.")

    def handle_edit_commit(self, segment_id: str, mode: EditMode, delta_ms: int):
        if not self.state_manager.can_transition(TimelineState.COMMITTING):
            self.ui.container.track.update()
            return
        self.state_manager.transition_to(TimelineState.COMMITTING)
        try:
            command = None
            if mode == EditMode.MOVE: command = MoveSegmentCommand(self.project, self.data_provider, segment_id, delta_ms)
            elif mode == EditMode.RESIZE_LEFT: command = ResizeStartCommand(self.project, self.data_provider, segment_id, delta_ms)
            elif mode == EditMode.RESIZE_RIGHT: command = ResizeEndCommand(self.project, self.data_provider, segment_id, delta_ms)

            if command and command.can_execute(None):
                if self._push_command(command):
                    self._refresh_ui()
                else:
                    self.ui.container.track.update()
            else:
                self.ui.container.track.update()
        finally:
            self.state_manager.transition_to(TimelineState.IDLE)

    def handle_undo(self):
        if not self.state_manager.can_transition(TimelineState.COMMITTING):
            return
            
        self.state_manager.transition_to(TimelineState.COMMITTING)
        try:
            if self.undo_manager.undo():
                self._refresh_ui()
        except Exception as e:
            import traceback
            print(f"[TIMELINE-UNDO-ERROR] Lỗi khi thực hiện Undo: {e}")
            traceback.print_exc()
            Toast.show_error(self.ui.window(), f"Lỗi Undo: {str(e)}")
        finally:
            self.state_manager.transition_to(TimelineState.IDLE)

    def handle_redo(self):
        if not self.state_manager.can_transition(TimelineState.COMMITTING):
            return
            
        self.state_manager.transition_to(TimelineState.COMMITTING)
        try:
            if self.undo_manager.redo():
                self._refresh_ui()
        except Exception as e:
            import traceback
            print(f"[TIMELINE-REDO-ERROR] Lỗi khi thực hiện Redo: {e}")
            traceback.print_exc()
            Toast.show_error(self.ui.window(), f"Lỗi Redo: {str(e)}")
        finally:
            self.state_manager.transition_to(TimelineState.IDLE)

    def _execute_safe(self, command):
        if not self.state_manager.can_transition(TimelineState.COMMITTING): return
        self.state_manager.transition_to(TimelineState.COMMITTING)
        try:
            if self._push_command(command):
                self._refresh_ui()
        finally:
            self.state_manager.transition_to(TimelineState.IDLE)

    def _push_command(self, command):
        if not command.can_execute(None):
            return False
        if hasattr(self.undo_manager, "push"):
            self.undo_manager.push(TimelineCommandAdapter(command))
            return True
        return self.undo_manager.execute_command(command, self.state_manager)

    def _refresh_ui(self):
        # 1. ĐỒNG BỘ DATA & SẮP XẾP TRƯỚC
        self.data_provider.sync_back_to_editor()
        
        # 2. ĐẨY LÊN TIMELINE VIEW SAU (Lúc này danh sách đã được sắp xếp chuẩn 100%)
        self.ui.load_project_data(self.data_provider.get_duration_ms(), self.data_provider.get_all_segments())
        
        # 3. VẼ LẠI TABLE BÊN DƯỚI
        main_window = self.ui.window()
        if hasattr(main_window, 'sub_editor'):
            main_window.sub_editor.render_page()
            if hasattr(main_window, 'project_service'):
                main_window.project_service.mark_dirty()
