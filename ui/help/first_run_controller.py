class FirstRunController:
    """C2 UI scaffold; banner orchestration is intentionally not implemented yet."""

    def __init__(self, progress_store, engine, banner, target_guide_id):
        self.progress_store = progress_store
        self.engine = engine
        self.banner = banner
        self.target_guide_id = target_guide_id

    def evaluate_and_show(
        self, external_open=False, recovery=False, workflow_started=False
    ):
        pass

    def on_workflow_started(self):
        pass
