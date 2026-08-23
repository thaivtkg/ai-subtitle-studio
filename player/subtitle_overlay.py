import re
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy

from ui.animations.animation_types import SubtitleAnimationState, SubtitleRenderInput
from ui.animations.subtitle_animation_controller import SubtitleAnimationController


@dataclass
class VisualLine:
    text: str
    start_char_idx: int
    end_char_idx: int


class SubtitleOverlay(QLabel):
    def __init__(self, parent=None, controller: SubtitleAnimationController = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.anim_controller = controller
        self.render_input: SubtitleRenderInput | None = None
        self.current_time_ms = 0

        self.font_family = "Arial"
        self.font_size = 20
        self.text_color = QColor("white")
        self.outline_color = QColor("black")
        self.outline_width = 2
        self.position_mode = "Bottom"
        self.highlight_color = QColor("#00E5FF")

        self.update_style()

    def update_style(self, family=None, size=None, color=None, out_color=None, out_width=None, position=None):
        if family: self.font_family = family
        if size is not None: self.font_size = int(size)
        if color: self.text_color = QColor(color)
        if out_color: self.outline_color = QColor(out_color)
        if out_width is not None: self.outline_width = int(out_width)
        if position: self.position_mode = position

        self.custom_font = QFont(self.font_family)
        self.custom_font.setPixelSize(self.font_size)
        self.custom_font.setBold(True)
        self.update()

    def update_subtitle(self, render_input: SubtitleRenderInput, current_time_ms: int):
        self.render_input = render_input
        self.current_time_ms = current_time_ms
        self.update()

    def clear_subtitle(self):
        self.render_input = None
        if self.anim_controller:
            self.anim_controller.current_state.reset()
        self.update()

    def _wrap_text_with_mapping(self, text: str, fm: QFontMetricsF, max_width: float) -> list[VisualLine]:
        """Chia dòng thông minh và bảo toàn 100% chỉ số ký tự gốc (Bao gồm Multi-spaces/Tabs)"""
        visual_lines: list[VisualLine] = []
        raw_lines = text.split('\n')
        global_char_offset = 0

        for r_idx, raw_line in enumerate(raw_lines):
            # Tách chuỗi theo cụm khoảng trắng, GIỮ LẠI các khoảng trắng trong mảng kết quả
            tokens = re.split(r'(\s+)', raw_line)
            cur_line = ""
            cur_line_start = global_char_offset
            
            for token in tokens:
                if not token:
                    continue
                    
                test_line = cur_line + token
                if fm.horizontalAdvance(test_line) <= max_width:
                    cur_line = test_line
                else:
                    # Nếu dòng đã có chữ, ngắt dòng
                    if cur_line.strip():
                        visual_lines.append(VisualLine(cur_line, cur_line_start, cur_line_start + len(cur_line)))
                        cur_line_start += len(cur_line)
                        cur_line = token
                    else:
                        # Fallback cho CJK hoặc 1 từ đơn dài hơn cả khung hình
                        temp = cur_line
                        for ch in token:
                            if fm.horizontalAdvance(temp + ch) > max_width and temp:
                                visual_lines.append(VisualLine(temp, cur_line_start, cur_line_start + len(temp)))
                                cur_line_start += len(temp)
                                temp = ""
                            temp += ch
                        cur_line = temp

            if cur_line:
                visual_lines.append(VisualLine(cur_line, cur_line_start, cur_line_start + len(cur_line)))

            # Cộng thêm 1 cho ký tự '\n' bị mất khi split ban đầu (trừ dòng cuối)
            global_char_offset += len(raw_line) + (1 if r_idx < len(raw_lines) - 1 else 0)

        return visual_lines

    def _snap_to_word_boundary(self, line: str, target_idx: int) -> int:
        if target_idx <= 0: return 0
        if target_idx >= len(line) or ' ' not in line: return target_idx
        idx = target_idx
        while idx < len(line) and line[idx] != ' ':
            idx += 1
        return idx

    def paintEvent(self, event):
        if not self.render_input or not self.render_input.text.strip():
            return

        visual_state = (
            self.anim_controller.calculate_state(self.current_time_ms, self.render_input)
            if self.anim_controller
            else None
        )

        if visual_state and (visual_state.animation_state == SubtitleAnimationState.HIDDEN or visual_state.opacity <= 0):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(self.custom_font)

        fm = QFontMetricsF(self.custom_font)
        max_text_width = self.width() * 0.90
        lines = self._wrap_text_with_mapping(self.render_input.text, fm, max_text_width)
        
        line_height = fm.height()
        total_height = line_height * len(lines)
        y_offset = visual_state.y_offset if visual_state else 0.0

        margin = 40
        if self.position_mode == "Top":
            start_y = margin + fm.ascent() + y_offset
        elif self.position_mode == "Middle":
            start_y = (self.height() - total_height) / 2 + fm.ascent() + y_offset
        else:
            start_y = self.height() - margin - total_height + fm.ascent() + y_offset

        if visual_state:
            painter.setOpacity(visual_state.opacity)
            self._draw_animated(painter, fm, lines, start_y, visual_state)
        else:
            painter.setOpacity(1.0)
            self._draw_static(painter, fm, lines, start_y)

    def _draw_static(self, painter, fm, lines: list[VisualLine], start_y: float):
        current_y = start_y
        for v_line in lines:
            line_width = fm.horizontalAdvance(v_line.text)
            start_x = (self.width() - line_width) / 2
            self._draw_text_path(painter, start_x, current_y, v_line.text, self.text_color)
            current_y += fm.height()

    def _draw_animated(self, painter, fm, lines: list[VisualLine], start_y: float, state):
        current_y = start_y
        is_reveal = state.visible_chars != -1
        is_highlight = state.highlight_chars > 0

        for v_line in lines:
            # Layout cố định hình học theo toàn bộ dòng chữ
            full_line_width = fm.horizontalAdvance(v_line.text)
            start_x = (self.width() - full_line_width) / 2

            if is_reveal:
                if state.visible_chars <= v_line.start_char_idx:
                    pass
                elif state.visible_chars >= v_line.end_char_idx:
                    self._draw_text_path(painter, start_x, current_y, v_line.text, self.text_color)
                else:
                    raw_cut = state.visible_chars - v_line.start_char_idx
                    cut_idx = self._snap_to_word_boundary(v_line.text, raw_cut)
                    self._draw_text_path(painter, start_x, current_y, v_line.text[:cut_idx], self.text_color)

            elif is_highlight:
                if state.highlight_chars <= v_line.start_char_idx:
                    self._draw_text_path(painter, start_x, current_y, v_line.text, self.text_color)
                elif state.highlight_chars >= v_line.end_char_idx:
                    self._draw_text_path(painter, start_x, current_y, v_line.text, self.highlight_color)
                else:
                    raw_cut = state.highlight_chars - v_line.start_char_idx
                    cut_idx = self._snap_to_word_boundary(v_line.text, raw_cut)
                    hl_part = v_line.text[:cut_idx]
                    norm_part = v_line.text[cut_idx:]

                    self._draw_text_path(painter, start_x, current_y, hl_part, self.highlight_color)
                    offset_x = fm.horizontalAdvance(hl_part)
                    self._draw_text_path(painter, start_x + offset_x, current_y, norm_part, self.text_color)
            else:
                self._draw_text_path(painter, start_x, current_y, v_line.text, self.text_color)

            current_y += fm.height()

    def _draw_text_path(self, painter, x: float, y: float, text: str, fill_color: QColor):
        if not text: return
        path = QPainterPath()
        path.addText(x, y, painter.font(), text)
        if self.outline_width > 0:
            pen = QPen(self.outline_color, self.outline_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        painter.fillPath(path, fill_color)