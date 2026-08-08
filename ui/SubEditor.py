import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QMessageBox, QAbstractItemView, QHeaderView
)
from PySide6.QtCore import Qt, Signal


class SubtitleEditorWidget(QWidget):
    # Tín hiệu phát ra khi Double Click vào 1 dòng, mang theo tham số mili-giây
    seek_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.srt_path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Bảng hiển thị phụ đề
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["STT", "Bắt đầu", "Kết thúc", "Nội dung"])
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)

        # Cho cột Nội dung tự động giãn lấp đầy khoảng trống
        self.table.horizontalHeader().setStretchLastSection(True)

        # Cấu hình UI cho bảng
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #10141F; color: #F5F7FA; gridline-color: #273247; border: 1px solid #273247; border-radius: 4px; }
            QHeaderView::section { background-color: #161B26; color: #98A2B3; font-weight: bold; padding: 4px; border: 1px solid #273247; }
            QTableWidget::item:selected { background-color: #35C8FF; color: #0D111A; font-weight: bold; }
        """)

        # Bắt sự kiện Double Click để Seek Video
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Lưu thay đổi (Ctrl+S)")
        self.save_btn.setObjectName("btn_secondary")
        self.save_btn.clicked.connect(self.save_srt)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def load_srt_file(self, srt_path):
        self.srt_path = srt_path
        self.table.setRowCount(0)
        if not srt_path or not os.path.exists(srt_path):
            return

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
        # Lấy thời gian bắt đầu của dòng được click
        start_item = self.table.item(row, 1)
        if start_item:
            time_str = start_item.text()
            ms = self.time_str_to_ms(time_str)
            self.seek_requested.emit(ms)  # Phát tín hiệu yêu cầu nhảy video

    def time_str_to_ms(self, time_str):
        """ Chuyển đổi '00:01:15,000' thành số nguyên 75000 mili-giây """
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
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu file: {str(e)}")

    def highlight_subtitle_at_time(self, ms):
        """ Highlight dòng phụ đề khớp với thời gian hiện tại của video """
        if self.table.rowCount() == 0:
            return

        for row in range(self.table.rowCount()):
            start_item = self.table.item(row, 1)
            end_item = self.table.item(row, 2)

            if start_item and end_item:
                start_ms = self.time_str_to_ms(start_item.text())
                end_ms = self.time_str_to_ms(end_item.text())

                # Kiểm tra nếu thời gian video nằm trong khoảng sub
                if start_ms <= ms <= end_ms:
                    # Nếu dòng này chưa được chọn thì mới select và scroll (tránh giật lag UI)
                    current_item = self.table.item(row, 0)
                    if current_item and not current_item.isSelected():
                        self.table.selectRow(row)
                        # Tự động cuộn bảng sao cho dòng đang đọc nằm ở giữa màn hình
                        self.table.scrollToItem(current_item, QAbstractItemView.PositionAtCenter)
                    return  # Đã tìm thấy dòng khớp thời gian thì thoát vòng lặp