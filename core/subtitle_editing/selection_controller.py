from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import QObject, Signal


class SelectionSource(Enum):
    EDITOR = auto()
    TIMELINE = auto()
    PLAYBACK = auto()
    PROGRAMMATIC = auto()


class SubtitleSelectionController(QObject):
    """Nguồn chân lý duy nhất (Single Source of Truth) cho trạng thái Selection."""

    # Sử dụng object để cho phép truyền đồng thời str (segment_id) hoặc None
    selection_changed = Signal(int, object, SelectionSource)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_index: int = -1
        self._selected_segment_id: Optional[str] = None

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @property
    def selected_segment_id(self) -> Optional[str]:
        return self._selected_segment_id

    def select(
        self,
        index: int,
        segment_id: Optional[str],
        source: SelectionSource = SelectionSource.PROGRAMMATIC,
    ):
        """Cập nhật trạng thái và phát tín hiệu đồng bộ xuống các View."""
        if self._selected_index == index and self._selected_segment_id == segment_id:
            return

        self._selected_index = index
        self._selected_segment_id = segment_id
        self.selection_changed.emit(index, segment_id, source)

    def clear_selection(
        self, source: SelectionSource = SelectionSource.PROGRAMMATIC
    ):
        """Bỏ chọn toàn bộ, truyền segment_id = None."""
        self.select(-1, None, source)
