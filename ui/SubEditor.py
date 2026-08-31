import json
import os
import re

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
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


def ms_to_time_str(ms: int) -> str:
    """Format milliseconds as the canonical SRT timestamp."""
    s, ms = divmod(max(0, int(ms)), 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def time_str_to_ms(time_str: str) -> int:
    """Parse a strict HH:MM:SS,mmm timestamp; return -1 when invalid."""
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
        times = QHBoxLayout()
        times.addWidget(QLabel("Start:"))
        self.start_edit = QLineEdit()
        times.addWidget(self.start_edit)
        times.addWidget(QLabel("End:"))
        self.end_edit = QLineEdit()
        times.addWidget(self.end_edit)
        layout.addLayout(times)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Nội dung phụ đề hiện tại...")
        self.text_edit.setMaximumHeight(70)
        layout.addWidget(self.text_edit)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        for widget in (self.start_edit, self.end_edit):
            widget.textChanged.connect(self._schedule_emit)
        self.text_edit.textChanged.connect(self._schedule_emit)
        self._debounce.timeout.connect(self._emit_changed)

    def set_values(self, start, end, text):
        for widget, value in ((self.start_edit, start), (self.end_edit, end)):
            widget.blockSignals(True)
            widget.setText(value)
            widget.blockSignals(False)
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self.text_edit.blockSignals(False)

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
        self.current_page = 0
        self.current_index = -1
        self.group_size = 0     
        self.is_rendering = False

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

        self.current_editor = CurrentSubtitleEditor()
        self.current_editor.setEnabled(False)
        self.current_editor.changed.connect(self._apply_current_editor)
        left_layout.addWidget(self.current_editor)

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
        self.table.setRowCount(len(display_segments))

        for row, seg in enumerate(display_segments):
            self.table.setItem(row, 0, QTableWidgetItem(str(seg['stt'])))
            self.table.setItem(row, 1, QTableWidgetItem(seg['start']))
            self.table.setItem(row, 2, QTableWidgetItem(seg['end']))
            try:
                duration_ms = self.time_str_to_ms(seg['end']) - self.time_str_to_ms(seg['start'])
                duration_text = self.ms_to_time_str(max(0, duration_ms))
            except ValueError:
                duration_text = "--"
            self.table.setItem(row, 3, QTableWidgetItem(duration_text))
            
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
        self.sync_to_controller()

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
        if self.is_rendering: return
        
        abs_idx = self.current_page * self.group_size + row if self.group_size > 0 else row
        if abs_idx >= len(self.all_segments): return

        old_start = self.all_segments[abs_idx]['start']
        old_end = self.all_segments[abs_idx]['end']

        it_stt = self.table.item(row, 0)
        it_start = self.table.item(row, 1)
        it_end = self.table.item(row, 2)
        it_text = self.table.item(row, 4)

        if it_stt and it_start and it_end and it_text:
            try:
                self.time_str_to_ms(it_start.text())
                start_ms = self.time_str_to_ms(it_start.text())
                end_ms = self.time_str_to_ms(it_end.text())
                if start_ms >= end_ms:
                    raise ValueError("Start phải nhỏ hơn End")
            except ValueError:
                # [S6-FIX] Dùng Toast Error thay cho QMessageBox
                Toast.show_error(self.window(), "Timestamp không hợp lệ (Chuẩn: HH:MM:SS,mmm)")
                self.table.blockSignals(True)
                it_start.setText(old_start)
                it_end.setText(old_end)
                self.table.blockSignals(False)
                return

            self.all_segments[abs_idx]['stt'] = it_stt.text()
            self.all_segments[abs_idx]['start'] = it_start.text()
            self.all_segments[abs_idx]['end'] = it_end.text()
            
            raw_text = it_text.text()
            if raw_text == "[ Chưa có nội dung ]": raw_text = ""
            self.all_segments[abs_idx]['text'] = raw_text
            
            self.sync_to_controller()
            self.update_draft_progress()

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
        self.current_index = index
        seg = self.all_segments[index]
        self.current_editor.setEnabled(True)
        self.current_editor.set_values(seg["start"], seg["end"], seg["text"])
        self.table.blockSignals(True)
        self.table.selectRow(index)
        self.table.blockSignals(False)

    def _load_current_editor(self):
        if 0 <= self.current_index < len(self.all_segments):
            seg = self.all_segments[self.current_index]
            self.current_editor.setEnabled(True)
            self.current_editor.set_values(seg["start"], seg["end"], seg["text"])

    def _apply_current_editor(self, values):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        abs_idx = self.current_page * self.group_size + row if self.group_size > 0 else row
        if not (0 <= abs_idx < len(self.all_segments)):
            return
        try:
            start_ms = self.time_str_to_ms(values["start"])
            end_ms = self.time_str_to_ms(values["end"])
            if start_ms >= end_ms:
                raise ValueError
        except ValueError:
            return
        self.all_segments[abs_idx].update(values)
        self.render_page()

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
        self.srt_path = srt_path
        self.all_segments.clear()

        if not srt_path or not os.path.exists(srt_path): 
            self.render_page()
            return

        with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().replace('\r\n', '\n')

        blocks = re.split(r'\n{2,}', content.strip())
        
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 2 and "-->" in lines[1]:
                idx = lines[0].strip()
                time_range = lines[1].strip()
                text = "\n".join(lines[2:]) if len(lines) > 2 else ""
                
                times = time_range.split(" --> ")
                start = times[0].strip() if len(times) > 0 else ""
                end = times[1].strip() if len(times) > 1 else ""
                
                self.all_segments.append({
                    "stt": idx,
                    "start": start,
                    "end": end,
                    "text": text,
                    "status": "draft",
                    "metadata": {"type": "normal"}
                })

        self.current_page = 0
        self.render_page()
        self.update_draft_progress()

    def save_srt(self):
        from PySide6.QtWidgets import QFileDialog
        import os
        
        path = self.srt_path
        if not path or not path.endswith('.srt'):
            base = os.path.splitext(path)[0] if path else "Project"
            default_name = f"{base}.srt"
            path, _ = QFileDialog.getSaveFileName(self, "Xuất file SRT", default_name, "SubRip Subtitle (*.srt)")
            if not path: return
            
        new_blocks = []
        for seg in self.all_segments:
            raw_text = seg['text']
            if raw_text == "[ Chưa có nội dung ]": raw_text = ""
            new_blocks.append(f"{seg['stt']}\n{seg['start']} --> {seg['end']}\n{raw_text}")
            
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(new_blocks) + "\n")
                
            self.srt_path = path 
            # [S6-FIX] Cắt ngắn đường dẫn và hiện Toast
            file_name = os.path.basename(path)
            Toast.show_success(self.window(), f"Đã xuất SRT: {file_name}")
            self.srt_saved.emit(self.srt_path)
        except Exception as e:
            Toast.show_error(self.window(), f"Lỗi lưu SRT: {str(e)}")

    def save_draft(self, silent=False):
        import json
        import os
        from PySide6.QtWidgets import QFileDialog
        
        path = self.srt_path
        
        if silent:
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
        
        draft_data = {"version": 1.0, "segments": []}
        for seg in self.all_segments:
            raw_text = seg['text'] if seg['text'] != "[ Chưa có nội dung ]" else ""
            current_status = seg.get('status', 'timing_only')
            
            if current_status != 'final':
                current_status = "draft" if raw_text.strip() else "timing_only"
                
            draft_data["segments"].append({
                "id": seg['stt'],
                "start_ms": self.time_str_to_ms(seg['start']),
                "end_ms": self.time_str_to_ms(seg['end']),
                "text": raw_text,
                "status": current_status,
                "metadata": seg.get('metadata', {"type": "normal"})
            })
            
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, ensure_ascii=False, indent=4)
                
            self.srt_path = path
            
            if not silent:
                file_name = os.path.basename(path)
                Toast.show_success(self.window(), f"Đã bảo lưu Draft: {file_name}")
        except Exception as e:
            if not silent: 
                Toast.show_error(self.window(), f"Lỗi lưu Draft: {str(e)}")

    def load_draft_file(self, draft_path):
        import json
        import os
        
        self.srt_path = draft_path 
        self.all_segments.clear()
        
        if not draft_path or not os.path.exists(draft_path):
            self.render_page()
            return
            
        with open(draft_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for seg in data.get("segments", []):
            self.all_segments.append({
                "stt": str(seg.get("id", 0)),
                "start": self.ms_to_time_str(seg.get("start_ms", 0)),
                "end": self.ms_to_time_str(seg.get("end_ms", 0)),
                "text": seg.get("text", ""),
                "status": seg.get("status", "timing_only"),
                "metadata": seg.get("metadata", {"type": "normal"})
            })
            
        self.current_page = 0
        self.render_page()
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
            
        Toast.show_success(self.window(), "Đã chốt Timing! Sẵn sàng cho AI điền chữ.")

    def update_draft_progress(self):
        if not self.all_segments:
            self.next_empty_idx = -1
            return

        self.next_empty_idx = -1
        for i, seg in enumerate(self.all_segments):
            if not seg.get('text', '').strip() or seg.get('status') == 'timing_only':
                self.next_empty_idx = i
                break
