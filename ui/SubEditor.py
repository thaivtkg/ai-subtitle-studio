import copy
import json
import os
import re
import uuid

from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractItemDelegate,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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
from core.subtitle_editing.subtitle_time_range_filter import (
    TimeRangeValidationError,
    indices_for_time_range,
    parse_minute_range,
)
from core.export.subtitle_parser import parse_srt_content


def ms_to_time_str(ms: int) -> str:
    """Format milliseconds as the canonical SRT timestamp."""
    s, ms = divmod(max(0, int(ms)), 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def time_str_to_ms(time_str: str) -> int:
    """Parse SRT/VTT timestamp with optional hours and dot/comma decimal; return -1 when invalid."""
    if isinstance(time_str, (int, float)) and not isinstance(time_str, bool):
        return int(time_str)
    match = re.fullmatch(r"^(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})$", str(time_str).strip())
    if not match:
        return -1
    h_str, m_str, s_str, ms_str = match.groups()
    h = int(h_str) if h_str is not None else 0
    m, s, ms = int(m_str), int(s_str), int(ms_str.ljust(3, '0'))
    if m >= 60 or s >= 60:
        return -1
    return (h * 3600 + m * 60 + s) * 1000 + ms


class CurrentSubtitleEditor(QWidget):
    changed = Signal(dict)
    scan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self.lbl_title = QLabel("#--")
        self.lbl_title.setStyleSheet(f"font-weight: bold; color: {Theme.CYAN}; min-width: 32px;")
        layout.addWidget(self.lbl_title)
        
        self.start_edit = QLineEdit()
        self.start_edit.setFixedWidth(95)
        self.start_edit.setAlignment(Qt.AlignCenter)
        self.start_edit.setPlaceholderText("00:00:00,000")
        layout.addWidget(self.start_edit)

        arrow_lbl = QLabel("→")
        arrow_lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-weight: bold;")
        layout.addWidget(arrow_lbl)

        self.end_edit = QLineEdit()
        self.end_edit.setFixedWidth(95)
        self.end_edit.setAlignment(Qt.AlignCenter)
        self.end_edit.setPlaceholderText("00:00:00,000")
        layout.addWidget(self.end_edit)

        self.lbl_duration = QLabel("0.000s")
        self.lbl_duration.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; min-width: 42px;")
        layout.addWidget(self.lbl_duration)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Nội dung phụ đề...")
        self.text_edit.setFixedHeight(30)
        layout.addWidget(self.text_edit, stretch=1)

        # Hidden text_original for backward compatibility
        self.text_original = QTextEdit(self)
        self.text_original.hide()


        self.btn_scan = QPushButton("Quét lại")
        self.btn_scan.setObjectName("btn_secondary")
        self.btn_scan.setToolTip("Nhận diện lại âm thanh đoạn này")
        self.btn_scan.setFixedHeight(26)
        self.btn_scan.clicked.connect(self.scan_requested.emit)
        layout.addWidget(self.btn_scan)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedSize(26, 26)
        self.btn_prev.setObjectName("btn_secondary")
        self.btn_prev.setToolTip("Dòng trước (Alt+Left)")
        self.btn_prev.clicked.connect(self._previous_requested)
        layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton(">")
        self.btn_next.setFixedSize(26, 26)
        self.btn_next.setObjectName("btn_secondary")
        self.btn_next.setToolTip("Dòng sau (Alt+Right)")
        self.btn_next.clicked.connect(self._next_requested)
        layout.addWidget(self.btn_next)
        
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        for widget in (self.start_edit, self.end_edit):
            widget.editingFinished.connect(self._emit_changed)
        self.text_edit.textChanged.connect(self._schedule_emit)
        self._debounce.timeout.connect(self._emit_changed)

    def set_time(self, start_ms, end_ms):
        start = ms_to_time_str(start_ms)
        end = ms_to_time_str(end_ms)
        for widget, value in ((self.start_edit, start), (self.end_edit, end)):
            widget.blockSignals(True)
            widget.setText(value)
            widget.blockSignals(False)
        self.lbl_duration.setText(f"{max(0, end_ms - start_ms) / 1000:.3f} s")

    def set_values(self, start, end, text, original_text=""):
        start = ms_to_time_str(start) if isinstance(start, (int, float)) else str(start)
        end = ms_to_time_str(end) if isinstance(end, (int, float)) else str(end)
        for widget, value in ((self.start_edit, start), (self.end_edit, end)):
            widget.blockSignals(True)
            widget.setText(value)
            widget.blockSignals(False)
            
        self.text_original.blockSignals(True)
        self.text_original.setPlainText(original_text)
        self.text_original.blockSignals(False)
        
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self.text_edit.blockSignals(False)
        
        start_ms = time_str_to_ms(start)
        end_ms = time_str_to_ms(end)
        self.lbl_duration.setText(f"{max(0, end_ms - start_ms) / 1000:.3f} s")

    def setTitle(self, title: str):
        if ":" in title:
            val = title.split(":")[-1].strip()
            self.lbl_title.setText(val if val != "None" else "Current Subtitle: None")
        else:
            self.lbl_title.setText(title)

    def _previous_requested(self):
        self.parent().select_previous() if self.parent() else None

    def _next_requested(self):
        self.parent().select_next() if self.parent() else None

    def _schedule_emit(self):
        self._debounce.start()

    def commit_pending_edit(self):
        if self._debounce.isActive():
            self._debounce.stop()
            self._emit_changed()

    def _emit_changed(self):
        self.changed.emit({"start": self.start_edit.text(), "end": self.end_edit.text(), "text": self.text_edit.toPlainText()})


class SubtitleEditorWidget(QWidget):
    COL_STT = 0
    COL_START = 1
    COL_END = 2
    COL_DUR = 3
    COL_TEXT = 4
    COL_TRANSLATION = 4
    COL_ORIGINAL = None

    request_tm_suggestion = Signal(str)  # original_text
    commit_segment = Signal(str, str, str, str, list)  # original, translated, prev, next, qc_flags
    request_ai_translate = Signal(list)
    segment_scan_requested = Signal(str, int, int) # selected indices

    seek_requested = Signal(int)
    segment_focused = Signal(int, int)
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
        # Display-only time filter. all_segments remains the canonical full source.
        # The filter is expressed as a half-open millisecond interval [start, end).
        self._active_time_range_ms = None
        self._visible_source_indices = []
        self._current_page_source_indices = []
        self.ripple_shift_enabled = True
        self._is_updating_filter = False
        self.is_rendering = False
        self._is_syncing_ui = False
        
        self._tm_debounce = QTimer(self)
        self._tm_debounce.setSingleShot(True)
        self._tm_debounce.setInterval(300)
        self._tm_debounce.timeout.connect(self._emit_tm_suggestion)


        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        # ================= LỚP 1: LEFT PANEL (EDITOR) =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        # --- THANH ĐIỀU HƯỚNG PHÂN TRANG (PAGINATION BAR) ---
        page_layout = QHBoxLayout()
        page_layout.setContentsMargins(4, 2, 4, 2)
        page_layout.addWidget(QLabel("Hiển thị:", styleSheet=f"font-weight:bold; color:{Theme.TEXT_MUTED};"))
        
        self.group_combo = QComboBox()
        self.group_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.group_combo.setMinimumWidth(100)
        self.group_combo.addItems(["Tất cả", "1 dòng", "5 dòng", "10 dòng", "20 dòng", "50 dòng"])
        self.group_combo.currentIndexChanged.connect(self.change_group_size)
        page_layout.addWidget(self.group_combo)

        page_layout.addWidget(QLabel("Phút bắt đầu:"))
        self.range_start_input = QLineEdit()
        self.range_start_input.setObjectName("subtitleTimeRangeStart")
        self.range_start_input.setPlaceholderText("0")
        self.range_start_input.setToolTip("Thời điểm bắt đầu lọc, tính bằng phút. Có thể nhập số thập phân, ví dụ 1.5.")
        self.range_start_input.setAlignment(Qt.AlignCenter)
        self.range_start_input.setFixedWidth(72)
        self.range_start_input.textChanged.connect(self._on_time_range_input_changed)
        self.range_start_input.returnPressed.connect(self.apply_time_filter)
        page_layout.addWidget(self.range_start_input)

        page_layout.addWidget(QLabel("Phút kết thúc:"))
        self.range_end_input = QLineEdit()
        self.range_end_input.setObjectName("subtitleTimeRangeEnd")
        self.range_end_input.setPlaceholderText("5")
        self.range_end_input.setToolTip("Thời điểm kết thúc lọc, tính bằng phút; phải lớn hơn phút bắt đầu.")
        self.range_end_input.setAlignment(Qt.AlignCenter)
        self.range_end_input.setFixedWidth(72)
        self.range_end_input.textChanged.connect(self._on_time_range_input_changed)
        self.range_end_input.returnPressed.connect(self.apply_time_filter)
        page_layout.addWidget(self.range_end_input)

        self.btn_apply_range = QPushButton("Áp dụng")
        self.btn_apply_range.setObjectName("btn_secondary")
        self.btn_apply_range.setToolTip("Chỉ hiển thị phụ đề giao với khoảng thời gian đã nhập.")
        self.btn_apply_range.clicked.connect(self.apply_time_filter)
        self.btn_apply_range.hide()

        self.btn_clear_range = QPushButton("Xóa lọc")
        self.btn_clear_range.setObjectName("btn_secondary")
        self.btn_clear_range.clicked.connect(self.clear_time_filter)
        self.btn_clear_range.hide()

        self.lbl_range_count = QLabel("0 / 0 phụ đề")
        self.lbl_range_count.setStyleSheet(f"color:{Theme.TEXT_MUTED}; font-size:11px;")
        self.lbl_range_count.setToolTip("Số phụ đề đang hiển thị / tổng số phụ đề trong dữ liệu chuẩn.")
        page_layout.addWidget(self.lbl_range_count)
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

        self.lbl_range_validation = QLabel("")
        self.lbl_range_validation.setObjectName("subtitleTimeRangeValidation")
        self.lbl_range_validation.setStyleSheet(
            "color: #ff7373; font-size: 11px; padding-left: 8px;"
        )
        self.lbl_range_validation.setWordWrap(True)
        self.lbl_range_validation.hide()
        left_layout.addWidget(self.lbl_range_validation)
        
        # --- BẢNG DỮ LIỆU (MODERN CARD-ROW DESIGN, EDGE-TO-EDGE) ---
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["STT", "Bắt đầu", "Kết thúc", "Duration", "Nội dung phụ đề"])
        from PySide6.QtWidgets import QHeaderView
        self.table.horizontalHeader().setSectionResizeMode(self.COL_STT, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_START, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_END, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_DUR, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_TEXT, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        self.table.setShowGrid(False)  # Tắt lưới Excel
        self.table.verticalHeader().hide() # Ẩn cột số thứ tự mặc định
        self.table.verticalHeader().setDefaultSectionSize(36) # Chiều cao hàng vừa vặn
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Bắt buộc giãn tối đa
        

        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.table.cellChanged.connect(self.on_table_edit)
        self.table.cellClicked.connect(self._on_row_selected)
        self.table.currentCellChanged.connect(self._on_table_current_cell_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        left_layout.addWidget(self.table, stretch=1)

        self.current_editor = CurrentSubtitleEditor(self)
        self.editor_group = self.current_editor
        self.inp_start = self.current_editor.start_edit
        self.inp_end = self.current_editor.end_edit
        self.lbl_duration = self.current_editor.lbl_duration
        self.txt_content = self.current_editor.text_edit
        self.current_editor.setEnabled(False)
        self.current_editor.changed.connect(self._apply_current_editor)
        self.current_editor.scan_requested.connect(self._on_current_editor_scan_requested)
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
        self.shortcut_prev = QShortcut(QKeySequence("Alt+Left"), self)
        self.shortcut_prev.setObjectName("previous_subtitle")
        self.shortcut_prev.setProperty("help_label", "Previous Subtitle")
        self.shortcut_prev.setProperty("help_context", "Timeline")
        self.shortcut_prev.activated.connect(self.select_previous)

        self.shortcut_next = QShortcut(QKeySequence("Alt+Right"), self)
        self.shortcut_next.setObjectName("next_subtitle")
        self.shortcut_next.setProperty("help_label", "Next Subtitle")
        self.shortcut_next.setProperty("help_context", "Timeline")
        self.shortcut_next.activated.connect(self.select_next)

        # --- CÁC NÚT HÀNH ĐỘNG (Sẽ được Gui.py gắn vào Timeline Toolbar) ---
        self.ai_translate_btn = QPushButton("🪄 AI Translate")
        self.ai_translate_btn.setProperty("variant", "primary")
        self.ai_translate_btn.setObjectName("btn_primary")
        self.ai_translate_btn.clicked.connect(self._on_ai_translate_clicked)
        self.ai_translate_btn.hide()
        
        from PySide6.QtWidgets import QMenu
        self.fix_overlap_btn = QPushButton("⚡ Chồng lấn ▾")
        self.fix_overlap_btn.setObjectName("btn_secondary")
        self.fix_overlap_btn.setProperty("variant", "secondary")
        self.fix_overlap_btn.setEnabled(False)
        self.fix_overlap_menu = QMenu(self)
        self.action_fix_keep_prev = self.fix_overlap_menu.addAction("Giữ Sub trước, rút Sub sau")
        self.action_fix_keep_next = self.fix_overlap_menu.addAction("Giữ Sub sau, rút Sub trước")
        self.fix_overlap_menu.addSeparator()
        self.action_fix_all = self.fix_overlap_menu.addAction("Sửa tất cả chồng lấn")
        self.fix_overlap_btn.setMenu(self.fix_overlap_menu)
        
        self.action_fix_keep_prev.triggered.connect(lambda: self.fix_overlaps(mode="keep_prev", all_overlaps=False))
        self.action_fix_keep_next.triggered.connect(lambda: self.fix_overlaps(mode="keep_next", all_overlaps=False))
        self.action_fix_all.triggered.connect(lambda: self.fix_overlaps(mode="keep_prev", all_overlaps=True))

        self.approve_btn = QPushButton("✅ Chốt Timing")
        self.approve_btn.setProperty("variant", "success")
        self.approve_btn.clicked.connect(self.approve_timing)
        
        self.save_draft_btn = QPushButton("📦 Lưu Draft")
        self.save_draft_btn.setObjectName("btn_secondary")
        self.save_draft_btn.setProperty("variant", "secondary")
        self.save_draft_btn.clicked.connect(lambda: self.save_draft(silent=False))
        
        self.save_btn = QPushButton("💾 Lưu SRT")
        self.save_btn.setObjectName("btn_secondary")
        self.save_btn.setProperty("variant", "secondary")
        self.save_btn.clicked.connect(self.save_srt)
        self.save_draft_btn.clicked.connect(lambda: self.save_requested.emit("draft"))
        self.save_btn.clicked.connect(lambda: self.save_requested.emit("srt"))
        self.approve_btn.clicked.connect(self.timing_committed.emit)

        self.reanalyze_audio_style_btn = QPushButton("🔄 Quét Audio")
        self.reanalyze_audio_style_btn.setObjectName("btn_secondary")
        self.reanalyze_audio_style_btn.setProperty("variant", "secondary")
        self.reanalyze_audio_style_btn.setToolTip("Quét lại Style phụ đề theo năng lượng âm thanh")
        self.reanalyze_audio_style_btn.clicked.connect(self._on_reanalyze_audio_style_clicked)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(left_panel, stretch=1)

    def _on_ai_translate_clicked(self):
        # Identify selected segments
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            # Without an explicit selection, operate on the current view. With no
            # active filter this still means every subtitle, as before.
            indices = self._get_visible_source_indices()
        else:
            indices = set()
            for r in selected_ranges:
                for i in range(r.topRow(), r.bottomRow() + 1):
                    # Resolve the displayed row through its stable segment ID.
                    actual_idx = self._source_index_for_row(i)
                    if 0 <= actual_idx < len(self.all_segments):
                        indices.add(actual_idx)
            indices = sorted(list(indices))
            
        if not indices:
            return
            
        # Emit signal to Gui.py to handle translation
        self.request_ai_translate.emit(indices)

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

    def _get_visible_source_indices(self):
        """Return source indices matching the active time interval without slicing data."""
        return indices_for_time_range(self.all_segments, self._active_time_range_ms)

    def _time_range_duration_limit_ms(self):
        duration_ms = self._video_duration_ms()
        return duration_ms if duration_ms > 0 else None

    def _on_time_range_input_changed(self, *_):
        """Auto-apply valid end minute filter, auto-clear when both are blank."""
        if getattr(self, "_is_updating_filter", False):
            return

        start_text = self.range_start_input.text().strip()
        end_text = self.range_end_input.text().strip()

        # Both inputs blank: auto-clear filter
        if not start_text and not end_text:
            self.lbl_range_validation.clear()
            self.lbl_range_validation.hide()
            if self._active_time_range_ms is not None:
                self._is_updating_filter = True
                try:
                    self._active_time_range_ms = None
                    self.current_page = 0
                    self.render_page()
                finally:
                    self._is_updating_filter = False
            return

        # If end_text is blank, user is still typing start
        if not end_text:
            self.lbl_range_validation.clear()
            self.lbl_range_validation.hide()
            return

        # If start input changed while no filter is active, wait for end input
        if self.sender() is self.range_start_input and self._active_time_range_ms is None:
            return

        effective_start = start_text if start_text else "0"
        try:
            time_range = parse_minute_range(
                effective_start,
                end_text,
                max_duration_ms=self._time_range_duration_limit_ms(),
            )
        except TimeRangeValidationError as exc:
            self.lbl_range_validation.setStyleSheet(
                "color: #ff7373; font-size: 11px; padding-left: 8px;"
            )
            self.lbl_range_validation.setText(str(exc))
            self.lbl_range_validation.show()
        else:
            self.lbl_range_validation.clear()
            self.lbl_range_validation.hide()
            new_range = (time_range.start_ms, time_range.end_ms) if time_range is not None else None
            if self._active_time_range_ms != new_range:
                self._is_updating_filter = True
                try:
                    self._active_time_range_ms = new_range
                    self.current_page = 0
                    self.render_page()
                finally:
                    self._is_updating_filter = False

    def apply_time_filter(self):
        """Validate both minute fields before committing a display-only time filter."""
        start_text = self.range_start_input.text().strip()
        end_text = self.range_end_input.text().strip()
        if not start_text and not end_text:
            self.clear_time_filter()
            return

        try:
            time_range = parse_minute_range(
                start_text,
                end_text,
                max_duration_ms=self._time_range_duration_limit_ms(),
            )
        except TimeRangeValidationError as exc:
            self.lbl_range_validation.setStyleSheet(
                "color: #ff7373; font-size: 11px; padding-left: 8px;"
            )
            self.lbl_range_validation.setText(str(exc))
            self.lbl_range_validation.show()
            Toast.show_error(self.window(), str(exc))
            return

        self._active_time_range_ms = (
            (time_range.start_ms, time_range.end_ms) if time_range is not None else None
        )
        self.lbl_range_validation.clear()
        self.lbl_range_validation.hide()
        self.current_page = 0
        self.render_page()

    def clear_time_filter(self):
        self.range_start_input.clear()
        self.range_end_input.clear()
        self._active_time_range_ms = None
        self.lbl_range_validation.clear()
        self.lbl_range_validation.hide()
        self.current_page = 0
        self.render_page()

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
        visible_count = len(self._get_visible_source_indices())
        max_page = max(0, (visible_count - 1) // self.group_size) if self.group_size > 0 else 0
        if self.current_page < max_page:
            self.current_page += 1
            self.render_page()

    def _source_index_for_row(self, row: int) -> int:
        """Map a visible table row to the canonical source index, preferring stable ID."""
        if not (0 <= row < len(self._current_page_source_indices)):
            return -1
        item = self.table.item(row, self.COL_STT)
        source_index = self._current_page_source_indices[row]
        if item is None:
            return source_index if 0 <= source_index < len(self.all_segments) else -1

        segment_id = item.data(Qt.UserRole)
        stored_index = item.data(Qt.UserRole + 1)
        if segment_id is not None:
            if (isinstance(stored_index, int) and 0 <= stored_index < len(self.all_segments)
                    and self.all_segments[stored_index].get("id") == segment_id):
                return stored_index
            for idx, seg in enumerate(self.all_segments):
                if seg.get("id") == segment_id:
                    return idx
            return -1
        if isinstance(stored_index, int) and 0 <= stored_index < len(self.all_segments):
            return stored_index
        return source_index if 0 <= source_index < len(self.all_segments) else -1

    def _get_row_by_source_index(self, source_index: int) -> int:
        try:
            visible_position = self._visible_source_indices.index(source_index)
        except ValueError:
            return -1
        page = visible_position // self.group_size if self.group_size > 0 else 0
        if page != self.current_page:
            return -1
        return visible_position % self.group_size if self.group_size > 0 else visible_position

    def _get_row_by_id(self, segment_id: str) -> int:
        if segment_id is None:
            return -1
        for source_index, seg in enumerate(self.all_segments):
            if seg.get("id") == segment_id:
                return self._get_row_by_source_index(source_index)
        return -1

    def _set_table_item(self, row: int, col: int, text: str):
        item = self.table.item(row, col)
        if item:
            item.setText(text)

    def on_timeline_live_edit(self, changes: list, edit_mode: object, *args):
        """Cập nhật UI thời gian thực khi người dùng đang kéo thả trên Timeline, cập nhật all_segments nhưng KHÔNG tạo Undo."""
        if not self.all_segments:
            return
            
        current_seg_id = None
        if 0 <= self.current_index < len(self.all_segments):
            current_seg_id = self.all_segments[self.current_index].get("id")
            
        
        for seg_id, new_start_ms, new_end_ms in changes:
            # 1. Cập nhật bảng CurrentSubtitleEditor
            if current_seg_id == seg_id:
                blocker = self.current_editor.blockSignals(True)
                self.current_editor.set_time(new_start_ms, new_end_ms)
                self.current_editor.blockSignals(False)

            # 2. Cập nhật all_segments và QTableWidget
            abs_idx = -1
            for i, seg in enumerate(self.all_segments):
                if seg.get("id") == seg_id:
                    abs_idx = i
                    break
            
            if abs_idx >= 0:
                self.all_segments[abs_idx]["start"] = ms_to_time_str(new_start_ms)
                self.all_segments[abs_idx]["end"] = ms_to_time_str(new_end_ms)
                
                page = abs_idx // self.group_size if self.group_size > 0 else 0
                if self.group_size == 0 or page == self.current_page:
                    row = abs_idx % self.group_size if self.group_size > 0 else abs_idx
                    self._set_table_item(row, self.COL_START, ms_to_time_str(new_start_ms))
                    self._set_table_item(row, self.COL_END, ms_to_time_str(new_end_ms))
                    dur_ms = max(0, new_end_ms - new_start_ms)
                    self._set_table_item(row, self.COL_DUR, f"{dur_ms / 1000:.3f} s")

    def render_page(self):
        self.is_rendering = True
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        if not self.all_segments:
            self._visible_source_indices = []
            self._current_page_source_indices = []
            self.current_index = -1
            self.lbl_page.setText("1 / 1")
            self.lbl_range_count.setText("0 / 0 phụ đề")
            self.lbl_range_count.setToolTip("")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.table.clearSelection()
            self.update_empty_state()
            self.table.blockSignals(False)
            self.is_rendering = False
            return

        # This mapping is display-only. all_segments is never replaced or sliced.
        self._visible_source_indices = self._get_visible_source_indices()
        visible_count = len(self._visible_source_indices)
        total_count = len(self.all_segments)
        count_text = f"{visible_count} / {total_count} phụ đề"
        if self._active_time_range_ms is not None:
            range_start_ms, range_end_ms = self._active_time_range_ms
            count_text += f"  •  {range_start_ms / 60000:g}–{range_end_ms / 60000:g} phút"
            duration_ms = self._video_duration_ms()
            if duration_ms > 0 and range_end_ms > duration_ms:
                self.lbl_range_count.setToolTip(
                    "Cảnh báo: khoảng lọc đã áp dụng vượt thời lượng video hiện tại. "
                    "Hãy điều chỉnh Phút kết thúc."
                )
            else:
                self.lbl_range_count.setToolTip(
                    "Chỉ hiển thị phụ đề có thời gian giao với khoảng [phút bắt đầu, phút kết thúc). "
                    "Dữ liệu gốc và Timeline không bị cắt."
                )
        else:
            self.lbl_range_count.setToolTip(
                "Số hàng đang hiển thị / tổng số phụ đề trong dữ liệu chuẩn."
            )
        self.lbl_range_count.setText(count_text)
        if self.range_start_input.text().strip() or self.range_end_input.text().strip():
            self._on_time_range_input_changed()

        if self.group_size == 0:
            self.current_page = 0
            page_start, page_end = 0, visible_count
            self.lbl_page.setText("Tất cả")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
        else:
            max_page = max(1, (visible_count + self.group_size - 1) // self.group_size)
            self.current_page = max(0, min(self.current_page, max_page - 1))
            page_start = self.current_page * self.group_size
            page_end = min(page_start + self.group_size, visible_count)
            self.lbl_page.setText(f"{self.current_page + 1} / {max_page}")
            self.btn_prev.setEnabled(self.current_page > 0)
            self.btn_next.setEnabled(self.current_page < max_page - 1)

        page_source_indices = self._visible_source_indices[page_start:page_end]
        self._current_page_source_indices = list(page_source_indices)
        all_issues = SubtitleValidator.validate_all(self.all_segments, self._video_duration_ms())
        self.table.setRowCount(len(page_source_indices))

        for row, global_index in enumerate(page_source_indices):
            seg = self.all_segments[global_index]
            start_text = self.ms_to_time_str(seg['start']) if isinstance(seg['start'], (int, float)) else seg['start']
            end_text = self.ms_to_time_str(seg['end']) if isinstance(seg['end'], (int, float)) else seg['end']
            item_id = QTableWidgetItem(str(seg.get('stt', global_index + 1)))
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
            # Store the identity and canonical index on the item; never infer identity
            # from a row number after filtering or pagination.
            item_id.setData(Qt.UserRole, seg.get("id"))
            item_id.setData(Qt.UserRole + 1, global_index)
            issues = all_issues.get(global_index, [])
            if issues:
                has_error = any(issue.severity is Severity.ERROR for issue in issues)
                item_id.setText(f"{'❌' if has_error else '⚠'} {item_id.text()}")
                item_id.setToolTip("\n".join(f"- {issue.message}" for issue in issues))

            preset = seg.get("style_preset", "normal")
            if preset == "loud":
                item_id.setText(f"⚡ {item_id.text()}")
                item_id.setBackground(QColor(255, 230, 0, 18))
                tip = (item_id.toolTip() + "\n" if item_id.toolTip() else "") + "Style: Nhấn mạnh (Loud)"
                item_id.setToolTip(tip.strip())
            elif preset == "whisper":
                item_id.setText(f"🤫 {item_id.text()}")
                tip = (item_id.toolTip() + "\n" if item_id.toolTip() else "") + "Style: Thì thầm (Whisper)"
                item_id.setToolTip(tip.strip())

            self.table.setItem(row, self.COL_STT, item_id)
            self._set_table_item(row, self.COL_START, start_text)
            self._set_table_item(row, self.COL_END, end_text)
            try:
                duration_ms = self.time_str_to_ms(seg['end']) - self.time_str_to_ms(seg['start'])
                duration_text = f"{max(0, duration_ms) / 1000:.3f} s"
            except ValueError:
                duration_text = "--"
            self._set_table_item(row, self.COL_DUR, duration_text, readonly=True)

            display_text = seg['text'] if seg['text'].strip() else "[ Chưa có nội dung ]"
            text_item = QTableWidgetItem(display_text)

            if not seg['text'].strip():
                text_item.setForeground(QColor(Theme.TEXT_DISABLED))
                font = text_item.font()
                font.setItalic(True)
                text_item.setFont(font)

            # Render existing Auto-QC flags without changing underlying data.
            qc_flags = seg.get('metadata', {}).get('qc_flags', [])
            if qc_flags:
                if 'alignment_failed_fallback' in qc_flags:
                    text_item.setBackground(QColor('#5c1a1a'))
                    text_item.setToolTip('Lỗi gộp dòng: Hệ thống tự động trả về câu gốc để tránh gãy cấu trúc.')
                else:
                    text_item.setBackground(QColor('#5c4a1a'))
                    text_item.setToolTip('Cảnh báo Auto-QC:\n' + '\n'.join(f'- {f}' for f in qc_flags))

            self.table.setItem(row, self.COL_TEXT, text_item)

        self.table.blockSignals(False)
        self.update_empty_state()
        self._load_current_editor()
        self.sync_to_controller()
        self.check_overlaps()
        if 0 <= self.current_index < len(self.all_segments):
            row = self._get_row_by_source_index(self.current_index)
            if row >= 0:
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.blockSignals(False)
        self.is_rendering = False

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
        if readonly or col in (self.COL_STT, self.COL_DUR):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if col in (self.COL_STT, self.COL_START, self.COL_END, self.COL_DUR):
            item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)

    def sync_to_controller(self):
        data = []
        for seg in self.all_segments:
            start_ms = self.time_str_to_ms(seg['start'])
            end_ms = self.time_str_to_ms(seg['end'])
            raw_text = seg['text']
            if not raw_text.strip() or raw_text == "[ Chưa có nội dung ]": raw_text = "[ Chưa có nội dung ]"
            try: stt = int(seg['stt'])
            except: stt = 0
            data.append((start_ms, end_ms, raw_text, stt))
        self.live_edit_applied.emit(data)

    def commit_pending_edit(self):
        self.current_editor.commit_pending_edit()
        for editor in self.table.findChildren(QLineEdit):
            position = editor.mapTo(
                self.table.viewport(), editor.rect().center()
            )
            index = self.table.indexAt(position)
            if not index.isValid():
                continue
            self.table.commitData(editor)
            self.table.closeEditor(editor, QAbstractItemDelegate.NoHint)

    def on_table_edit(self, row, col):
        if self.is_rendering or self.undo_manager is None: return
        
        abs_idx = self._source_index_for_row(row)
        if not (0 <= abs_idx < len(self.all_segments)): return

        segment = self.all_segments[abs_idx]
        old_start = segment['start']
        old_end = segment['end']

        it_stt = self.table.item(row, self.COL_STT)
        it_start = self.table.item(row, self.COL_START)
        it_end = self.table.item(row, self.COL_END)
        it_text = self.table.item(row, self.COL_TEXT)

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
                changes = self._build_timing_changes(abs_idx, old_start, old_end, new_start, new_end)
                self.undo_manager.push(
                    EditTimingCommand(changes, data_provider=self.all_segments)
                )
                self.live_edit_applied.emit(self.all_segments)

            if segment['text'] != raw_text:
                self.undo_manager.push(
                    EditTextCommand(abs_idx, segment['text'], raw_text, self.all_segments)
                )
                
            # Emit TM commit
            orig = segment.get("original_text", "").strip()
            if orig and orig != "[Unknown Source]":
                prev_orig = self.all_segments[abs_idx - 1].get("original_text", "") if abs_idx > 0 else ""
                next_orig = self.all_segments[abs_idx + 1].get("original_text", "") if abs_idx < len(self.all_segments) - 1 else ""
                qc_flags = segment.get("metadata", {}).get("qc_flags", [])
                self.commit_segment.emit(orig, raw_text, prev_orig, next_orig, qc_flags)

    def _get_selected_source_indices(self) -> list[int]:
        """Lấy danh sách index nguồn (toàn cục) của các hàng đang được chọn trên bảng."""
        selected_ranges = self.table.selectedRanges()
        indices = set()
        for r in selected_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                idx = self._source_index_for_row(row)
                if 0 <= idx < len(self.all_segments):
                    indices.add(idx)
        return sorted(list(indices))

    def _show_table_context_menu(self, pos):
        """Menu chuột phải để đổi Style hoặc Quét lại âm lượng cho các dòng đang chọn."""
        selected_indices = self._get_selected_source_indices()
        if not selected_indices:
            row = self.table.rowAt(pos.y())
            if row >= 0:
                idx = self._source_index_for_row(row)
                if 0 <= idx < len(self.all_segments):
                    selected_indices = [idx]
        if not selected_indices:
            return

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        style_menu = menu.addMenu("🏷️ Đặt Style")
        act_normal = style_menu.addAction("Normal (Mặc định)")
        act_loud = style_menu.addAction("⚡ Loud (Nhấn mạnh)")
        act_whisper = style_menu.addAction("🤫 Whisper (Thì thầm)")

        menu.addSeparator()
        act_reanalyze = menu.addAction("🔄 Quét lại âm lượng")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_normal:
            self._set_style_preset_for_indices(selected_indices, "normal")
        elif action == act_loud:
            self._set_style_preset_for_indices(selected_indices, "loud")
        elif action == act_whisper:
            self._set_style_preset_for_indices(selected_indices, "whisper")
        elif action == act_reanalyze:
            self._on_reanalyze_audio_style_clicked(selected_indices)

    def _set_style_preset_for_indices(self, indices: list[int], new_preset: str):
        """Thay đổi style preset có hỗ trợ hoàn tác Undo/Redo."""
        from core.subtitle_editing.commands.edit_style_command import EditStyleCommand
        changes = []
        for idx in indices:
            old_p = self.all_segments[idx].get("style_preset", "normal")
            if old_p != new_preset:
                changes.append({"index": idx, "old_preset": old_p, "new_preset": new_preset})
        if not changes:
            return
        cmd = EditStyleCommand(changes, self.all_segments)
        if self.undo_manager:
            self.undo_manager.push(cmd)
        else:
            cmd.redo()
        self.render_page()
        self.live_edit_applied.emit(self.all_segments)

    def _on_reanalyze_audio_style_clicked(self, target_indices=None):
        """Quét lại Style theo năng lượng âm thanh cho nhóm dòng mục tiêu hoặc toàn bộ."""
        if not target_indices or not isinstance(target_indices, (list, set)):
            target_indices = self._get_selected_source_indices()
            if not target_indices:
                target_indices = list(range(len(self.all_segments)))
        if not target_indices or not self.all_segments:
            return

        win = self.window()
        video_path = win.get_current_video_path() if hasattr(win, "get_current_video_path") else getattr(win, "current_vid", None)
        if not video_path or not os.path.exists(video_path):
            Toast.show_warning(win, "Chưa có video nguồn để phân tích âm thanh.")
            return

        try:
            from core.subtitle_quality.audio_energy_analyzer import AudioEnergyAnalyzer
            from core.subtitle_editing.commands.edit_style_command import EditStyleCommand
            peaks = AudioEnergyAnalyzer.get_peaks_data(video_path)
            old_presets = {i: self.all_segments[i].get("style_preset", "normal") for i in target_indices}
            AudioEnergyAnalyzer.analyze_segments(peaks, self.all_segments, target_indices=target_indices)

            changes = [
                {"index": i, "old_preset": old_presets[i], "new_preset": self.all_segments[i].get("style_preset", "normal")}
                for i in target_indices
                if old_presets[i] != self.all_segments[i].get("style_preset", "normal")
            ]
            if changes and self.undo_manager:
                cmd = EditStyleCommand(changes, self.all_segments)
                self.undo_manager.push(cmd)

            self.render_page()
            self.live_edit_applied.emit(self.all_segments)
            Toast.show_success(win, f"⚡ Đã cập nhật Style cho {len(target_indices)} dòng phụ đề.", duration_ms=3000)
        except Exception as e:
            Toast.show_error(win, f"Lỗi phân tích âm thanh: {e}")

    def _on_row_selected(self, row, _column):
        abs_idx = self._source_index_for_row(row)
        if 0 <= abs_idx < len(self.all_segments):
            self.select_segment(abs_idx)

    def _on_table_current_cell_changed(self, currentRow, _currentColumn, _previousRow, _previousColumn):
        if not self.is_rendering and currentRow >= 0:
            abs_idx = self._source_index_for_row(currentRow)
            if 0 <= abs_idx < len(self.all_segments) and abs_idx != self.current_index:
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
            request_activation = getattr(
                self.selection_controller, "request_editor_activation", None
            )
            if request_activation:
                request_activation(index, self.all_segments[index].get("id"))
            self.selection_controller.select(
                index, self.all_segments[index].get("id"), SelectionSource.EDITOR
            )
            return
        self._select_segment_ui(index)

    def sync_selection(self, index, segment_id, source=None):
        target_idx = -1
        if segment_id:
            target_idx = next(
                (i for i, seg in enumerate(self.all_segments) if seg.get("id") == segment_id),
                -1,
            )
        if target_idx < 0 and 0 <= index < len(self.all_segments):
            target_idx = index

        if 0 <= target_idx < len(self.all_segments):
            self._is_syncing_ui = True
            self._select_segment_ui(target_idx)
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

        # If the selected ID is included by the active range but is on another
        # filtered page, navigate to that page. If it is outside the filter, keep
        # the filter and show the current editor without falsely selecting another row.
        try:
            visible_pos = self._visible_source_indices.index(index)
        except ValueError:
            visible_pos = -1
        if visible_pos >= 0:
            target_page = visible_pos // self.group_size if self.group_size > 0 else 0
            if target_page != self.current_page:
                self.current_page = target_page
                self.render_page()

        self.table.blockSignals(True)
        row = self._get_row_by_source_index(index)
        if row >= 0:
            self.table.selectRow(row)
        else:
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
        self.table.blockSignals(False)

    def sync_playback_highlight(self, absolute_index: int):
        """Select the playing subtitle without assuming visible row == source index."""
        if not (0 <= absolute_index < len(self.all_segments)):
            return
        if self.selection_controller and not self._is_syncing_ui:
            self.selection_controller.select(
                absolute_index, self.all_segments[absolute_index].get("id"), SelectionSource.PLAYBACK
            )
            return

        self.current_index = absolute_index
        try:
            visible_pos = self._visible_source_indices.index(absolute_index)
        except ValueError:
            self._is_syncing_ui = True
            self.table.clearSelection()
            self._load_current_editor()
            self.update_empty_state()
            self._is_syncing_ui = False
            return

        # Translate the filtered-list position into the page-local table row.
        target_page = visible_pos // self.group_size if self.group_size > 0 else 0
        if target_page != self.current_page:
            self.current_page = target_page
            self.render_page()
        row_in_table = visible_pos % self.group_size if self.group_size > 0 else visible_pos
        self._is_syncing_ui = True
        self.table.selectRow(row_in_table)
        self._load_current_editor()
        self.update_empty_state()
        self._is_syncing_ui = False

    def _emit_tm_suggestion(self):
        if 0 <= self.current_index < len(self.all_segments):
            seg = self.all_segments[self.current_index]
            orig = seg.get("original_text", "").strip()
            if orig and orig != "[Unknown Source]":
                self.request_tm_suggestion.emit(orig)

    def _load_current_editor(self):
        if 0 <= self.current_index < len(self.all_segments):
            seg = self.all_segments[self.current_index]
            self.current_editor.setEnabled(True)
            self.current_editor.setTitle(f"Current Subtitle: #{self.current_index + 1}")
            self.current_editor.set_values(
                seg["start"], 
                seg["end"], 
                seg["text"], 
                original_text=seg.get("original_text", "")
            )
            self._tm_debounce.start()

    def _on_current_editor_scan_requested(self):
        if not self.all_segments or self.current_index < 0 or self.current_index >= len(self.all_segments):
            return
        seg = self.all_segments[self.current_index]
        start_ms = time_str_to_ms(seg.get("start", "00:00:00,000"))
        end_ms = time_str_to_ms(seg.get("end", "00:00:00,000"))
        self.segment_scan_requested.emit(seg.get("id"), start_ms, end_ms)

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
        
        # Hard clamp to prevent overlap
        start_ms = self.time_str_to_ms(new_start)
        end_ms = self.time_str_to_ms(new_end)
        
        if abs_idx > 0:
            prev_seg = self.all_segments[abs_idx - 1]
            prev_end_ms = self.time_str_to_ms(prev_seg["end"])
            if start_ms < prev_end_ms:
                start_ms = prev_end_ms
                new_start = self.ms_to_time_str(start_ms)
                
        ripple = getattr(self, "ripple_shift_enabled", True)
        if not ripple and abs_idx < len(self.all_segments) - 1:
            next_seg = self.all_segments[abs_idx + 1]
            next_start_ms = self.time_str_to_ms(next_seg["start"])
            if end_ms > next_start_ms:
                end_ms = next_start_ms
                new_end = self.ms_to_time_str(end_ms)
                
        # Also ensure start < end after clamping
        if start_ms >= end_ms:
            # If invalid, fallback to original
            new_start = segment["start"]
            new_end = segment["end"]

        if new_start != segment["start"] or new_end != segment["end"]:
            changes = self._build_timing_changes(
                abs_idx,
                segment["start"],
                segment["end"],
                new_start,
                new_end,
            )
            self.undo_manager.push(
                EditTimingCommand(
                    changes,
                    data_provider=self.all_segments,
                )
            )
            self.live_edit_applied.emit(self.all_segments)
        if values["text"] != segment["text"]:
            self.undo_manager.push(
                EditTextCommand(abs_idx, segment["text"], values["text"], self.all_segments)
            )
            
        # Emit TM commit
        orig = segment.get("original_text", "").strip()
        if orig and orig != "[Unknown Source]":
            prev_orig = self.all_segments[abs_idx - 1].get("original_text", "") if abs_idx > 0 else ""
            next_orig = self.all_segments[abs_idx + 1].get("original_text", "") if abs_idx < len(self.all_segments) - 1 else ""
            qc_flags = segment.get("metadata", {}).get("qc_flags", [])
            self.commit_segment.emit(orig, values["text"], prev_orig, next_orig, qc_flags)

    def _build_timing_changes(self, abs_idx: int, old_start, old_end, new_start, new_end) -> list:
        changes = [{
            "index": abs_idx,
            "old_start": old_start,
            "old_end": old_end,
            "new_start": new_start,
            "new_end": new_end,
        }]

        if not getattr(self, "ripple_shift_enabled", True):
            return changes

        old_end_ms = self.time_str_to_ms(old_end)
        new_end_ms = self.time_str_to_ms(new_end)
        ripple_delta_ms = new_end_ms - old_end_ms

        if ripple_delta_ms == 0:
            return changes

        for i in range(abs_idx + 1, len(self.all_segments)):
            seg = self.all_segments[i]
            cur_s = seg["start"]
            cur_e = seg["end"]
            s_ms = self.time_str_to_ms(cur_s)
            e_ms = self.time_str_to_ms(cur_e)

            shifted_s_ms = max(0, s_ms + ripple_delta_ms)
            shifted_e_ms = max(shifted_s_ms + 50, e_ms + ripple_delta_ms)

            changes.append({
                "index": i,
                "old_start": cur_s,
                "old_end": cur_e,
                "new_start": self._coerce_time_value(cur_s, self.ms_to_time_str(shifted_s_ms)),
                "new_end": self._coerce_time_value(cur_e, self.ms_to_time_str(shifted_e_ms)),
            })

        return changes


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
        if not self.all_segments or self.undo_manager is None:
            return

        def _get_range(seg):
            s_val = seg.get("start_ms") if "start_ms" in seg else self.time_str_to_ms(seg["start"])
            e_val = seg.get("end_ms") if "end_ms" in seg else self.time_str_to_ms(seg["end"])
            return int(s_val), int(e_val)

        target_idx = -1
        if 0 <= self.current_index < len(self.all_segments):
            s_ms, e_ms = _get_range(self.all_segments[self.current_index])
            if s_ms <= playhead_ms < e_ms:
                target_idx = self.current_index

        if target_idx == -1:
            for idx, seg in enumerate(self.all_segments):
                s_ms, e_ms = _get_range(seg)
                if s_ms <= playhead_ms < e_ms:
                    target_idx = idx
                    break

        if target_idx == -1:
            return

        start_ms, end_ms = _get_range(self.all_segments[target_idx])
        # shortcut: 200ms boundary guard prevents sub-frame slivers, upgrade to dynamic threshold if fps changes
        if (playhead_ms - start_ms >= 200) and (end_ms - playhead_ms >= 200):
            self.undo_manager.push(
                SplitCommand(target_idx, playhead_ms, self.all_segments)
            )
            new_idx = target_idx + 1
            if 0 <= new_idx < len(self.all_segments):
                self.current_index = new_idx
                new_seg = self.all_segments[new_idx]
                if getattr(self, "selection_controller", None) and new_seg.get("id"):
                    self.selection_controller.set_selected_id(new_seg.get("id"))
                if hasattr(self, "render_page"):
                    self.render_page()

    def nudge_selected_segment(self, delta_ms: int, target: str = "both"):
        if self.current_index < 0:
            if hasattr(self, "table") and self.table.currentRow() >= 0:
                self.current_index = self._source_index_for_row(self.table.currentRow())
            elif getattr(self, "selection_controller", None) and self.selection_controller.selected_segment_id:
                sid = self.selection_controller.selected_segment_id
                self.current_index = next((i for i, s in enumerate(self.all_segments) if s.get("id") == sid), -1)

        if self.current_index < 0 or self.current_index >= len(self.all_segments):
            return
        if self.undo_manager is None:
            return

        if hasattr(self, "current_editor"):
            self.current_editor.commit_pending_edit()

        abs_idx = self.current_index
        segment = self.all_segments[abs_idx]
        old_start = segment["start"]
        old_end = segment["end"]
        start_ms = self.time_str_to_ms(old_start)
        end_ms = self.time_str_to_ms(old_end)

        if target == "start":
            start_ms = max(0, start_ms + delta_ms)
            if start_ms >= end_ms:
                start_ms = max(0, end_ms - 50)
        elif target == "end":
            end_ms = max(start_ms + 50, end_ms + delta_ms)
        else:  # "both" (shift entire segment)
            shift = delta_ms
            if start_ms + shift < 0:
                shift = -start_ms
            start_ms += shift
            end_ms += shift

        new_start = self._coerce_time_value(old_start, self.ms_to_time_str(start_ms))
        new_end = self._coerce_time_value(old_end, self.ms_to_time_str(end_ms))

        if new_start != old_start or new_end != old_end:
            changes = self._build_timing_changes(
                abs_idx, old_start, old_end, new_start, new_end
            )
            self.undo_manager.push(
                EditTimingCommand(
                    changes, data_provider=self.all_segments
                )
            )
            self.current_editor.set_time(start_ms, end_ms)
            self.live_edit_applied.emit(self.all_segments)
            if getattr(self, "selection_controller", None) and isinstance(segment, dict):
                # Trigger global selection focus to update waveform highlight
                self.selection_controller.selection_changed.emit(
                    abs_idx, segment.get("id"), SelectionSource.EDITOR
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
        target_id = None
        for i, seg in enumerate(self.all_segments):
            if str(seg.get('stt', i + 1)).strip() == str(stt).strip():
                target_idx = i
                target_id = seg.get("id")
                break

        if target_idx == -1:
            return

        try:
            visible_pos = self._visible_source_indices.index(target_idx)
        except ValueError:
            self.table.clearSelection()
            return

        target_page = visible_pos // self.group_size if self.group_size > 0 else 0
        if target_page != self.current_page:
            self.current_page = target_page
            self.render_page()

        row_in_table = visible_pos % self.group_size if self.group_size > 0 else visible_pos
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.selectRow(row_in_table)
        item = self.table.item(row_in_table, self.COL_STT)
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
            segments = parse_srt_content(handle.read())
        self._load_segments(segments, srt_path)

    def load_canonical_segments(self, segments, srt_path):
        rows = copy.deepcopy(segments)
        for index, row in enumerate(rows, 1):
            row["stt"] = str(index)
            row["start"] = ms_to_time_str(row["start_ms"])
            row["end"] = ms_to_time_str(row["end_ms"])
        self._load_segments(rows, srt_path)

    def _load_segments(self, segments, srt_path):
        self.all_segments = segments
        self.srt_path = srt_path
        self.current_page = 0
        
        if self.undo_manager:
            self.undo_manager.clear()
        if self.selection_controller:
            self.selection_controller.clear_selection(SelectionSource.PROGRAMMATIC)
            
        if not self.auto_resolve_overlaps():
            self.render_page()
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
        self._load_segments(data.get("segments", []), draft_path)

    def on_row_double_clicked(self, row, column):
        start_item = self.table.item(row, 1)
        end_item = self.table.item(row, 2)
        if start_item and end_item:
            try:
                start_ms = self.time_str_to_ms(start_item.text())
                end_ms = self.time_str_to_ms(end_item.text())
                self.segment_focused.emit(start_ms, end_ms)
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


    def auto_resolve_overlaps(self):
        if not self.all_segments or self.undo_manager is None:
            return False
            
        changes = []
        MIN_DURATION_MS = 100
        
        for i in range(len(self.all_segments) - 1):
            s1 = self.all_segments[i]
            s2 = self.all_segments[i + 1]
            
            end_ms = self.time_str_to_ms(s1["end"])
            next_start_ms = self.time_str_to_ms(s2["start"])
            next_end_ms = self.time_str_to_ms(s2["end"])
            
            if end_ms > next_start_ms:
                new_next_start_ms = end_ms
                new_duration = next_end_ms - new_next_start_ms
                
                if new_duration >= MIN_DURATION_MS:
                    changes.append({
                        "index": i + 1,
                        "old_start": s2["start"],
                        "old_end": s2["end"],
                        "new_start": self.ms_to_time_str(new_next_start_ms),
                        "new_end": s2["end"],
                    })
                    s2["start"] = self.ms_to_time_str(new_next_start_ms)
                    
        if changes:
            from ui.toast import Toast
            self.undo_manager.push(EditTimingCommand(changes, data_provider=self.all_segments))
            Toast.show_info(self.window(), f"⚡ Đã tự động sửa {len(changes)} chồng lấn.\n(Nhấn Ctrl+Z để Hoàn tác)")
            return True
            
        return False

    def check_overlaps(self):
        overlaps = 0
        self.overlap_pairs = []
        for i in range(len(self.all_segments) - 1):
            s1 = self.all_segments[i]
            s2 = self.all_segments[i + 1]
            end_ms = self.time_str_to_ms(s1["end"])
            next_start_ms = self.time_str_to_ms(s2["start"])
            if end_ms > next_start_ms:
                overlaps += 1
                self.overlap_pairs.append(i)
                
        if overlaps > 0:
            self.fix_overlap_btn.setText(f"⚡ Chồng lấn ({overlaps})")
            self.fix_overlap_btn.setEnabled(True)
        else:
            self.fix_overlap_btn.setText("⚡ Chồng lấn ▾")
            self.fix_overlap_btn.setEnabled(False)

    def fix_overlaps(self, mode="keep_prev", all_overlaps=False):
        if not self.overlap_pairs or self.undo_manager is None:
            return
            
        targets = self.overlap_pairs if all_overlaps else [self.overlap_pairs[0]]
        if not all_overlaps and self.current_index in self.overlap_pairs:
            targets = [self.current_index]
            
        changes = []
        for i in targets:
            s1 = self.all_segments[i]
            s2 = self.all_segments[i + 1]
            end_ms = self.time_str_to_ms(s1["end"])
            next_start_ms = self.time_str_to_ms(s2["start"])
            
            if end_ms <= next_start_ms:
                continue
                
            if mode == "keep_prev":
                new_next_start_ms = end_ms
                next_end_ms = self.time_str_to_ms(s2["end"])
                if new_next_start_ms > next_end_ms - 100:
                    new_next_start_ms = next_end_ms - 100
                changes.append({
                    "index": i + 1,
                    "old_start": s2["start"],
                    "old_end": s2["end"],
                    "new_start": self.ms_to_time_str(new_next_start_ms),
                    "new_end": s2["end"],
                })
            else:
                new_end_ms = next_start_ms
                start_ms = self.time_str_to_ms(s1["start"])
                if new_end_ms < start_ms + 100:
                    new_end_ms = start_ms + 100
                changes.append({
                    "index": i,
                    "old_start": s1["start"],
                    "old_end": s1["end"],
                    "new_start": s1["start"],
                    "new_end": self.ms_to_time_str(new_end_ms),
                })
                
        if changes:
            self.undo_manager.push(EditTimingCommand(changes, data_provider=self.all_segments))
            self.render_page()
            
