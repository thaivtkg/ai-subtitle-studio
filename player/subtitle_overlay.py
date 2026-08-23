from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy

from ui.animations.animation_types import SubtitleAnimationState, SubtitleTextEffect
from ui.animations.subtitle_animation_controller import SubtitleAnimationController


class SubtitleOverlay(QLabel):
    def __init__(self, parent=None, controller: SubtitleAnimationController = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Trạng thái dữ liệu cho Animation
        self.anim_controller = controller
        self.current_segment = None
        self.current_time_ms = 0
        
        # Thiết lập cơ bản
        self.font_family = "Arial"
        self.font_size = 20
        self.text_color = QColor("white")
        self.outline_color = QColor("black")
        self.outline_width = 2
        self.position_mode = "Bottom"
        self.highlight_color = QColor("#00E5FF") # Màu Cyan Highlight

        self.update_style()

    def update_style(self, family=None, size=None, color=None, out_color=None, out_width=None, position=None):
        if family: self.font_family = family
        
        # [FIX CRITICAL] Ép kiểu int() để giải quyết triệt để lỗi Shiboken (str -> C++)
        if size is not None: self.font_size = int(size)
        
        if color: self.text_color = QColor(color)
        if out_color: self.outline_color = QColor(out_color)
        
        # [FIX CRITICAL] Ép kiểu int() cho độ dày viền
        if out_width is not None: self.outline_width = int(out_width)
        
        if position: self.position_mode = position
        
        self.custom_font = QFont(self.font_family)
        self.custom_font.setPixelSize(self.font_size)
        self.custom_font.setBold(True)
        self.update()

    # Nhận toàn bộ đối tượng segment chứa start_ms, end_ms và thời gian thực
    def update_subtitle(self, segment, current_time_ms):
        self.current_segment = segment
        self.current_time_ms = current_time_ms
        self.update()

    def clear_subtitle(self):
        self.current_segment = None
        if self.anim_controller:
            self.anim_controller.current_state.reset()
        self.update()

    def paintEvent(self, event):
        if not self.current_segment:
            return
            
        raw_text = self.current_segment.get('text', '').strip()
        if not raw_text:
            return

        if self.anim_controller:
            visual_state = self.anim_controller.calculate_state(self.current_time_ms, self.current_segment)
        else:
            from ui.animations.subtitle_visual_state import SubtitleVisualState
            visual_state = SubtitleVisualState()
            visual_state.animation_state = SubtitleAnimationState.VISIBLE

        if visual_state.animation_state == SubtitleAnimationState.HIDDEN or visual_state.opacity <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # font = QFont(self.font_family, self.font_size)
        # font.setBold(True)
        # painter.setFont(font)

        # fm = QFontMetricsF(font)
        painter.setFont(self.custom_font)
        fm = QFontMetricsF(self.custom_font)
        
        # Tính toán chiều rộng tối đa cho phép (90% chiều rộng Video để có khoảng lề 2 bên an toàn)
        max_text_width = self.width() * 0.90
        
        # Chuyển text qua thuật toán ngắt dòng thông minh thay vì chỉ dùng split('\n')
        lines = self._wrap_text(raw_text, fm, max_text_width)
        
        line_height = fm.height()
        total_height = line_height * len(lines)
        
        margin = 40
        if self.position_mode == "Bottom":
            start_y = self.height() - margin - total_height + fm.ascent() + visual_state.y_offset
        elif self.position_mode == "Top":
            start_y = margin + fm.ascent() + visual_state.y_offset
        else:
            start_y = (self.height() - total_height) / 2 + fm.ascent() + visual_state.y_offset

        is_animated = (
            visual_state.opacity < 1.0 or 
            visual_state.visible_chars != -1 or 
            visual_state.highlight_chars > 0 or
            visual_state.y_offset != 0.0
        )

        painter.setOpacity(visual_state.opacity)
        if is_animated:
            self._draw_animated(painter, fm, lines, start_y, visual_state)
        else:
            self._draw_static(painter, fm, lines, start_y)

    def _draw_static(self, painter, fm, lines, start_y):
        current_y = start_y
        for line in lines:
            line_width = fm.horizontalAdvance(line)
            start_x = (self.width() - line_width) / 2
            self._draw_text_path(painter, start_x, current_y, line, self.text_color)
            current_y += fm.height()

    def _draw_animated(self, painter, fm, lines, start_y, state):
        current_y = start_y
        char_count = 0
        is_reveal = state.visible_chars != -1
        is_highlight = state.highlight_chars > 0

        for line in lines:
            line_len = len(line)
            line_width = fm.horizontalAdvance(line)
            start_x = (self.width() - line_width) / 2
            
            if is_reveal:
                if char_count >= state.visible_chars:
                    break
                elif char_count + line_len > state.visible_chars:
                    chars_to_draw = state.visible_chars - char_count
                    self._draw_text_path(painter, start_x, current_y, line[:chars_to_draw], self.text_color)
                else:
                    self._draw_text_path(painter, start_x, current_y, line, self.text_color)
            elif is_highlight:
                if char_count >= state.highlight_chars:
                    self._draw_text_path(painter, start_x, current_y, line, self.text_color)
                elif char_count + line_len > state.highlight_chars:
                    cut_idx = state.highlight_chars - char_count
                    highlight_part = line[:cut_idx]
                    normal_part = line[cut_idx:]
                    self._draw_text_path(painter, start_x, current_y, highlight_part, self.highlight_color)
                    offset_x = fm.horizontalAdvance(highlight_part)
                    self._draw_text_path(painter, start_x + offset_x, current_y, normal_part, self.text_color)
                else:
                    self._draw_text_path(painter, start_x, current_y, line, self.highlight_color)
            else:
                self._draw_text_path(painter, start_x, current_y, line, self.text_color)

            char_count += line_len + 1 
            current_y += fm.height()

    def _draw_text_path(self, painter, x, y, text, fill_color):
        if not text: return
        path = QPainterPath()
        path.addText(x, y, painter.font(), text)
        if self.outline_width > 0:
            pen = QPen(self.outline_color, self.outline_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        painter.fillPath(path, fill_color)

    def _wrap_text(self, text, fm, max_width):
        """Thuật toán ngắt dòng thông minh hỗ trợ Latin (Việt/Anh) và CJK (Nhật/Trung)"""
        result = []
        for raw_line in text.split('\n'):
            words = raw_line.split(' ')
            current_line = ""
            
            for word in words:
                # Thử ráp thêm từ mới vào dòng hiện tại
                test_line = f"{current_line} {word}" if current_line else word
                
                if fm.horizontalAdvance(test_line) <= max_width:
                    current_line = test_line
                else:
                    # Nếu dòng đã có chữ, đẩy dòng hiện tại vào kết quả và lấy từ mới làm dòng tiếp theo
                    if current_line:
                        result.append(current_line)
                        current_line = word
                    else:
                        current_line = word
                    
                    # Cứu cánh (Fallback) cho CJK: Nếu bản thân 1 khối chữ quá dài (do không có dấu cách)
                    while fm.horizontalAdvance(current_line) > max_width:
                        # Buộc phải cắt từng ký tự cho đến khi vừa khung
                        temp = ""
                        for char in current_line:
                            if fm.horizontalAdvance(temp + char) > max_width:
                                break
                            temp += char
                        result.append(temp)
                        current_line = current_line[len(temp):] # Phần dư đẩy xuống dòng dưới
                        
            if current_line:
                result.append(current_line)
        return result