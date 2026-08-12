from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QSplitter
from PySide6.QtCore import Qt, Signal
from ui.queue_item import QueueItemWidget
from ui.video_info_widget import VideoInfoWidget

class QueueWidget(QWidget):
    # Signals phát ra để Gui.py bắt
    item_clicked = Signal(str)
    item_removed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #273247; width: 2px; }")

        # Nửa Trái: Danh sách Queue
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(6)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_area.setWidget(self.list_container)
        
        splitter.addWidget(self.scroll_area)

        # Nửa Phải: Thông tin Video
        self.info_panel = VideoInfoWidget()
        splitter.addWidget(self.info_panel)
        
        # Chia tỷ lệ 60 - 40
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)
        
        self._items = {} # Cache quản lý Widget để tối ưu hiệu suất

    def sync_with_manager(self, queue_items, active_vid):
        """ 
        [Optimization] 
        Thay vì clear layout và tạo lại toàn bộ mỗi lần có thay đổi,
        hàm này chỉ thêm mới/cập nhật những widget cần thiết. Tránh lag khi Stress Test 20+ video.
        """
        # 1. Xóa widget của các video không còn trong danh sách
        to_remove = [vid for vid in self._items if vid not in queue_items]
        for vid in to_remove:
            widget = self._items.pop(vid)
            self.list_layout.removeWidget(widget)
            widget.deleteLater()

        # 2. Thêm mới hoặc cập nhật widget hiện có
        for vid_path, data in queue_items.items():
            status = data.get("status", "Waiting")
            has_srt = bool(data.get("srt_path"))
            meta = data.get("metadata")
            duration = meta.get("duration", "--:--:--") if meta else "--:--:--"

            if vid_path not in self._items:
                # Tạo widget mới
                item_widget = QueueItemWidget(vid_path, status, has_srt, duration)
                item_widget.clicked_signal.connect(self.item_clicked.emit)
                item_widget.remove_signal.connect(self.item_removed.emit)
                self.list_layout.addWidget(item_widget)
                self._items[vid_path] = item_widget
            else:
                # Cập nhật thông tin nhanh cho widget cũ (chống nhấp nháy UI)
                widget = self._items[vid_path]
                status_icon = "🟢" if status == "Ready" else "🟡"
                widget.lbl_status.setText(f"{status_icon} {status}")
                widget.lbl_srt.setText("📝 Có sẵn SRT" if has_srt else "🤖 Cần AI")
                widget.lbl_srt.setStyleSheet(f"color: {'#33D17A' if has_srt else '#F5B942'}; font-size: 11px; font-weight: bold;")
                widget.lbl_duration.setText(f"⏱ {duration}")

            # Đặt trạng thái Active (Sáng viền)
            self._items[vid_path].set_active(vid_path == active_vid)

        # 3. Cập nhật bảng Thông tin
        if active_vid and active_vid in queue_items:
            self.info_panel.update_info(
                active_vid, 
                queue_items[active_vid].get("metadata"), 
                queue_items[active_vid].get("srt_path")
            )
        else:
            self.info_panel.clear_info()