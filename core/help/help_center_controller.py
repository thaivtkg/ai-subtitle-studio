from .guide_card_policy import build_guide_card_view_model


class HelpCenterController:
    def __init__(self, guides, progress_provider, start_callback):
        self._guides = tuple(guides)
        self._progress_provider = progress_provider
        self._start_callback = start_callback
        self.cards = ()
        self.refresh()

    def refresh(self):
        self.cards = tuple(
            build_guide_card_view_model(
                guide, self._progress_provider(guide)
            )
            for guide in self._guides
        )
        return self.cards

    def search(self, query):
        needle = query.strip().casefold()
        if not needle:
            return self.cards
        return tuple(
            card for card in self.cards
            if needle in " ".join(
                (card.title, card.description, card.category)
            ).casefold()
        )

    def start_guide(self, guide_id):
        for guide in self._guides:
            if guide.guide_id == guide_id:
                self._start_callback(guide)
                return True
        return False
