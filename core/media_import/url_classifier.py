from enum import Enum
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit


class MediaURLType(str, Enum):
    DIRECT_MEDIA = "DIRECT_MEDIA"
    PAGE_OR_EXTRACTOR = "PAGE_OR_EXTRACTOR"


class URLClassifier:
    _DIRECT_MEDIA_EXTENSIONS = {
        ".aac",
        ".avi",
        ".flac",
        ".m2ts",
        ".m4a",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".ogg",
        ".opus",
        ".ts",
        ".wav",
        ".webm",
        ".wma",
    }

    def classify(self, url: str) -> MediaURLType:
        try:
            path = unquote(urlsplit(url).path)
        except ValueError:
            return MediaURLType.PAGE_OR_EXTRACTOR
        if PurePosixPath(path).suffix.lower() in self._DIRECT_MEDIA_EXTENSIONS:
            return MediaURLType.DIRECT_MEDIA
        return MediaURLType.PAGE_OR_EXTRACTOR

    def is_obvious_direct_media(self, url: str, content_type: str | None = None) -> bool:
        if self.classify(url) is MediaURLType.DIRECT_MEDIA:
            return True
        media_type = (content_type or "").partition(";")[0].strip().lower()
        return media_type.startswith(("audio/", "video/"))
