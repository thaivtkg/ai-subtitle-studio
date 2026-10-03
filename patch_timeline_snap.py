import re

with open('ui/timeline/subtitle_track.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add is_snapped and snap_line_x to __init__
init_pattern = r'(self\.selected_gap = None\n\s*self\.pixels_per_second = 100)'
init_replace = r'\1\n        self.is_snapped = False\n        self.snap_line_x = None'
content = re.sub(init_pattern, init_replace, content)

# 2. Add to mouseReleaseEvent to clear them
release_pattern = r'(self\.drag_segment_id = ""\n\s*self\.current_delta_ms = 0)'
release_replace = r'\1\n            self.is_snapped = False\n            self.snap_line_x = None'
content = re.sub(release_pattern, release_replace, content)

# 3. Rewrite mouseMoveEvent completely
mouse_move_pattern = r'    def mouseMoveEvent\(self, event\):.*?(?=\n    def mouseReleaseEvent)'

new_mouse_move = '''    def mouseMoveEvent(self, event):
        x = event.pos().x()
        
        if self.edit_mode != EditMode.NONE:
            delta_x = x - self.drag_start_x
            raw_delta_ms = int((delta_x / self.pixels_per_second) * 1000.0)
            self.current_delta_ms = raw_delta_ms
            seg = next((s for s in self.segments if s.segment_id == self.drag_segment_id), None)
            
            self.is_snapped = False
            self.snap_line_x = None

            if seg:
                idx = self.segments.index(seg)
                prev_end = self.segments[idx-1].end_ms if idx > 0 else 0
                next_start = self.segments[idx+1].start_ms if idx < len(self.segments) - 1 else self.duration_ms
                
                # 1. Magnetic Snapping (O(1) logic with Snap Bypass)
                bypass_snap = (event.modifiers() & Qt.AltModifier) or (event.modifiers() & Qt.ShiftModifier)
                if self.snap_enabled and not bypass_snap:
                    SNAP_TOLERANCE_MS = 150
                    snap_threshold_ms = (self.snap_threshold_px / self.pixels_per_second) * 1000.0
                    
                    proposed_start = seg.start_ms + raw_delta_ms
                    proposed_end = seg.end_ms + raw_delta_ms
                    
                    if self.edit_mode in (EditMode.MOVE, EditMode.RESIZE_LEFT):
                        if abs(proposed_start - self.playhead_ms) <= snap_threshold_ms:
                            self.current_delta_ms = self.playhead_ms - seg.start_ms
                            self.is_snapped = True
                            self.snap_line_x = self._ms_to_x(self.playhead_ms)
                        elif abs(proposed_start - prev_end) <= SNAP_TOLERANCE_MS:
                            self.current_delta_ms = prev_end - seg.start_ms
                            self.is_snapped = True
                            self.snap_line_x = self._ms_to_x(prev_end)

                    if self.edit_mode in (EditMode.MOVE, EditMode.RESIZE_RIGHT):
                        if not self.is_snapped:
                            if abs(proposed_end - self.playhead_ms) <= snap_threshold_ms:
                                self.current_delta_ms = self.playhead_ms - seg.end_ms
                                self.is_snapped = True
                                self.snap_line_x = self._ms_to_x(self.playhead_ms)
                            elif abs(proposed_end - next_start) <= SNAP_TOLERANCE_MS:
                                self.current_delta_ms = next_start - seg.end_ms
                                self.is_snapped = True
                                self.snap_line_x = self._ms_to_x(next_start)

                # 2. Hard Clamp Constraints (Collision & Inversion Guard)
                min_duration = 100

                if self.edit_mode == EditMode.MOVE:
                    min_delta = prev_end - seg.start_ms
                    max_delta = next_start - seg.end_ms
                    self.current_delta_ms = max(min_delta, min(self.current_delta_ms, max_delta))
                elif self.edit_mode == EditMode.RESIZE_LEFT:
                    min_delta = prev_end - seg.start_ms
                    max_delta = (seg.end_ms - min_duration) - seg.start_ms
                    self.current_delta_ms = max(min_delta, min(self.current_delta_ms, max_delta))
                elif self.edit_mode == EditMode.RESIZE_RIGHT:
                    min_delta = (seg.start_ms + min_duration) - seg.end_ms
                    max_delta = next_start - seg.end_ms
                    self.current_delta_ms = max(min_delta, min(self.current_delta_ms, max_delta))

                c_start = seg.start_ms
                c_end = seg.end_ms
                if self.edit_mode == EditMode.MOVE:
                    c_start += self.current_delta_ms
                    c_end += self.current_delta_ms
                elif self.edit_mode == EditMode.RESIZE_LEFT:
                    c_start += self.current_delta_ms
                elif self.edit_mode == EditMode.RESIZE_RIGHT:
                    c_end += self.current_delta_ms
                
                self.live_edit_updated.emit(self.drag_segment_id, c_start, c_end, self.edit_mode)

            self.update() 
            return

        seg, mode = self.get_hit_target(x)
        if mode in (EditMode.RESIZE_LEFT, EditMode.RESIZE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        elif mode == EditMode.MOVE:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        new_hover_id = seg.segment_id if seg else ""
        if new_hover_id != self.hovered_id:
            self.hovered_id = new_hover_id
            self.update()

        super().mouseMoveEvent(event)'''

content = re.sub(mouse_move_pattern, new_mouse_move, content, flags=re.DOTALL)

# 4. Add the snap line rendering at the very end of paintEvent
paint_event_pattern = r'(        painter\.end\(\))'
paint_event_replace = r'''        if getattr(self, "is_snapped", False) and getattr(self, "snap_line_x", None) is not None:
            painter.setPen(QPen(QColor(Theme.CYAN), 1))
            painter.drawLine(self.snap_line_x, 0, self.snap_line_x, self.height())
\1'''
content = re.sub(paint_event_pattern, paint_event_replace, content)

with open('ui/timeline/subtitle_track.py', 'w', encoding='utf-8') as f:
    f.write(content)
