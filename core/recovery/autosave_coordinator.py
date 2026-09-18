from copy import deepcopy


class AutosaveCoordinator:
    """Schedule dirty working-state snapshots without owning project state."""

    INACTIVITY_MS = 30_000
    MAX_CYCLE_MS = 120_000

    def __init__(
        self,
        revision_tracker,
        session_provider,
        snapshot_provider,
        persist_snapshot,
        scheduler,
        activity_logger=None,
    ):
        self.revision_tracker = revision_tracker
        self.session_provider = session_provider
        self.snapshot_provider = snapshot_provider
        self.persist_snapshot = persist_snapshot
        self.scheduler = scheduler
        self.activity_logger = activity_logger
        self._inactivity_handle = None
        self._max_handle = None
        self._retry_handle = None
        self._cycle_token = None
        self._bound = False
        self._bound_session_id = None
        self._generation = 0
        self._connected = False
        self._last_snapshot_revision = revision_tracker.snapshot_revision

    def start(self):
        if not self._connected:
            self.revision_tracker.revision_changed.connect(self._on_revision_changed)
            self._connected = True
        self._bound = True
        if self.revision_tracker.is_dirty:
            self._ensure_cycle(self.revision_tracker.edit_revision)

    def bind_session(self, session_id=None):
        if self._bound and self._bound_session_id == session_id:
            self._ensure_cycle_if_dirty()
            return
        self._generation += 1
        self._bound = True
        self._bound_session_id = session_id
        self._cancel_cycle()
        self._ensure_cycle_if_dirty()

    def clear_session(self):
        self._generation += 1
        self._bound = False
        self._bound_session_id = None
        self._cancel_cycle()

    def manual_save_succeeded(self):
        self._cancel_cycle()

    def dispose(self):
        self._cancel_cycle()
        if self._connected:
            self.revision_tracker.revision_changed.disconnect(self._on_revision_changed)
            self._connected = False
        self._bound = False
        self._bound_session_id = None
        self._generation += 1

    def trigger_now(self):
        """Run the current eligible callback immediately for explicit fallback paths."""
        if not self._bound:
            return
        if self._cycle_token is None:
            self._ensure_cycle_if_dirty()
        if self._cycle_token is not None:
            self._attempt(self._cycle_token)

    def _on_revision_changed(self, revision):
        if not self._bound:
            return
        if self.revision_tracker.is_dirty and revision > self.revision_tracker.snapshot_revision:
            self._ensure_cycle(revision)

    def _ensure_cycle_if_dirty(self):
        if self.revision_tracker.is_dirty and self.revision_tracker.edit_revision > self.revision_tracker.snapshot_revision:
            self._ensure_cycle(self.revision_tracker.edit_revision)

    def _ensure_cycle(self, revision):
        token = self._current_token()
        if token is None:
            return
        if self._cycle_token != token:
            self._cancel_cycle()
            self._cycle_token = token
            self._max_handle = self.scheduler.call_later(
                self.MAX_CYCLE_MS,
                lambda captured=token: self._attempt(captured),
            )
        self._cancel_handle("_inactivity_handle")
        self._inactivity_handle = self.scheduler.call_later(
            self.INACTIVITY_MS,
            lambda captured=token: self._attempt(captured),
        )

    def _attempt(self, captured_token):
        if captured_token != self._current_token():
            return
        if not self.revision_tracker.is_dirty:
            self._cancel_cycle()
            return
        revision = self.revision_tracker.edit_revision
        if revision <= self.revision_tracker.snapshot_revision:
            self._cancel_cycle()
            return

        try:
            state = deepcopy(self.snapshot_provider())
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            self._failed_attempt(captured_token, error)
            return

        if captured_token != self._current_token():
            return

        try:
            result = self.persist_snapshot(state)
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            self._failed_attempt(captured_token, error)
            return

        if result is False:
            self._failed_attempt(captured_token, None)
            return

        self._last_snapshot_revision = self.revision_tracker.snapshot_revision
        self._log("autosave succeeded", revision=revision)
        self._cancel_cycle()

    def _failed_attempt(self, captured_token, error):
        self._log("autosave failed", error=error)
        if captured_token != self._current_token():
            return
        if not self.revision_tracker.is_dirty:
            return
        if self.revision_tracker.edit_revision <= self.revision_tracker.snapshot_revision:
            return
        self._cancel_handle("_retry_handle")
        self._retry_handle = self.scheduler.call_later(
            self.INACTIVITY_MS,
            lambda captured=captured_token: self._attempt(captured),
        )

    def _current_token(self):
        if not self._bound:
            return None
        identity = self.session_provider()
        if identity is None:
            return None
        if isinstance(identity, dict):
            session_id = identity.get("session_id")
            provider_generation = identity.get("generation")
        else:
            session_id = getattr(identity, "session_id", None)
            provider_generation = getattr(identity, "generation", None)
        if not session_id:
            return None
        return self._generation, provider_generation, session_id

    def _cancel_cycle(self):
        self._cancel_handle("_inactivity_handle")
        self._cancel_handle("_max_handle")
        self._cancel_handle("_retry_handle")
        self._cycle_token = None

    def _cancel_handle(self, name):
        handle = getattr(self, name)
        if handle is not None:
            self.scheduler.cancel(handle)
            setattr(self, name, None)

    def _log(self, message, **details):
        if self.activity_logger is not None:
            self.activity_logger({"event": message, **details})
