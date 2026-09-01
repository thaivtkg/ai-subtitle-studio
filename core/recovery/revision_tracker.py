from PySide6.QtCore import QObject, Signal

from core.subtitle_editing.global_undo_manager import GlobalUndoManager


class RevisionTracker(QObject):
    """Track monotonic working-state revisions independently of undo history."""

    dirty_changed = Signal(bool)
    revision_changed = Signal(int)
    clean_point_reached = Signal(int)

    def __init__(self, undo_manager: GlobalUndoManager, parent=None):
        super().__init__(parent or undo_manager)
        self._undo_manager = undo_manager
        self._edit_revision = 0
        self._snapshot_revision = 0
        self._last_saved_revision = 0
        self._last_clean_revision = 0
        self._recovered_dirty_baseline = False
        self._last_dirty = False
        self._undo_manager.state_changed.connect(self.record_state_transition)

    @property
    def edit_revision(self) -> int:
        return self._edit_revision

    @property
    def snapshot_revision(self) -> int:
        return self._snapshot_revision

    @property
    def last_saved_revision(self) -> int:
        return self._last_saved_revision

    @property
    def last_clean_revision(self) -> int:
        return self._last_clean_revision

    @property
    def recovered_dirty_baseline(self) -> bool:
        return self._recovered_dirty_baseline

    @property
    def is_dirty(self) -> bool:
        return self._recovered_dirty_baseline or not self._undo_manager.undo_stack.isClean()

    def record_state_transition(self) -> int:
        """Record exactly one successful push, undo, or redo transition."""
        self._edit_revision += 1
        self.revision_changed.emit(self._edit_revision)
        if self._undo_manager.undo_stack.isClean() and not self._recovered_dirty_baseline:
            self._last_clean_revision = self._edit_revision
            self.clean_point_reached.emit(self._edit_revision)
        self._emit_dirty_change()
        return self._edit_revision

    def record_snapshot_success(self, revision: int) -> None:
        self._snapshot_revision = revision

    def record_explicit_save_success(self) -> None:
        self._undo_manager.mark_saved()
        self._last_saved_revision = self._edit_revision
        self._last_clean_revision = self._edit_revision
        self._recovered_dirty_baseline = False
        self._emit_dirty_change()

    def restore_from_snapshot(
        self,
        snapshot_revision: int,
        last_saved_revision: int,
        last_clean_revision: int,
    ) -> None:
        self._edit_revision = snapshot_revision
        self._snapshot_revision = snapshot_revision
        self._last_saved_revision = last_saved_revision
        self._last_clean_revision = last_clean_revision
        self._recovered_dirty_baseline = True
        self._emit_dirty_change()

    def reset_for_new_document(self) -> None:
        self._edit_revision = 0
        self._snapshot_revision = 0
        self._last_saved_revision = 0
        self._last_clean_revision = 0
        self._recovered_dirty_baseline = False
        self._emit_dirty_change()

    def _emit_dirty_change(self) -> None:
        dirty = self.is_dirty
        if dirty != self._last_dirty:
            self._last_dirty = dirty
            self.dirty_changed.emit(dirty)
