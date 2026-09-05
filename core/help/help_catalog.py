import unicodedata

from .help_models import HelpSearchResult, SearchResultType


def _normalize(value):
    return " ".join(unicodedata.normalize("NFKD", value or "").casefold().split())


class HelpCatalog:
    def search(self, query, *, cards=(), shortcuts=()):
        needle = _normalize(query)
        if not needle:
            return ()
        results = []
        for card in cards:
            if any(needle in _normalize(value) for value in (card.title, card.description, card.category)):
                results.append(HelpSearchResult(SearchResultType.GUIDE, card.guide_id, card.title, card.description, card.category))
        for shortcut in shortcuts:
            if any(needle in _normalize(value) for value in (shortcut.label, shortcut.sequence, shortcut.context)):
                results.append(HelpSearchResult(SearchResultType.SHORTCUT, shortcut.action_id, shortcut.label, shortcut.sequence, shortcut.context))
        return tuple(results)
