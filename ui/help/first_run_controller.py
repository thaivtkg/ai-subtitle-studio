from core.help.first_run_policy import (
    FirstRunDecision,
    dismiss_first_run,
    evaluate_startup,
    start_first_run,
)


class FirstRunController:
    """Coordinate first-run policy decisions with the banner and TourEngine."""

    def __init__(
        self,
        progress_store,
        engine,
        banner,
        target_guide_id: str,
        target_content_version: int = 1,
    ):
        self.progress_store = progress_store
        self.engine = engine
        self.banner = banner
        self.target_guide_id = target_guide_id
        self.target_content_version = target_content_version
        self.banner.dismiss_btn.clicked.connect(self._on_dismiss)
        self.banner.start_btn.clicked.connect(self._on_start)

    def evaluate_and_show(
        self, external_open=False, recovery=False, workflow_started=False
    ):
        decision = evaluate_startup(
            self.progress_store,
            self.target_guide_id,
            self.target_content_version,
            external_open=external_open,
            recovery=recovery,
            workflow_started=workflow_started,
        )
        self.banner.setVisible(decision == FirstRunDecision.SHOW_BANNER)

    def on_workflow_started(self):
        self.banner.hide()

    def _on_dismiss(self):
        dismiss_first_run(
            self.progress_store, self.target_guide_id, self.target_content_version
        )
        self.banner.hide()

    def _on_start(self):
        start_first_run(
            self.progress_store,
            self.target_guide_id,
            self.target_content_version,
            self.engine.start,
        )
        self.banner.hide()
