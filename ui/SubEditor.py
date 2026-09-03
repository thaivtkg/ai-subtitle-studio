import json
import os
import re
import uuid

from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Nạp Design System
from ui.theme import Theme
from ui.toast import Toast
from core.subtitle_editing.commands.edit_text_command import EditTextCommand
from core.subtitle_editing.commands.edit_timing_command import EditTimingCommand
from core.subtitle_editing.commands.add_command import AddCommand
from core.subtitle_editing.commands.delete_command import DeleteCommand
from core.subtitle_editing.commands.merge_command import MergeCommand
from core.subtitle_editing.commands.split_command import SplitCommand
from core.subtitle_validation.subtitle_validator import SubtitleValidator
from core.subtitle_validation.validation_issue import Severity
from core.subtitle_editing.selection_controller import SelectionSource
from core.export.subtitle_parser import parse_srt_content


def ms_to_time_str(ms: int) -> str:
    """Format milliseconds as the canonical SRT timestamp."""
    s, ms = divmod(max(0, int(ms)), 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def time_str_to_ms(time_str: str) -> int:
    """Parse a strict HH:MM:SS,mmm timestamp; return -1 when invalid."""
    if isinstance(time_str, (int, float)) and not isinstance(time_str, bool):
        return int(time_str)
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", str(time_str).strip())
    if not match:
        return -1
    h, m, s, ms = map(int, match.groups())
    if m >= 60 or s >= 60 or ms >= 1000:
        return -1
    return (h * 3600 + m * 60 + s) * 1000 + ms


class CurrentSubtitleEditor(QWidget):
    changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.lbl_title = QLabel("Current Subtitle: None")
        self.lbl_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_title)
        times = QHBoxLayout()
        times.addWidget(QLabel("Start:"))
        self.start_edit = QLineEdit()
        times.addWidget(self.start_edit)
        times.addWidget(QLabel("End:"))
        self.end_edit = QLineEdit()
        times.addWidget(self.end_edit)
        times.addWidget(QLabel("Duration:"))
        self.lbl_duration = QLabel("0.000 s")
        times.addWidget(self.lbl_duration)
        layout.addLayout(times)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Nội dung phụ đề hiện tại...")
        self.text_edit.setMaximumHeight(70)
        layout.addWidget(self.text_edit)
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Previous")
        self.btn_next = QPushButton("Next ▶")
        self.btn_prev.clicked.connect(self._previous_requested)
        self.btn_next.clicked.connect(self._next_requested)
        nav.addWidget(self.btn_prev)
        nav.addStretch()
        nav.addWidget(self.btn_next)
        layout.addLayout(nav)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        for widget in (self.start_edit, self.end_edit):
            widget.textChanged.connect(self._schedule_emit)
        self.text_edit.textChanged.connect(self._schedule_emit)
        self._debounce.timeout.connect(self._emit_changed)

    def set_values(self, start, end, text):
        start = ms_to_time_str(start) if isinstance(start, (int, float)) else str(start)
        end = ms_to_time_str(end) if isinstance(end, (int, float)) else str(end)
        for widget, value in ((self.start_edit, start), (self.end_edit, end)):
            widget.blockSignals(True)
            widget.setText(value)
            widget.blockSignals(False)
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self.text_edit.blockSignals(False)
        start_ms = time_str_to_ms(start)
        end_ms = time_str_to_ms(end)
        self.lbl_duration.setText(f"{max(0, end_ms - start_ms) / 1000:.3f} s")

    def setTitle(self, title: str):
        self.lbl_title.setText(title)

    def _previous_requested(self):
        self.parent().select_previous() if self.parent() else None

    def _next_requested(self):
        self.parent().select_next() if self.parent() else None

    def _schedule_emit(self):
        self._debounce.start()

    def _emit_changed(self):
        self.changed.emit({"start": self.start_edit.text(), "end": self.end_edit.text(), "text": self.text_edit.toPlainText()})


class SubtitleEditorWidget(QWidget):
    seek_requested = Signal(int)
    srt_saved = Signal(str)
    live_edit_applied = Signal(list)
    save_requested = Signal(str)
    timing_committed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.srt_path = None
        
        self.all_segments = []
        self.undo_manager = None
        self.selection_controller = None
        self.current_page = 0
        self.current_index = -1
        self.group_size = 0     
        self.is_rendering = False
        self._is_syncing_ui = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; width: 1px; }}")
        
        # ================= LỚP 1: LEFT PANEL (EDITOR) =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        
        # --- THANH ĐIỀU HƯỚNG PHÂN TRANG (PAGINATION BAR) ---
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("Hiển thị:", styleSheet=f"font-weight:bold; color:{Theme.TEXT_MUTED};"))
        
        self.group_combo = QComboBox()
        self.group_combo.addItems(["Tất cả", "1 dòng", "5 dòng", "10 dòng", "20 dòng", "50 dòng"])
        self.group_combo.currentIndexChanged.connect(self.change_group_size)
        page_layout.addWidget(self.group_combo)
        page_layout.addStretch()
        
        self.btn_prev = QPushButton("◀ Trước")
        self.btn_prev.setObjectName("btn_secondary")
        self.btn_prev.clicked.connect(self.prev_page)
        page_layout.addWidget(self.btn_prev)
        
        self.lbl_page = QLabel("1 / 1")
        self.lbl_page.setStyleSheet(f"font-weight:bold; color:{Theme.CYAN}; padding: 0 10px;")
        page_layout.addWidget(self.lbl_page)
        
        self.btn_next = QPushButton("Sau ▶")
        self.btn_next.setObjectName("btn_secondary")
        self.btn_next.clicked.connect(self.next_page)
        page_layout.addWidget(self.btn_next)
        
        left_layout.addLayout(page_layout)
        
        # --- BẢNG DỮ LIỆU (MODERN CARD-ROW DESIGN) ---
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["STT", "Bắt đầu", "Kết thúc", "Duration", "Nội dung"])
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 95)
        self.table.setColumnWidth(2, 95)
        self.table.setColumnWidth(3, 85)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # [S6-T5] Lột xác QTableWidget
        self.table.setShowGrid(False)  # Tắt lưới Excel
        self.table.verticalHeader().hide() # Ẩn cột số thứ tự mặc định
        self.table.verticalHeader().setDefaultSectionSize(40) # Mở rộng chiều cao hàng (Card feel)
        
        self.table.setStyleSheet(f"""
            QTableWidget {{ 
                background-color: {Theme.SURFACE}; 
                color: {Theme.TEXT_PRIMARY}; 
                border: 1px solid {Theme.BORDER}; 
                border-radius: 6px; 
                outline: none;
            }}
            QTableWidget::item {{ 
                border-bottom: 1px solid {Theme.BG_APP}; 
                padding: 4px; 
            }}
            QTableWidget::item:selected {{ 
                background-color: {Theme.SURFACE_SOFT}; 
                color: {Theme.CYAN}; 
                font-weight: bold;
                border-left: 3px solid {Theme.PRIMARY_PURPLE}; 
            }}
            QHeaderView::section {{ 
                background-color: {Theme.BG_APP}; 
                color: {Theme.TEXT_MUTED}; 
                font-weight: bold; 
                padding: 6px; 
                border: none; 
                border-bottom: 1px solid {Theme.BORDER}; 
            }}
        """)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.table.cellChanged.connect(self.on_table_edit)
        self.table.cellClicked.connect(self._on_row_selected)
        left_layout.addWidget(self.table)

        self.current_editor = CurrentSubtitleEditor(self)
        self.editor_group = self.current_editor
        self.inp_start = self.current_editor.start_edit
        self.inp_end = self.current_editor.end_edit
        self.lbl_duration = self.current_editor.lbl_duration
        self.txt_content = self.current_editor.text_edit
        self.current_editor.setEnabled(False)
        self.current_editor.changed.connect(self._apply_current_editor)
        left_layout.addWidget(self.current_editor)
        for widget in (
            self.current_editor.text_edit,
            self.current_editor.start_edit,
            self.current_editor.end_edit,
        ):
            if hasattr(widget, "setUndoRedoEnabled"):
                widget.setUndoRedoEnabled(False)
            elif hasattr(widget, "setUndoEnabled"):
                widget.setUndoEnabled(False)
            widget.installEventFilter(self)
        QShortcut(QKeySequence("Alt+Left"), self).activated.connect(self.select_previous)
        QShortcut(QKeySequence("Alt+Right"), self).activated.connect(self.select_next)

        # --- CỤM NÚT LƯU & DUYỆT BÊN DƯỚI ---
        btn_layout = QHBoxLayout()
        
        self.approve_btn = QPushButton("✅ Chốt Timing")
        self.approve_btn.setStyleSheet(f"background-color: {Theme.SUCCESS}; color: #0D111A; font-weight: bold; border-radius: 6px; padding: 8px 16px; border: none;")
        self.approve_btn.clicked.connect(self.approve_timing)
        
        self.save_draft_btn = QPushButton("📦 Lưu Draft")
        self.save_draft_btn.setObjectName("btn_secondary")
        self.save_draft_btn.clicked.connect(lambda: self.save_draft(silent=False))
        
        self.save_btn = QPushButton("💾 Lưu SRT")
        self.save_btn.setObjectName("btn_secondary")
        self.save_btn.clicked.connect(self.save_srt)
        self.save_draft_btn.clicked.connect(lambda: self.save_requested.emit("draft"))
        self.save_btn.clicked.connect(lambda: self.save_requested.emit("srt"))
        self.approve_btn.clicked.connect(self.timing_committed.emit)
        
        btn_layout.addWidget(self.approve_btn)
        btn_layout.addWidget(self.save_draft_btn)
        btn_layout.addWidget(self.save_btn)
        left_layout.addLayout(btn_layout)
        
        splitter.addWidget(left_panel)
        
        main_layout.addWidget(splitter)

    # ================= LOGIC ĐIỀU HƯỚNG PHÂN TRANG =================
    def update_empty_state(self):
        has_selection = 0 <= self.current_index < len(self.all_segments)
        self.editor_group.setEnabled(has_selection)
        if not has_selection:
            self.editor_group.setTitle("Current Subtitle: None")
            self._is_syncing_ui = True
            self.inp_start.clear()
            self.inp_end.clear()
            self.lbl_duration.setText("0.000 s")
            self.txt_content.clear()
            self._is_syncing_ui = False
        self.current_editor.btn_prev.setEnabled(self.current_index > 0)
        self.current_editor.btn_next.setEnabled(
            self.current_index < len(self.all_segments) - 1 and has_selection
        )

    def change_group_size(self):
        txt = self.group_combo.currentText()
        if "Tất cả" in txt:
            self.group_size = 0
        else:
            self.group_size = int(txt.split()[0])
        self.current_page = 0
        self.render_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.render_page()

    def next_page(self):
        max_page = max(0, (len(self.all_segments) - 1) // self.group_size) if self.group_size > 0 else 0
        if self.current_page < max_page:
            self.current_page += 1
            self.render_page()

    def render_page(self):
        self.is_rendering = True
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        
        if not self.all_segments:
            self.lbl_page.setText("1 / 1")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.table.blockSignals(False)
            self.is_rendering = False
            return

        if self.group_size == 0:
            start_idx, end_idx = 0, len(self.all_segments)
            self.lbl_page.setText("Tất cả")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
        else:
            start_idx = self.current_page * self.group_size
            end_idx = min(start_idx + self.group_size, len(self.all_segments))
            max_page = max(1, (len(self.all_segments) + self.group_size - 1) // self.group_size)
            self.lbl_page.setText(f"{self.current_page + 1} / {max_page}")
            self.btn_prev.setEnabled(self.current_page > 0)
            self.btn_next.setEnabled(self.current_page < max_page - 1)

        display_segments = self.all_segments[start_idx:end_idx]
        all_issues = SubtitleValidator.validate_all(self.all_segments, self._video_duration_ms())
        self.table.setRowCount(len(display_segments))

        for row, seg in enumerate(display_segments):
            global_index = start_idx + row
            start_text = self.ms_to_time_str(seg['start']) if isinstance(seg['start'], (int, float)) else seg['start']
            end_text = self.ms_to_time_str(seg['end']) if isinstance(seg['end'], (int, float)) else seg['end']
            item_id = QTableWidgetItem(str(seg.get('stt', global_index + 1)))
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
            issues = all_issues.get(global_index, [])
            if issues:
                has_error = any(issue.severity is Severity.ERROR for issue in issues)
                item_id.setText(f"{'❌' if has_error else '⚠'} {item_id.text()}")
                item_id.setToolTip("\n".join(f"- {issue.message}" for issue in issues))
            self.table.setItem(row, 0, item_id)
            self._set_table_item(row, 1, start_text)
            self._set_table_item(row, 2, end_text)
            try:
                duration_ms = self.time_str_to_ms(seg['end']) - self.time_str_to_ms(seg['start'])
                duration_text = f"{max(0, duration_ms) / 1000:.3f} s"
            except ValueError:
                duration_text = "--"
            self._set_table_item(row, 3, duration_text, readonly=True)
            
            display_text = seg['text'] if seg['text'].strip() else "[ Chưa có nội dung ]"
            text_item = QTableWidgetItem(display_text)
            
            if not seg['text'].strip():
                text_item.setForeground(QColor(Theme.TEXT_DISABLED))
                font = text_item.font()
                font.setItalic(True)
                text_item.setFont(font)
                
            self.table.setItem(row, 4, text_item)

        self.table.blockSignals(False)
        self.is_rendering = False
        self.update_empty_state()
        self._load_current_editor()
        self.sync_to_controller()

    def _video_duration_ms(self):
        try:
            player = getattr(self.window(), "video_player", None)
            getter = getattr(player, "get_video_duration_ms", None)
            if getter:
                return max(0, int(getter()))
            return max(0, int(player.player.duration())) if player is not None else 0
        except (AttributeError, TypeError, ValueError):
            return 0

    def _has_blocking_validation_errors(self):
        return any(
            issue.severity is Severity.ERROR
            for issues in SubtitleValidator.validate_all(self.all_segments, self._video_duration_ms()).values()
            for issue in issues
        )

    def _set_table_item(self, row, col, text, readonly=False):
        item = QTableWidgetItem(str(text))
        if readonly or col in (0, 3):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if col in (0, 1, 2, 3):
            item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)

    def sync_to_controller(self):
        data = []
        for seg in self.all_segments:
            start_ms = self.time_str_to_ms(seg['start'])
            end_ms = self.time_str_to_ms(seg['end'])
            raw_text = seg['text']
            if raw_text == "[ Chưa có nội dung ]": raw_text = ""
            try: stt = int(seg['stt'])
            except: stt = 0
            data.append((start_ms, end_ms, raw_text, stt))
        self.live_edit_applied.emit(data)

    def on_table_edit(self, row, col):
        if self.is_rendering or self.undo_manager is None: return
        
        abs_idx = self.current_page * self.group_size + row if self.group_size > 0 else row
        if abs_idx >= len(self.all_segments): return

        segment = self.all_segments[abs_idx]
        old_start = segment['start']
        old_end = segment['end']

        it_stt = self.table.item(row, 0)
        it_start = self.table.item(row, 1)
        it_end = self.table.item(row, 2)
        it_text = self.table.item(row, 4)

        if it_stt and it_start and it_end and it_text:
            try:
                start_ms = self.time_str_to_ms(it_start.text())
                end_ms = self.time_str_to_ms(it_end.text())
                if start_ms >= end_ms:
                    raise ValueError("Start phải nhỏ hơn End")
            except ValueError:
                # [S6-FIX] Dùng Toast Error thay cho QMessageBox
                Toast.show_error(self.window(), "Timestamp không hợp lệ (Chuẩn: HH:MM:SS,mmm)")
                self.table.blockSignals(True)
                it_start.setText(self._display_time_value(old_start))
                it_end.setText(self._display_time_value(old_end))
                self.table.blockSignals(False)
                return

            new_start, new_end = it_start.text(), it_end.text()
            new_start = self._coerce_time_value(old_start, new_start)
            new_end = self._coerce_time_value(old_end, new_end)
            raw_text = it_text.text()
            if raw_text == "[ Chưa có nội dung ]": raw_text = ""
            if new_start != old_start or new_end != old_end:
                self.undo_manager.push(
                    EditTimingCommand(
                        abs_idx, old_start, old_end, new_start, new_end, self.all_segments
                    )
                )

            if segment['text'] != raw_text:
                self.undo_manager.push(
                    EditTextCommand(abs_idx, segment['text'], raw_text, self.all_segments)
                )

    def _on_row_selected(self, row, _column):
        abs_idx = self.current_page * self.group_size + row if self.group_size > 0 else row
        if 0 <= abs_idx < len(self.all_segments):
            self.select_segment(abs_idx)

    def select_previous(self):
        if self.current_index > 0:
            self.select_segment(self.current_index - 1)

    def select_next(self):
        if self.current_index < len(self.all_segments) - 1:
            self.select_segment(self.current_index + 1)

    def select_segment(self, index: int):
        if not (0 <= index < len(self.all_segments)):
            return
        if self.selection_controller and not self._is_syncing_ui:
            self.selection_controller.select(
                index, self.all_segments[index].get("id"), SelectionSource.EDITOR
            )
            return
        self._select_segment_ui(index)

    def sync_selection(self, index, segment_id, source=None):
        if 0 <= index < len(self.all_segments):
            self._is_syncing_ui = True
            self._select_segment_ui(index)
            self._is_syncing_ui = False
        else:
            self.current_index = -1
            self.update_empty_state()

    def _select_segment_ui(self, index: int):
        self.current_index = index
        seg = self.all_segments[index]
        self.current_editor.setEnabled(True)
        self.current_editor.setTitle(f"Current Subtitle: #{index + 1}")
        self.current_editor.set_values(seg["start"], seg["end"], seg["text"])
        self.table.blockSignals(True)
        row = index % self.group_size if self.group_size > 0 else index
        self.table.selectRow(row)
        self.table.blockSignals(False)

    def sync_playback_highlight(self, absolute_index: int):
        """Select the subtitle currently playing without issuing a seek."""
        if not (0 <= absolute_index < len(self.all_segments)):
            return
        if self.selection_controller and not self._is_syncing_ui:
            self.selection_controller.select(
                absolute_index, self.all_segments[absolute_index].get("id"), SelectionSource.PLAYBACK
            )
            return
        self.current_index = absolute_index
        items_per_page = self.group_size or len(self.all_segments)
        if items_per_page > 0 and items_per_page != len(self.all_segments):
            target_page = absolute_index // items_per_page
            if target_page != self.current_page:
                self.current_page = target_page
                self.render_page()
            row_in_table = absolute_index % items_per_page
        else:
            row_in_table = absolute_index
        self._is_syncing_ui = True
        self.table.selectRow(row_in_table)
        self._load_current_editor()
        self.update_empty_state()
        self._is_syncing_ui = False

    def _load_current_editor(self):
        if 0 <= self.current_index < len(self.all_segments):
            seg = self.all_segments[self.current_index]
            self.current_editor.setEnabled(True)
            self.current_editor.setTitle(f"Current Subtitle: #{self.current_index + 1}")
            self.current_editor.set_values(seg["start"], seg["end"], seg["text"])

    def _apply_current_editor(self, values=None):
        if self._is_syncing_ui or self.current_index < 0 or self.undo_manager is None:
            return
        if values is None:
            values = {
                "start": self.inp_start.text(),
                "end": self.inp_end.text(),
                "text": self.txt_content.toPlainText(),
            }
        abs_idx = self.current_index
        if not (0 <= abs_idx < len(self.all_segments)):
            return
        segment = self.all_segments[abs_idx]
        try:
            start_ms = self.time_str_to_ms(values["start"])
            end_ms = self.time_str_to_ms(values["end"])
            if start_ms < 0 or end_ms < 0 or start_ms >= end_ms:
                raise ValueError
        except ValueError:
            self._is_syncing_ui = True
            self.inp_start.setText(self._display_time_value(segment["start"]))
            self.inp_end.setText(self._display_time_value(segment["end"]))
            self._is_syncing_ui = False
            return

        new_start = self._coerce_time_value(segment["start"], values["start"])
        new_end = self._coerce_time_value(segment["end"], values["end"])
        if new_start != segment["start"] or new_end != segment["end"]:
            self.undo_manager.push(
                EditTimingCommand(
                    abs_idx,
                    segment["start"],
                    segment["end"],
                    new_start,
                    new_end,
                    self.all_segments,
                )
            )
        if values["text"] != segment["text"]:
            self.undo_manager.push(
                EditTextCommand(abs_idx, segment["text"], values["text"], self.all_segments)
            )

    @staticmethod
    def _coerce_time_value(old_value, value):
        if isinstance(old_value, (int, float)) and not isinstance(old_value, bool):
            return time_str_to_ms(value)
        return value

    @staticmethod
    def _display_time_value(value):
        return ms_to_time_str(value) if isinstance(value, (int, float)) else str(value)

    def trigger_delete(self):
        if self.current_index < 0 or self.undo_manager is None:
            return
        self.undo_manager.push(DeleteCommand(self.current_index, self.all_segments))

    def trigger_merge(self):
        if (
            self.current_index < 0
            or self.current_index >= len(self.all_segments) - 1
            or self.undo_manager is None
        ):
            return
        self.undo_manager.push(MergeCommand(self.current_index, self.all_segments))

    def trigger_split(self, playhead_ms: int):
        if self.current_index < 0 or self.undo_manager is None:
            return
        segment = self.all_segments[self.current_index]
        start_ms = self.time_str_to_ms(segment["start"])
        end_ms = self.time_str_to_ms(segment["end"])
        if start_ms < playhead_ms < end_ms:
            self.undo_manager.push(
                SplitCommand(self.current_index, playhead_ms, self.all_segments)
            )

    def trigger_add(self, playhead_ms: int, video_duration_ms: int):
        if self.undo_manager is None:
            return
        start_ms = max(0, int(playhead_ms))
        end_ms = min(start_ms + 2000, int(video_duration_ms))
        insert_idx = self.current_index + 1 if self.current_index >= 0 else len(self.all_segments)
        if insert_idx < len(self.all_segments):
            next_start = self.time_str_to_ms(self.all_segments[insert_idx]["start"])
            end_ms = min(end_ms, next_start)
        if end_ms <= start_ms:
            return
        self.undo_manager.push(AddCommand(insert_idx, start_ms, end_ms, self.all_segments))

    def _undo_manager(self):
        if self.undo_manager is not None:
            return self.undo_manager
        window = self.window()
        timeline = getattr(window, "timeline_widget", None)
        manager = getattr(timeline, "undo_manager", None)
        if manager is None:
            controller = getattr(window, "timeline_controller", None)
            manager = getattr(controller, "undo_manager", None)
        return manager

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and self.current_index >= 0:
            modifiers = event.modifiers()
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter) and modifiers & Qt.ControlModifier:
                self.setFocus()
                return True
            manager = self._undo_manager()
            if manager is not None and key == Qt.Key_Z and modifiers & Qt.ControlModifier:
                (manager.redo if modifiers & Qt.ShiftModifier else manager.undo)()
                return True
            if manager is not None and key == Qt.Key_Y and modifiers & Qt.ControlModifier:
                manager.redo()
                return True
        return super().eventFilter(obj, event)

    def highlight_row_by_stt(self, stt):
        target_idx = -1
        for i, seg in enumerate(self.all_segments):
            if str(seg['stt']).strip() == str(stt).strip():
                target_idx = i
                break
                
        if target_idx == -1: return

        if self.group_size > 0:
            target_page = target_idx // self.group_size
            if target_page != self.current_page:
                self.current_page = target_page
                self.render_page()

        row_in_table = target_idx % self.group_size if self.group_size > 0 else target_idx
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.selectRow(row_in_table)
        
        item = self.table.item(row_in_table, 0)
        if item:
            self.table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            
        self.table.blockSignals(False)

    def clear_highlight(self):
        self.table.clearSelection()

    # ================= LOGIC FILE I/O =================
    def ms_to_time_str(self, ms):
        return ms_to_time_str(ms)

    def time_str_to_ms(self, time_str):
        value = time_str_to_ms(time_str)
        if value < 0:
            raise ValueError("Sai định dạng HH:MM:SS,mmm")
        return value

    def load_srt_file(self, srt_path):
        if not srt_path or not os.path.exists(srt_path):
            return
        with open(srt_path, "r", encoding="utf-8", errors="ignore") as handle:
            self.all_segments = parse_srt_content(handle.read())
        self.srt_path = srt_path
        self.current_page = 0
        self.render_page()
        if self.undo_manager:
            self.undo_manager.clear()
        if self.selection_controller:
            self.selection_controller.clear_selection(SelectionSource.PROGRAMMATIC)
        self.update_draft_progress()

    def save_srt(self):
        from PySide6.QtWidgets import QFileDialog
        import os

        if self._has_blocking_validation_errors():
            QMessageBox.critical(
                self,
                "Lỗi Phụ Đề",
                "Phụ đề đang chứa lỗi thời gian nghiêm trọng (❌). Vui lòng sửa trước khi xuất file.",
            )
            return
        
        path = self.srt_path
        if not path or not path.endswith('.srt'):
            base = os.path.splitext(path)[0] if path else "Project"
            default_name = f"{base}.srt"
            path, _ = QFileDialog.getSaveFileName(self, "Xuất file SRT", default_name, "SubRip Subtitle (*.srt)")
            if not path: return
            
        from core.export.export_service import generate_srt_content
            
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(generate_srt_content(self.all_segments))
                
            self.srt_path = path 
            # [S6-FIX] Cắt ngắn đường dẫn và hiện Toast
            file_name = os.path.basename(path)
            Toast.show_success(self.window(), f"Đã xuất SRT: {file_name}")
            self.srt_saved.emit(self.srt_path)
        except Exception as e:
            Toast.show_error(self.window(), f"Lỗi lưu SRT: {e!s}")

    def save_draft(self, filepath=None, silent=False):
        import json
        import os
        from PySide6.QtWidgets import QFileDialog
        
        explicit_path = bool(filepath)
        path = filepath or self.srt_path
        
        if silent and not explicit_path:
            if not path:
                path = "Project.ai-subtitle-draft"
            elif not path.endswith('.ai-subtitle-draft'):
                base = os.path.splitext(path)[0]
                path = f"{base}.ai-subtitle-draft"
        else:
            base = os.path.splitext(path)[0] if path else "Project"
            default_name = f"{base}.ai-subtitle-draft"
            path, _ = QFileDialog.getSaveFileName(self, "Lưu Timing Artifact", default_name, "AI Subtitle Draft (*.ai-subtitle-draft)")
            
        if not path: return
        
        try:
            if not getattr(self, "project_service", None):
                return
            self.project_service.save_draft(path, self.all_segments)
            if self.undo_manager:
                self.undo_manager.mark_saved()
                
            self.srt_path = path
            
            if not silent:
                file_name = os.path.basename(path)
                Toast.show_success(self.window(), f"Đã bảo lưu Draft: {file_name}")
        except Exception as e:
            if not silent: 
                Toast.show_error(self.window(), f"Lỗi lưu Draft: {e!s}")

    def load_draft_file(self, draft_path):
        if not getattr(self, "project_service", None) or not draft_path:
            return
        data = self.project_service.load_draft(draft_path)
        self.srt_path = draft_path
        self.all_segments = data.get("segments", [])
        self.current_page = 0
        self.render_page()
        if self.undo_manager:
            self.undo_manager.clear()
        if self.selection_controller:
            self.selection_controller.clear_selection(SelectionSource.PROGRAMMATIC)
        self.update_draft_progress()

    def on_row_double_clicked(self, row, column):
        start_item = self.table.item(row, 1)
        if start_item:
            try:
                ms = self.time_str_to_ms(start_item.text())
                self.seek_requested.emit(ms)
            except ValueError:
                pass

    def approve_timing(self):
        if not self.all_segments:
            return
            
        for seg in self.all_segments:
            seg['status'] = 'final'
            
        Toast.show_success(self.window(), "Đã chốt Timing! Sẵn sàng tạo phụ đề.")

    def update_draft_progress(self):
        if not self.all_segments:
            self.next_empty_idx = -1
            return

        self.next_empty_idx = -1
        for i, seg in enumerate(self.all_segments):
            if not seg.get('text', '').strip() or seg.get('status') == 'timing_only':
                self.next_empty_idx = i
                break
