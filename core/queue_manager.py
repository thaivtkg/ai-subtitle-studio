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
        self.active_item_key = None
        self._last_added_key = None

    @staticmethod
    def _same_path(left, right):
        if not left or not right:
            return False
        return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
            os.path.abspath(str(right))
        )

    @staticmethod
    def _video_path(item_key, data):
        return data.get("video_path", item_key)

    def _matches_binding(self, data, project_id=None, project_root=None):
        if project_id is not None and data.get("project_id") != project_id:
            return False
        if project_root is not None and not self._same_path(
            data.get("project_root"), project_root
        ):
            return False
        return project_id is not None or project_root is not None

    def _find_item_key(self, identifier, project_id=None, project_root=None):
        if identifier in self._items:
            data = self._items[identifier]
            if not (project_id is not None or project_root is not None) or self._matches_binding(
                data, project_id, project_root
            ):
                return identifier

        candidates = [
            (key, data)
            for key, data in self._items.items()
            if self._same_path(self._video_path(key, data), identifier)
        ]
        if project_id is not None or project_root is not None:
            for key, data in candidates:
                if self._matches_binding(data, project_id, project_root):
                    return key
            return None
        if self.active_item_key in {key for key, _ in candidates}:
            return self.active_item_key
        if len(candidates) == 1:
            return candidates[0][0]
        return None

    def add_video(self, vid_path, project_id=None, project_root=None):
        if not vid_path or not os.path.exists(vid_path):
            return False

        item_key = str(vid_path)
        if item_key in self._items:
            existing = self._items[item_key]
            if not (project_id is not None or project_root is not None):
                return False
            if self._matches_binding(existing, project_id, project_root):
                return False
            suffix = project_id or os.path.normpath(str(project_root))
            item_key = f"{vid_path}::project::{suffix}"
            counter = 2
            while item_key in self._items:
                item_key = f"{vid_path}::project::{suffix}::{counter}"
                counter += 1

        base_path = os.path.splitext(vid_path)[0]
        potential_srt = f"{base_path}.srt"
        srt_path = potential_srt if os.path.exists(potential_srt) else None

        self._items[item_key] = {
            "video_path": str(vid_path),
            "srt_path": srt_path,
            "status": "Ready" if srt_path else "Waiting",
            "metadata": None,
            "project_id": project_id,
            "project_root": project_root,
        }
        self._last_added_key = item_key
        # Tự động phát signal duy nhất từ Manager
        self.queue_updated.emit()
        return True

    def get_item(self, identifier):
        key = self._find_item_key(identifier)
        return self._items.get(key) if key is not None else None

    def get_item_key(self, identifier, project_id=None, project_root=None):
        return self._find_item_key(identifier, project_id, project_root)

    def ensure_project_binding(self, vid_path, project_id=None, project_root=None):
        key = self._find_item_key(vid_path, project_id, project_root)
        if key is not None:
            data = self._items[key]
            if data.get("project_id") is None and data.get("project_root") is None:
                data["project_id"] = project_id
                data["project_root"] = project_root
                self.queue_updated.emit()
            return key

        unbound_key = self._find_item_key(vid_path)
        if unbound_key is not None:
            data = self._items[unbound_key]
            if data.get("project_id") is None and data.get("project_root") is None:
                data["project_id"] = project_id
                data["project_root"] = project_root
                self.queue_updated.emit()
                return unbound_key

        if not self.add_video(vid_path, project_id, project_root):
            return None
        return self._last_added_key

    def bind_project(self, identifier, project_id=None, project_root=None):
        key = self._find_item_key(identifier)
        if key is None:
            return None
        self._items[key]["project_id"] = project_id
        self._items[key]["project_root"] = project_root
        self.queue_updated.emit()
        return key

    def set_srt_for_video(self, vid_path, srt_path):
        item_key = self._find_item_key(vid_path)
        if item_key is not None and os.path.exists(srt_path):
            self._items[item_key]["srt_path"] = srt_path
            self._items[item_key]["status"] = "Ready"
            self.queue_updated.emit()

    def update_metadata(self, vid_path, metadata_dict):
        item_key = self._find_item_key(vid_path)
        if item_key is not None:
            self._items[item_key]["metadata"] = metadata_dict
            self.queue_updated.emit()

    def remove_video(self, vid_path):
        item_key = self._find_item_key(vid_path)
        if item_key is not None:
            keys = list(self._items.keys())
            idx = keys.index(item_key)
            
            del self._items[item_key]
            
            if self.active_item_key == item_key:
                remaining_keys = list(self._items.keys())
                if remaining_keys:
                    new_idx = min(idx, len(remaining_keys) - 1)
                    self.active_item_key = remaining_keys[new_idx]
                    self.active_vid = self._video_path(
                        self.active_item_key, self._items[self.active_item_key]
                    )
                    # [Fix] Phát signal chuyển active
                    self.active_changed.emit(self.active_item_key)
                else:
                    self.active_vid = None
                    self.active_item_key = None
            
            self.item_removed.emit(item_key)
            self.queue_updated.emit()

    def clear_queue(self):
        self._items.clear()
        self.active_vid = None
        self.active_item_key = None
        self.queue_cleared.emit()
        self.queue_updated.emit()

    def get_items(self):
        return self._items

    def get_active_data(self):
        if self.active_item_key and self.active_item_key in self._items:
            data = self._items[self.active_item_key]
            return self._video_path(self.active_item_key, data), data["srt_path"]
        return None, None
        
    def set_active(self, vid_path):
        item_key = self._find_item_key(vid_path)
        if item_key is not None:
            self.active_item_key = item_key
            self.active_vid = self._video_path(item_key, self._items[item_key])
            # [Fix] Tuyệt đối không emit queue_updated ở đây nữa
            self.active_changed.emit(item_key)
