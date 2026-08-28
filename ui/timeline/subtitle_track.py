from enum import Enum
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PySide6.QtCore import Qt, QRect, Signal

from ui.theme import Theme

class EditMode(Enum):
    NONE = 0
    MOVE = 1
    RESIZE_LEFT = 2
    RESIZE_RIGHT = 3

class SubtitleTrack(QWidget):
    """[S8-T12 -> T18] Render Subtitle và Xử lý tương tác Kéo thả, Resize trực tiếp"""
    
    segment_clicked = Signal(int, bool)
    action_split_requested = Signal(int)
    action_merge_requested = Signal(set)
    action_delete_requested = Signal(set)
    action_undo_requested = Signal()
    action_redo_requested = Signal()
    
    # Phát tín hiệu khi thả chuột (Commit): id, edit_mode, delta_ms
    edit_committed = Signal(int, EditMode, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.segments = []
        self.pixels_per_second = 100
        self.duration_ms = 0
        self.playhead_ms = 0
        self.snap_enabled = True
        self.snap_threshold_px = 15
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.selected_ids = set()
        self.hovered_id = -1

        # Trạng thái Drag & Drop
        self.edit_mode = EditMode.NONE
        self.drag_segment_id = -1
        self.drag_start_x = 0
        self.current_delta_ms = 0

        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def update_playhead(self, ms: int):
        self.playhead_ms = ms

    def set_data(self, segments: list, duration_ms: int):
        self.segments = segments
        self.duration_ms = duration_ms
        self.update_geometry_size()
        self.update()

    def set_zoom(self, pixels_per_second: int):
        self.pixels_per_second = max(10, min(pixels_per_second, 1000))
        self.update_geometry_size()
        self.update()
        
    def set_selection(self, selected_ids: set):
        self.selected_ids = selected_ids
        self.update()

    def update_geometry_size(self):
        self.setMinimumWidth(int((self.duration_ms / 1000.0) * self.pixels_per_second))

    def _ms_to_x(self, ms: int) -> int:
        return int((ms / 1000.0) * self.pixels_per_second)

    def get_hit_target(self, x: int):
        """Phát hiện va chạm: Trả về (Segment, EditMode)"""
        target_ms = (x / self.pixels_per_second) * 1000.0
        edge_tolerance_ms = (5.0 / self.pixels_per_second) * 1000.0 # 5 pixel quy ra mili-giây

        for seg in self.segments:
            if seg.start_ms - edge_tolerance_ms <= target_ms <= seg.end_ms + edge_tolerance_ms:
                if abs(target_ms - seg.start_ms) <= edge_tolerance_ms:
                    return seg, EditMode.RESIZE_LEFT
                elif abs(target_ms - seg.end_ms) <= edge_tolerance_ms:
                    return seg, EditMode.RESIZE_RIGHT
                elif seg.start_ms <= target_ms <= seg.end_ms:
                    return seg, EditMode.MOVE
        return None, EditMode.NONE

    def mousePressEvent(self, event):
        self.setFocus() # Y
        if event.button() == Qt.LeftButton:
            seg, mode = self.get_hit_target(event.pos().x())
            is_ctrl = event.modifiers() == Qt.ControlModifier
            
            if seg:
                # Logic Chọn nhiều (Multi-select)
                if is_ctrl:
                    if seg.id in self.selected_ids:
                        self.selected_ids.remove(seg.id)
                    else:
                        self.selected_ids.add(seg.id)
                else:
                    if seg.id not in self.selected_ids:
                        self.selected_ids = {seg.id}
                        
                self.update()
                
                # Logic Kéo thả
                self.edit_mode = mode
                self.drag_segment_id = seg.id
                self.drag_start_x = event.pos().x()
                self.current_delta_ms = 0
                self.segment_clicked.emit(seg.id, is_ctrl)
            else:
                # Bấm ra ngoài -> Hủy chọn
                self.selected_ids.clear()
                self.update()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_T:
            # Ưu tiên segment đang được hover, nếu không có thì lấy segment đang select
            target_id = self.hovered_id if self.hovered_id != -1 else (list(self.selected_ids)[0] if self.selected_ids else -1)
            if target_id != -1:
                self.action_split_requested.emit(target_id)
                
        elif event.key() == Qt.Key_M:
            if len(self.selected_ids) >= 2:
                self.action_merge_requested.emit(self.selected_ids)
                
        elif event.key() == Qt.Key_Delete:
            if self.selected_ids:
                self.action_delete_requested.emit(self.selected_ids)
                
        elif event.key() == Qt.Key_Z and event.modifiers() == Qt.ControlModifier:
            self.action_undo_requested.emit()
            
        elif event.key() == Qt.Key_Z and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            self.action_redo_requested.emit()
            
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        x = event.pos().x()
        
        if self.edit_mode != EditMode.NONE:
            delta_x = x - self.drag_start_x
            raw_delta_ms = int((delta_x / self.pixels_per_second) * 1000.0)
            self.current_delta_ms = raw_delta_ms

            # --- THUẬT TOÁN SNAP TO PLAYHEAD ---
            if self.snap_enabled:
                seg = next((s for s in self.segments if s.id == self.drag_segment_id), None)
                if seg:
                    # Chuyển đổi Threshold từ Pixel sang ms tùy thuộc vào mức Zoom
                    snap_threshold_ms = (self.snap_threshold_px / self.pixels_per_second) * 1000.0
                    
                    proposed_start = seg.start_ms + raw_delta_ms
                    proposed_end = seg.end_ms + raw_delta_ms

                    # Kiểm tra cạnh trái
                    if self.edit_mode in (EditMode.MOVE, EditMode.RESIZE_LEFT):
                        if abs(proposed_start - self.playhead_ms) <= snap_threshold_ms:
                            self.current_delta_ms = self.playhead_ms - seg.start_ms

                    # Kiểm tra cạnh phải
                    if self.edit_mode in (EditMode.MOVE, EditMode.RESIZE_RIGHT):
                        if abs(proposed_end - self.playhead_ms) <= snap_threshold_ms:
                            self.current_delta_ms = self.playhead_ms - seg.end_ms

            self.update() 
            return

        # 2. Nếu chỉ lướt chuột qua (Hover) -> Đổi hình con trỏ
        seg, mode = self.get_hit_target(x)
        if mode in (EditMode.RESIZE_LEFT, EditMode.RESIZE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        new_hover_id = seg.id if seg else -1
        if new_hover_id != self.hovered_id:
            self.hovered_id = new_hover_id
            self.update()


        seg, mode = self.get_hit_target(x)
        if mode in (EditMode.RESIZE_LEFT, EditMode.RESIZE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        new_hover_id = seg.id if seg else -1
        if new_hover_id != self.hovered_id:
            self.hovered_id = new_hover_id
            self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.edit_mode != EditMode.NONE:
            if self.current_delta_ms != 0:
                # Bắn tín hiệu Commit lên Controller để xin FSM duyệt lệnh
                self.edit_committed.emit(self.drag_segment_id, self.edit_mode, self.current_delta_ms)
            
            # Reset trạng thái Edit
            self.edit_mode = EditMode.NONE
            self.drag_segment_id = -1
            self.current_delta_ms = 0
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        rect = event.rect()
        painter.fillRect(rect, QColor(Theme.SURFACE))

        if not self.segments: return

        start_ms = (rect.left() / self.pixels_per_second) * 1000.0
        end_ms = (rect.right() / self.pixels_per_second) * 1000.0

        for seg in self.segments:
            if seg.end_ms < start_ms: continue
            if seg.start_ms > end_ms: break

            # Tính tọa độ cho Khối hiển thị thực tế
            render_start_ms = seg.start_ms
            render_end_ms = seg.end_ms

            # Nếu Segment này đang bị kéo giãn -> Đè thông số vẽ bằng Ghost state
            is_dragging = (self.edit_mode != EditMode.NONE and seg.id == self.drag_segment_id)
            if is_dragging:
                if self.edit_mode == EditMode.MOVE:
                    render_start_ms += self.current_delta_ms
                    render_end_ms += self.current_delta_ms
                elif self.edit_mode == EditMode.RESIZE_LEFT:
                    render_start_ms += self.current_delta_ms
                elif self.edit_mode == EditMode.RESIZE_RIGHT:
                    render_end_ms += self.current_delta_ms

                # Validation hiển thị: Không cho Start vượt quá End
                if render_start_ms >= render_end_ms - 100:
                    if self.edit_mode == EditMode.RESIZE_LEFT: render_start_ms = render_end_ms - 100
                    if self.edit_mode == EditMode.RESIZE_RIGHT: render_end_ms = render_start_ms + 100

            x1 = self._ms_to_x(render_start_ms)
            x2 = self._ms_to_x(render_end_ms)
            seg_rect = QRect(x1, 5, max(1, x2 - x1), self.height() - 10)

            is_selected = seg.id in self.selected_ids
            is_hovered = seg.id == self.hovered_id

            bg_color = QColor(Theme.PRIMARY_PURPLE) if is_selected else QColor(Theme.SURFACE_ELEVATED)
            border_color = QColor(Theme.CYAN) if is_selected else (QColor(Theme.TEXT_SECONDARY) if is_hovered else QColor(Theme.BORDER))
            
            # Làm mờ Ghost Segment 50% để phân biệt với dữ liệu thật
            if is_dragging:
                bg_color.setAlpha(150)
                border_color = QColor(Theme.WARNING)
            elif is_hovered and not is_selected:
                bg_color = QColor(Theme.SURFACE_SOFT)

            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(border_color, 1))
            painter.drawRoundedRect(seg_rect, 4, 4)

            painter.setPen(QColor(Theme.TEXT_PRIMARY))
            text_rect = seg_rect.adjusted(5, 0, -5, 0)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, painter.fontMetrics().elidedText(seg.text, Qt.ElideRight, text_rect.width()))