import json
import os
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Nạp Design System
from ui.theme import Theme
from ui.toast import Toast


class SubtitleEditorWidget(QWidget):
    seek_requested = Signal(int)
    srt_saved = Signal(str)
    style_changed = Signal(dict)
    preview_toggled = Signal(bool)
    live_edit_applied = Signal(list)
    fill_text_requested = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.srt_path = None
        
        self.all_segments = []
        self.current_page = 0
        self.group_size = 0     
        self.is_rendering = False

        self.current_text_color = QColor("white")
        self.current_outline_color = QColor("black")
        
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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["STT", "Bắt đầu", "Kết thúc", "Nội dung"])
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 95)
        self.table.setColumnWidth(2, 95)
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
        left_layout.addWidget(self.table)

        # =========================================================
        # [S6-T6] KHU VỰC ĐIỀU KHIỂN AI RANGE & CONTINUE
        # =========================================================
        ai_frame = QFrame()
        ai_frame.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 6px;")
        ai_layout = QHBoxLayout(ai_frame)
        ai_layout.setContentsMargins(12, 8, 12, 8)
        ai_layout.setSpacing(10)
        
        self.lbl_progress = QLabel("Đã điền: 0 / 0")
        self.lbl_progress.setStyleSheet(f"color: {Theme.CYAN}; font-weight: bold; font-size: 12px; border: none;")
        ai_layout.addWidget(self.lbl_progress)
        
        ai_layout.addStretch()
        
        lbl_batch = QLabel("Batch AI:")
        lbl_batch.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-weight: bold; border: none;")
        ai_layout.addWidget(lbl_batch)
        
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1, 100)
        self.spin_batch.setValue(5)
        self.spin_batch.setFixedWidth(65)
        self.spin_batch.setStyleSheet(f"""
            QSpinBox {{
                background-color: {Theme.BG_APP};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding-left: 6px;
                padding-right: 20px;
                min-height: 26px;
                font-weight: bold;
            }}
            QSpinBox:focus {{ border: 1px solid {Theme.CYAN}; }}
            QSpinBox::up-button {{
                subcontrol-origin: border; subcontrol-position: top right;
                width: 18px; border-left: 1px solid {Theme.BORDER};
                border-bottom: 1px solid {Theme.BORDER}; background-color: {Theme.SURFACE}; border-top-right-radius: 3px;
            }}
            QSpinBox::up-button:hover {{ background-color: {Theme.BORDER}; }}
            QSpinBox::down-button {{
                subcontrol-origin: border; subcontrol-position: bottom right;
                width: 18px; border-left: 1px solid {Theme.BORDER}; background-color: {Theme.SURFACE}; border-bottom-right-radius: 3px;
            }}
            QSpinBox::down-button:hover {{ background-color: {Theme.BORDER}; }}
            QSpinBox::up-arrow {{
                width: 0px; height: 0px;
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-bottom: 5px solid {Theme.TEXT_MUTED}; margin-top: 1px;
            }}
            QSpinBox::up-arrow:hover {{ border-bottom: 5px solid #FFFFFF; }}
            QSpinBox::down-arrow {{
                width: 0px; height: 0px;
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 5px solid {Theme.TEXT_MUTED}; margin-bottom: 1px;
            }}
            QSpinBox::down-arrow:hover {{ border-top: 5px solid #FFFFFF; }}
        """)
        ai_layout.addWidget(self.spin_batch)
        
        self.btn_continue = QPushButton("▶ Tiếp tục từ câu...")
        self.btn_continue.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.PRIMARY_PURPLE}; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 5px 16px; border: none; min-height: 20px;
            }}
            QPushButton:hover {{ background-color: {Theme.PRIMARY_PINK}; }}
            QPushButton:disabled {{ background-color: {Theme.SURFACE}; color: {Theme.TEXT_DISABLED}; border: 1px solid {Theme.BORDER}; }}
        """)
        self.btn_continue.clicked.connect(self.trigger_ai_fill)
        ai_layout.addWidget(self.btn_continue)
        
        left_layout.addWidget(ai_frame)
        
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
        
        btn_layout.addWidget(self.approve_btn)
        btn_layout.addWidget(self.save_draft_btn)
        btn_layout.addWidget(self.save_btn)
        left_layout.addLayout(btn_layout)
        
        splitter.addWidget(left_panel)
        
        # ================= LỚP 2: RIGHT PANEL (INSPECTOR STYLE) =================
        right_panel = QFrame()
        right_panel.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 6px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12) 
        
        title_lbl = QLabel("🎨 Subtitle Inspector")
        title_lbl.setStyleSheet(f"font-weight: bold; color: {Theme.TEXT_PRIMARY}; font-size: 14px; border: none;")
        right_layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Theme.BORDER}; border: none;")
        right_layout.addWidget(sep)
        
        self.chk_preview = QCheckBox("Hiển thị Subtitle Overlay")
        self.chk_preview.setChecked(True)
        self.chk_preview.setStyleSheet("font-weight: bold; border: none;")
        self.chk_preview.toggled.connect(self.on_preview_toggled)
        right_layout.addWidget(self.chk_preview)
        
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font:", styleSheet=f"border: none; color: {Theme.TEXT_MUTED};"))
        self.font_combo = QComboBox()
        for f in ["Arial", "Noto Sans JP", "Segoe UI", "Tahoma"]:
            self.font_combo.addItem(f, f)
        self.font_combo.currentTextChanged.connect(self.emit_style)
        font_layout.addWidget(self.font_combo, stretch=2)
        right_layout.addLayout(font_layout)

        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Cỡ chữ:", styleSheet=f"border: none; color: {Theme.TEXT_MUTED};"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(10, 100)
        self.size_spin.setValue(28)
        self.size_spin.setStyleSheet(f"QSpinBox {{ padding: 4px; min-height: 24px; }}")
        self.size_spin.valueChanged.connect(self.emit_style)
        size_layout.addWidget(self.size_spin, stretch=2)
        right_layout.addLayout(size_layout)
        
        color_layout = QHBoxLayout()
        self.btn_text_color = QPushButton("■ Màu chữ")
        self.btn_text_color.setStyleSheet(f"color: {self.current_text_color.name()}; font-weight: bold; background: {Theme.BG_APP}; border: 1px solid {Theme.CYAN}; border-radius: 4px; padding: 6px;")
        self.btn_text_color.clicked.connect(self.choose_text_color)
        color_layout.addWidget(self.btn_text_color)
        
        self.btn_outline_color = QPushButton("■ Màu viền")
        self.btn_outline_color.setStyleSheet(f"color: {self.current_outline_color.name()}; font-weight: bold; background: #FFFFFF; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 6px;")
        self.btn_outline_color.clicked.connect(self.choose_outline_color)
        color_layout.addWidget(self.btn_outline_color)
        right_layout.addLayout(color_layout)
        
        outline_layout = QHBoxLayout()
        outline_layout.addWidget(QLabel("Độ dày viền:", styleSheet=f"border: none; color: {Theme.TEXT_MUTED};"))
        self.outline_spin = QSpinBox()
        self.outline_spin.setStyleSheet(f"QSpinBox {{ padding: 4px; min-height: 24px; }}")
        self.outline_spin.setRange(0, 10)
        self.outline_spin.setValue(2)
        self.outline_spin.valueChanged.connect(self.emit_style)
        outline_layout.addWidget(self.outline_spin, stretch=2)
        right_layout.addLayout(outline_layout)
        
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Vị trí:", styleSheet=f"border: none; color: {Theme.TEXT_MUTED};"))
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["Bottom", "Top", "Center"])
        self.pos_combo.currentTextChanged.connect(self.emit_style)
        pos_layout.addWidget(self.pos_combo, stretch=2)
        right_layout.addLayout(pos_layout)
        
        right_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setSizes([750, 250])
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
            
            display_text = seg['text'] if seg['text'].strip() else "[ Chưa có nội dung ]"
            text_item = QTableWidgetItem(display_text)
            
            if not seg['text'].strip():
                text_item.setForeground(QColor(Theme.TEXT_DISABLED))
                font = text_item.font()
                font.setItalic(True)
                text_item.setFont(font)
                
            self.table.setItem(row, 3, text_item)

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
        it_text = self.table.item(row, 3)

        if it_stt and it_start and it_end and it_text:
            try:
                self.time_str_to_ms(it_start.text())
                self.time_str_to_ms(it_end.text())
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
        s, ms = divmod(int(ms), 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def time_str_to_ms(self, time_str):
        time_str = time_str.strip()
        parts = time_str.replace(',', ':').split(':')
        if len(parts) == 4:
            h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            return (h * 3600 + m * 60 + s) * 1000 + ms
        raise ValueError("Sai định dạng HH:MM:SS,mmm")

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

    # ================= LOGIC PREVIEW STYLE =================
    def _open_color_dialog(self, initial_color, title):
        dialog = QColorDialog(initial_color, self)
        dialog.setWindowTitle(title)
        dialog.setStyleSheet(f"""
            QDialog, QColorDialog {{ background-color: {Theme.SURFACE}; color: {Theme.TEXT_PRIMARY}; }}
            QLabel {{ color: {Theme.TEXT_PRIMARY}; }}
            QPushButton {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY}; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 6px 12px; }}
            QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; border: 1px solid {Theme.CYAN}; }}
        """)
        if dialog.exec(): return dialog.currentColor()
        return QColor()

    def choose_text_color(self):
        color = self._open_color_dialog(self.current_text_color, "Chọn màu chữ")
        if color.isValid():
            self.current_text_color = color
            self.btn_text_color.setStyleSheet(f"color: {color.name()}; font-weight: bold; background: {Theme.BG_APP}; border: 1px solid {Theme.CYAN}; border-radius: 4px; padding: 6px;")
            self.emit_style()

    def choose_outline_color(self):
        color = self._open_color_dialog(self.current_outline_color, "Chọn màu viền")
        if color.isValid():
            self.current_outline_color = color
            self.btn_outline_color.setStyleSheet(f"color: {color.name()}; font-weight: bold; background: #FFFFFF; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 6px;")
            self.emit_style()

    def on_preview_toggled(self, checked):
        self.preview_toggled.emit(checked)

    def emit_style(self):
        if not hasattr(self, 'font_combo'): return
        current_pos = self.pos_combo.currentText() if hasattr(self, 'pos_combo') else "Bottom"
        self.style_changed.emit({
            "family": self.font_combo.currentText(),
            "size": self.size_spin.value(),
            "color": self.current_text_color.name(),
            "out_color": self.current_outline_color.name(),
            "out_width": self.outline_spin.value(),
            "position": current_pos
        })

    def approve_timing(self):
        if not self.all_segments:
            return
            
        for seg in self.all_segments:
            seg['status'] = 'final'
            
        Toast.show_success(self.window(), "Đã chốt Timing! Sẵn sàng cho AI điền chữ.")

    def update_draft_progress(self):
        if not self.all_segments:
            self.lbl_progress.setText("Trống")
            self.btn_continue.setEnabled(False)
            return
            
        done_count = sum(1 for s in self.all_segments if s.get('text', '').strip())
        total = len(self.all_segments)
        self.lbl_progress.setText(f"Đã điền: {done_count} / {total}")
        
        self.next_empty_idx = -1
        for i, seg in enumerate(self.all_segments):
            if not seg.get('text', '').strip() or seg.get('status') == 'timing_only':
                self.next_empty_idx = i
                break
                
        if self.next_empty_idx != -1:
            stt = self.all_segments[self.next_empty_idx]['stt']
            self.btn_continue.setText(f"▶ Tiếp tục từ câu {stt}")
            self.btn_continue.setEnabled(True)
        else:
            self.btn_continue.setText("✨ Đã hoàn thành toàn bộ")
            self.btn_continue.setEnabled(False)

    def trigger_ai_fill(self):
        if hasattr(self, 'next_empty_idx') and self.next_empty_idx != -1:
            count = self.spin_batch.value()
            self.fill_text_requested.emit(self.next_empty_idx, count)