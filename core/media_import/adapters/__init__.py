__all__ = ["DirectHTTPAdapter"]


def __getattr__(name):
    if name == "DirectHTTPAdapter":
        from .direct_http_adapter import DirectHTTPAdapter

        return DirectHTTPAdapter
    raise AttributeError(name)
