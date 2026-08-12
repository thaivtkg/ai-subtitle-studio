import os

from PySide6.QtCore import QObject, Signal


class QueueManager(QObject):
    # Signals để UI tự động cập nhật khi core thay đổi
    queue_updated = Signal()
    item_removed = Signal(str) # Phát ra vid_path bị xóa
    queue_cleared = Signal()

    def __init__(self):
        super().__init__()
        # Cấu trúc: { vid_path: {"srt_path": str, "status": str, "metadata": dict} }
        self._items = {}
        self.active_vid = None

    def add_video(self, vid_path):
        if not vid_path or not os.path.exists(vid_path) or vid_path in self._items:
            return False

        # [Auto Detect SRT]
        srt_path = None
        base_path = os.path.splitext(vid_path)[0]
        potential_srt = f"{base_path}.srt"
        if os.path.exists(potential_srt):
            srt_path = potential_srt

        self._items[vid_path] = {
            "srt_path": srt_path,
            "status": "Ready" if srt_path else "Waiting",
            "metadata": None # Sẽ load lazy (chỉ load khi click) để tối ưu RAM khi add 20 video
        }
        self.queue_updated.emit()
        return True

    def set_srt_for_video(self, vid_path, srt_path):
        if vid_path in self._items and os.path.exists(srt_path):
            self._items[vid_path]["srt_path"] = srt_path
            self._items[vid_path]["status"] = "Ready"
            self.queue_updated.emit()

    def update_metadata(self, vid_path, metadata_dict):
        if vid_path in self._items:
            self._items[vid_path]["metadata"] = metadata_dict

    def remove_video(self, vid_path):
        if vid_path in self._items:
            del self._items[vid_path]
            
            # [Safe Fallback Selection]
            if self.active_vid == vid_path:
                self.active_vid = list(self._items.keys())[0] if self._items else None
            
            self.item_removed.emit(vid_path)
            self.queue_updated.emit()

    def clear_queue(self):
        self._items.clear()
        self.active_vid = None
        self.queue_cleared.emit()
        self.queue_updated.emit()

    def get_items(self):
        return self._items

    def get_active_data(self):
        """ Trả về tuple (vid_path, srt_path) an toàn """
        if self.active_vid and self.active_vid in self._items:
            return self.active_vid, self._items[self.active_vid]["srt_path"]
        return None, None
        
    def set_active(self, vid_path):
        if vid_path in self._items:
            self.active_vid = vid_path
            self.queue_updated.emit() # Phát tín hiệu để UI highlight lại