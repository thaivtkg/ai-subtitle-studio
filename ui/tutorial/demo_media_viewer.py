from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.tutorial.models import MediaSpec


class DemoMediaViewer(QWidget):
    """Render local static images and GIFs for Guided Tour demos."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("demo_media_viewer")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.media_label = QLabel(self)
        self.media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.media_label.setScaledContents(True)
        layout.addWidget(self.media_label)

        self._current_pixmap: Optional[QPixmap] = None
        self._current_movie: Optional[QMovie] = None

    def set_media(self, spec: MediaSpec) -> None:
        if spec.type not in ("image", "gif"):
            raise ValueError(
                f"Unsupported media type: '{spec.type}'. "
                "Only 'image' and 'gif' are supported."
            )

        self._cleanup_resources()

        if spec.type == "image":
            self._current_pixmap = QPixmap(spec.path)
            self.media_label.setPixmap(self._current_pixmap)
        else:
            self._current_movie = QMovie(spec.path)
            self.media_label.setMovie(self._current_movie)
            if self.isVisible():
                self._current_movie.start()

    def current_pixmap(self) -> Optional[QPixmap]:
        return self._current_pixmap

    def current_movie(self) -> Optional[QMovie]:
        return self._current_movie

    def is_playing(self) -> bool:
        return bool(self._current_movie and self._current_movie.state() == QMovie.MovieState.Running)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._current_movie and self._current_movie.state() != QMovie.MovieState.Running:
            self._current_movie.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if self._current_movie and self._current_movie.state() == QMovie.MovieState.Running:
            self._current_movie.setPaused(True)

    def _cleanup_resources(self) -> None:
        if self._current_movie:
            self._current_movie.stop()
            self._current_movie.deleteLater()
            self._current_movie = None
        self._current_pixmap = None
        self.media_label.clear()
