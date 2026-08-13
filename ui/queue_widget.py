from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QSplitter
from PySide6.QtCore import Qt, Signal
from ui.queue_item import QueueItemWidget
from ui.video_info_widget import VideoInfoWidget

class QueueWidget(QWidget):
    item_clicked = Signal(str)
    item_removed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; height: 6px; }")

        # Nửa Trên: Danh sách Queue
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

        # Nửa Dưới: Thông tin Video
        self.info_panel = VideoInfoWidget()
        splitter.addWidget(self.info_panel)
        
        # [FIX] Đặt tỷ lệ 1:0 và cấp phát kích thước khởi tạo [320, 155]
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([320, 170])
        
        layout.addWidget(splitter)
        self._items = {}

    def sync_with_manager(self, queue_items, active_vid):
        to_remove = [vid for vid in self._items if vid not in queue_items]
        for vid in to_remove:
            widget = self._items.pop(vid)
            self.list_layout.removeWidget(widget)
            widget.deleteLater()

        for vid_path, data in queue_items.items():
            status = data.get("status", "Waiting")
            has_srt = bool(data.get("srt_path"))
            meta = data.get("metadata")
            duration = meta.get("duration", "--:--:--") if meta else "--:--:--"

            if vid_path not in self._items:
                item_widget = QueueItemWidget(vid_path, status, has_srt, duration)
                item_widget.clicked_signal.connect(self.item_clicked.emit)
                item_widget.remove_signal.connect(self.item_removed.emit)
                self.list_layout.addWidget(item_widget)
                self._items[vid_path] = item_widget
            else:
                self._items[vid_path].update_details_text(status, has_srt, duration)

            self._items[vid_path].set_active(vid_path == active_vid)

        if active_vid and active_vid in queue_items:
            self.info_panel.update_info(
                active_vid, 
                queue_items[active_vid].get("metadata"), 
                queue_items[active_vid].get("srt_path")
            )
        else:
            self.info_panel.clear_info()