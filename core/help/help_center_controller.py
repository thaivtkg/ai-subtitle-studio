from .guide_card_policy import build_guide_card_view_model
from .help_catalog import HelpCatalog
from .help_models import GuideStartResult, GuideStartStatus


class HelpCenterController:
    def __init__(self, catalog, progress_store, environment, engine=None,
                 start_tour_fn=None, help_catalog=None, shortcut_provider=None):
        self._catalog = catalog
        self._progress_store = progress_store
        self._environment = environment
        self._start_tour_fn = start_tour_fn or (engine.start if engine else None)
        self._help_catalog = help_catalog or HelpCatalog()
        self._shortcut_provider = shortcut_provider

    def check_preconditions(self, guide):
        for precondition in getattr(guide, "preconditions", ()):
            key = getattr(precondition, "value", precondition)
            if self._environment is not None and not self._environment.check(key):
                return False, f"Precondition failed: {key}"
        return True, None

    def build_guide_cards(self):
        guides = self._catalog.load_all() if hasattr(self._catalog, "load_all") else self._catalog.all_guides()
        cards = []
        for guide in guides:
            passed, reason = self.check_preconditions(guide)
            progress = self._progress_store.status(guide.guide_id, guide.content_version)
            cards.append(build_guide_card_view_model(guide, progress, enabled=passed, blocked_reason=reason))
        return tuple(cards)

    def start_guide(self, guide_id):
        guide = self._catalog.get_guide(guide_id)
        if guide is None:
            return GuideStartResult(GuideStartStatus.START_FAILED, guide_id, f"Guide '{guide_id}' not found")
        passed, reason = self.check_preconditions(guide)
        if not passed:
            return GuideStartResult(GuideStartStatus.PRECONDITION_FAILED, guide_id, reason)
        if self._start_tour_fn is None:
            return GuideStartResult(GuideStartStatus.START_FAILED, guide_id, "Tour engine unavailable")
        if self._start_tour_fn(guide_id):
            return GuideStartResult(GuideStartStatus.READY, guide_id)
        return GuideStartResult(GuideStartStatus.START_FAILED, guide_id, "Tour engine rejected start")

    def search(self, query):
        return self._help_catalog.search(query, cards=self.build_guide_cards(), shortcuts=self.get_shortcuts())

    def get_shortcuts(self):
        return self._shortcut_provider.get_shortcuts() if self._shortcut_provider else ()
