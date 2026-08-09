import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
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


class SubtitleEditorWidget(QWidget):
    # Các tín hiệu cũ
    seek_requested = Signal(int)
    srt_saved = Signal(str)
    
    # Các tín hiệu mới cho Preview
    style_changed = Signal(dict)
    preview_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.srt_path = None
        
        # Khởi tạo giá trị mặc định cho Style (Đồng bộ với SubtitleOverlay)
        self.current_text_color = QColor("white")
        self.current_outline_color = QColor("black")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sử dụng QSplitter để chia đôi màn hình 70-30
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #273247; width: 2px; }")
        
        # ================= LỚP 1: LEFT PANEL (BẢNG PHỤ ĐỀ) =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["STT", "Bắt đầu", "Kết thúc", "Nội dung"])
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #10141F; color: #F5F7FA; gridline-color: #273247; border: 1px solid #273247; border-radius: 4px; }
            QHeaderView::section { background-color: #161B26; color: #98A2B3; font-weight: bold; padding: 4px; border: 1px solid #273247; }
            QTableWidget::item:selected { background-color: #35C8FF; color: #0D111A; font-weight: bold; }
        """)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        left_layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Lưu thay đổi (Ctrl+S)")
        self.save_btn.setObjectName("btn_secondary")
        self.save_btn.clicked.connect(self.save_srt)
        btn_layout.addWidget(self.save_btn)
        left_layout.addLayout(btn_layout)
        
        splitter.addWidget(left_panel)
        
        # ================= LỚP 2: RIGHT PANEL (STYLE PREVIEW) =================
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #161B26; border: 1px solid #273247; border-radius: 6px;")
        right_layout = QVBoxLayout(right_panel)
        
        # Tối ưu Margin & Spacing để thu gọn giao diện
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8) 
        
        title_lbl = QLabel("🎨 Subtitle Preview")
        title_lbl.setStyleSheet("font-weight: bold; color: #35C8FF; font-size: 13px; border: none;")
        right_layout.addWidget(title_lbl)
        
        # 1. Checkbox Bật/Tắt
        self.chk_preview = QCheckBox("Hiển thị Subtitle trên Video")
        self.chk_preview.setChecked(True)
        self.chk_preview.setStyleSheet("font-weight: bold; border: none;")
        self.chk_preview.toggled.connect(self.on_preview_toggled)
        right_layout.addWidget(self.chk_preview)
        
        # 2. Chọn Font (Xếp ngang hàng để tiết kiệm diện tích)
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font:", styleSheet="border: none; color: #98A2B3;"))
        self.font_combo = QComboBox()
        for f in ["Arial", "Noto Sans JP", "Segoe UI", "Tahoma"]:
            self.font_combo.addItem(f, f)
        self.font_combo.currentTextChanged.connect(self.emit_style)
        font_layout.addWidget(self.font_combo, stretch=2)
        right_layout.addLayout(font_layout)

        # fix_spinbox_css = """
        #     QSpinBox { 
        #         padding: 2px 20px 2px 4px; /* Đẩy padding phải ra 20px để nhường chỗ cho nút */
        #     }
        #     QSpinBox::up-button, QSpinBox::down-button { 
        #         subcontrol-origin: border;
        #         width: 20px; /* Cố định chiều rộng vùng bấm */
        #         background: #2B3547;
        #     }
        #     QSpinBox::up-button { subcontrol-position: top right; }
        #     QSpinBox::down-button { subcontrol-position: bottom right; }
        #     QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #35C8FF; }
        # """

        # Định nghĩa CSS vá lỗi vùng bấm (Trả quyền quản lý hitbox về cho hệ điều hành)
        fix_spinbox_css = """
            QSpinBox { 
                padding: 4px; 
                min-height: 24px; 
            }
        """
        
        # 3. Kích thước (Xếp ngang hàng)
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Cỡ chữ:", styleSheet="border: none; color: #98A2B3;"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(10, 100)
        self.size_spin.setValue(28)
        self.size_spin.valueChanged.connect(self.emit_style)
        size_layout.addWidget(self.size_spin, stretch=2)
        right_layout.addLayout(size_layout)
        
        # 4. Màu chữ và Viền 
        color_layout = QHBoxLayout()
        self.btn_text_color = QPushButton("■ Màu chữ")
        self.btn_text_color.setStyleSheet(f"color: {self.current_text_color.name()}; font-weight: bold; background: #2B3547; border: 1px solid #4AC1FF;")
        self.btn_text_color.clicked.connect(self.choose_text_color)
        color_layout.addWidget(self.btn_text_color)
        
        self.btn_outline_color = QPushButton("■ Màu viền")
        self.btn_outline_color.setStyleSheet(f"color: {self.current_outline_color.name()}; font-weight: bold; background: #FFF; border: 1px solid #273247;")
        self.btn_outline_color.clicked.connect(self.choose_outline_color)
        color_layout.addWidget(self.btn_outline_color)
        right_layout.addLayout(color_layout)
        
        # 5. Độ dày viền (Xếp ngang hàng)
        outline_layout = QHBoxLayout()
        outline_layout.addWidget(QLabel("Độ dày viền:", styleSheet="border: none; color: #98A2B3;"))
        self.outline_spin = QSpinBox()
        self.outline_spin.setStyleSheet(fix_spinbox_css)
        self.outline_spin.setRange(0, 10)
        self.outline_spin.setValue(2)
        self.outline_spin.valueChanged.connect(self.emit_style)
        outline_layout.addWidget(self.outline_spin, stretch=2)
        right_layout.addLayout(outline_layout)
        
        # 6. Vị trí (Xếp ngang hàng)
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Vị trí:", styleSheet="border: none; color: #98A2B3;"))
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["Bottom", "Top", "Center"])
        self.pos_combo.currentTextChanged.connect(self.emit_style)
        pos_layout.addWidget(self.pos_combo, stretch=2)
        right_layout.addLayout(pos_layout)
        
        right_layout.addStretch()
        splitter.addWidget(right_panel)
        
        # Đặt tỷ lệ mặc định 70% trái - 30% phải
        splitter.setSizes([700, 300])
        main_layout.addWidget(splitter)

    # ================= CÁC HÀM XỬ LÝ STYLE =================
    def _open_color_dialog(self, initial_color, title):
        """ Hàm hỗ trợ khởi tạo hộp thoại chọn màu với giao diện Dark Mode """
        dialog = QColorDialog(initial_color, self)
        dialog.setWindowTitle(title)
        
        # Bơm CSS cục bộ để ép hộp thoại này thành Dark Theme, nút bấm rõ ràng
        dialog.setStyleSheet("""
            QDialog, QColorDialog { background-color: #161B26; }
            QLabel { color: #F5F7FA; }
            QPushButton { 
                background-color: #2B3547; color: #FFFFFF; 
                border: 1px solid #273247; border-radius: 4px; 
                padding: 6px 12px; min-width: 60px;
            }
            QPushButton:hover { background-color: #38455A; border: 1px solid #35C8FF; }
        """)
        
        # Thực thi hộp thoại (chặn tương tác màn hình chính cho đến khi đóng)
        if dialog.exec():
            return dialog.currentColor()
        
        return QColor() # Trả về màu không hợp lệ (Invalid) nếu người dùng bấm Cancel

    def choose_text_color(self):
        color = self._open_color_dialog(self.current_text_color, "Chọn màu chữ")
        
        # Kiểm tra biến color an toàn trước khi áp dụng
        if color.isValid():
            self.current_text_color = color
            self.btn_text_color.setStyleSheet(f"color: {color.name()}; font-weight: bold; background: #2B3547; border: 1px solid #4AC1FF;")
            self.emit_style()

    def choose_outline_color(self):
        color = self._open_color_dialog(self.current_outline_color, "Chọn màu viền")
        
        if color.isValid():
            self.current_outline_color = color
            self.btn_outline_color.setStyleSheet(f"color: {color.name()}; font-weight: bold; background: #FFF; border: 1px solid #273247;")
            self.emit_style()

    def on_preview_toggled(self, checked):
        self.preview_toggled.emit(checked)

    def emit_style(self):
        if not hasattr(self, 'font_combo'): return

        # Xử lý an toàn: Kiểm tra pos_combo đã được tạo chưa (tránh lỗi NoneType lúc khởi tạo UI)
        current_pos = "Bottom"
        if hasattr(self, 'pos_combo'):
            current_pos = self.pos_combo.currentText()
        
        style_data = {
            "family": self.font_combo.currentText(),
            "size": self.size_spin.value(),
            "color": self.current_text_color.name(),
            "out_color": self.current_outline_color.name(),
            "out_width": self.outline_spin.value(),
            "position": current_pos
        }
        self.style_changed.emit(style_data)

    # ================= CÁC HÀM CŨ (GIỮ NGUYÊN) =================
    def load_srt_file(self, srt_path):
        self.srt_path = srt_path
        self.table.setRowCount(0)
        if not srt_path or not os.path.exists(srt_path): return

        with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        blocks = content.strip().split("\n\n")
        self.table.setRowCount(len(blocks))

        for row, block in enumerate(blocks):
            lines = block.split("\n")
            if len(lines) >= 3:
                index = lines[0]
                time_range = lines[1]
                text = "\n".join(lines[2:])

                times = time_range.split(" --> ")
                start = times[0] if len(times) > 0 else ""
                end = times[1] if len(times) > 1 else ""

                self.table.setItem(row, 0, QTableWidgetItem(index))
                self.table.setItem(row, 1, QTableWidgetItem(start))
                self.table.setItem(row, 2, QTableWidgetItem(end))
                self.table.setItem(row, 3, QTableWidgetItem(text))

    def on_row_double_clicked(self, row, column):
        start_item = self.table.item(row, 1)
        if start_item:
            time_str = start_item.text()
            ms = self.time_str_to_ms(time_str)
            self.seek_requested.emit(ms)

    def time_str_to_ms(self, time_str):
        try:
            time_str = time_str.strip()
            parts = time_str.replace(',', ':').split(':')
            if len(parts) == 4:
                h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                return (h * 3600 + m * 60 + s) * 1000 + ms
            return 0
        except Exception:
            return 0

    def save_srt(self):
        if not self.srt_path: return
        new_blocks = []
        for row in range(self.table.rowCount()):
            idx = self.table.item(row, 0)
            start = self.table.item(row, 1)
            end = self.table.item(row, 2)
            text = self.table.item(row, 3)

            if idx and start and end and text:
                new_blocks.append(f"{idx.text()}\n{start.text()} --> {end.text()}\n{text.text()}")
        try:
            with open(self.srt_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(new_blocks) + "\n")
            QMessageBox.information(self, "Thành công", "Đã lưu file SRT thành công!")
            self.srt_saved.emit(self.srt_path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu file: {str(e)}")

    def highlight_row_by_stt(self, stt):
        for row in range(self.table.rowCount()):
            item_stt = self.table.item(row, 0)
            if item_stt and item_stt.text() == str(stt):
                if not item_stt.isSelected():
                    self.table.selectRow(row)
                    self.table.scrollToItem(item_stt, QAbstractItemView.PositionAtCenter)
                return

    def clear_highlight(self):
        self.table.clearSelection()