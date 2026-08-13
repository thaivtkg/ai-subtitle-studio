import os

from PySide6.QtCore import QObject, Signal


class QueueManager(QObject):
    queue_updated = Signal()
    active_changed = Signal(str)  # [Fix] Signal độc lập cho việc thay đổi Video đang chọn
    item_removed = Signal(str)
    queue_cleared = Signal()

    def __init__(self):
        super().__init__()
        self._items = {}
        self.active_vid = None

    def add_video(self, vid_path):
        if not vid_path or not os.path.exists(vid_path) or vid_path in self._items:
            return False

        base_path = os.path.splitext(vid_path)[0]
        potential_srt = f"{base_path}.srt"
        srt_path = potential_srt if os.path.exists(potential_srt) else None

        self._items[vid_path] = {
            "srt_path": srt_path,
            "status": "Ready" if srt_path else "Waiting",
            "metadata": None
        }
        # Tự động phát signal duy nhất từ Manager
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
            self.queue_updated.emit()

    def remove_video(self, vid_path):
        if vid_path in self._items:
            keys = list(self._items.keys())
            idx = keys.index(vid_path)
            
            del self._items[vid_path]
            
            if self.active_vid == vid_path:
                remaining_keys = list(self._items.keys())
                if remaining_keys:
                    new_idx = min(idx, len(remaining_keys) - 1)
                    self.active_vid = remaining_keys[new_idx]
                    # [Fix] Phát signal chuyển active
                    self.active_changed.emit(self.active_vid)
                else:
                    self.active_vid = None
            
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
        if self.active_vid and self.active_vid in self._items:
            return self.active_vid, self._items[self.active_vid]["srt_path"]
        return None, None
        
    def set_active(self, vid_path):
        if vid_path in self._items:
            self.active_vid = vid_path
            # [Fix] Tuyệt đối không emit queue_updated ở đây nữa
            self.active_changed.emit(vid_path)