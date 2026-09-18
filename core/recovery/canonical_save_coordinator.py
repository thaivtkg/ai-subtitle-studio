class CanonicalSaveCoordinator:
    """Debounce real project saves; recovery snapshots remain a separate system."""

    DEFAULT_DELAY_MS = 1000

    def __init__(
        self,
        *,
        revision_tracker,
        save_current_project,
        scheduler,
        active_project_provider,
        delay_ms=DEFAULT_DELAY_MS,
        enabled=True,
    ):
        self.revision_tracker = revision_tracker
        self.save_current_project = save_current_project
        self.scheduler = scheduler
        self.active_project_provider = active_project_provider
        self.delay_ms = delay_ms
        self.enabled = enabled
        self.presentation_state = "idle"
        self.recovery_protection_available = True
        self.recovery_cycle_cancelled = False
        self._handle = None
        self._connected = False

    def start(self):
        if not self._connected:
            self.revision_tracker.revision_changed.connect(self._on_revision_changed)
            self._connected = True
        self._schedule_if_eligible()

    def dispose(self):
        self._cancel()
        if self._connected:
            self.revision_tracker.revision_changed.disconnect(self._on_revision_changed)
            self._connected = False

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self._cancel()
            self.presentation_state = "idle"
            return
        self._schedule_if_eligible()

    def set_delay_ms(self, delay_ms):
        self.delay_ms = int(delay_ms)
        if self._handle is not None:
            self._schedule_if_eligible()

    def manual_save_succeeded(self):
        self._cancel()
        self.recovery_cycle_cancelled = True
        if self.revision_tracker.is_dirty:
            self._schedule_if_eligible()
        else:
            self.presentation_state = "saved"

    def cancel_pending(self):
        self._cancel()

    def flush_now(self):
        if not self._eligible():
            self._cancel()
            return True
        self._cancel()
        return self._attempt()

    def _on_revision_changed(self, revision):
        self._schedule_if_eligible(revision)

    def _schedule_if_eligible(self, revision=None):
        if not self._eligible(revision):
            return
        self._cancel()
        self._handle = self.scheduler.call_later(self.delay_ms, self._attempt)
        self.presentation_state = "pending"

    def _attempt(self):
        self._handle = None
        if not self._eligible():
            return True
        target_revision = self.revision_tracker.edit_revision
        self.presentation_state = "saving"
        try:
            result = self.save_current_project(
                reason="autosave",
                notify_user=False,
                target_revision=target_revision,
            )
        except (OSError, ValueError, RuntimeError):
            result = False
        if result:
            self.recovery_cycle_cancelled = True
            if self.revision_tracker.is_dirty:
                self._schedule_if_eligible()
            else:
                self.presentation_state = "saved"
        else:
            self.presentation_state = "save_failed"
        return bool(result and not self.revision_tracker.is_dirty)

    def _eligible(self, revision=None):
        if not self.enabled or not self.active_project_provider():
            return False
        if not self.revision_tracker.is_dirty:
            return False
        current_revision = (
            self.revision_tracker.edit_revision if revision is None else revision
        )
        return current_revision > self.revision_tracker.snapshot_revision

    def _cancel(self):
        if self._handle is not None:
            self.scheduler.cancel(self._handle)
            self._handle = None
