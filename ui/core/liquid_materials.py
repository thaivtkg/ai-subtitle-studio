from __future__ import annotations

from math import exp, hypot
from typing import Optional

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, QElapsedTimer, Signal, Qt
from PySide6.QtGui import QColor, QImage, QPixmap, QPainter, QPainterPath

# ============================================================
# LIQUID GLASS MATERIAL TOKENS
# Three hierarchy levels + popup/active variants.
# Values are visual-engineering targets, not Apple's private values.
# ============================================================
MATERIALS = {
    "drawer": {
        "blur": 24,
        "diffusion": 0.16,
        "tint": 0.10,
        "saturation": 1.08,
        "dark_edge": 0.18,
        "specular": 0.32,
        "shadow": 0.18,
        "refraction_x": 0.0,
        "refraction_y": 0.0,
    },
    "surface": {
        "fill": 0.045,
        "blur": 16,
        "tint": 0.04,
        "dark_edge": 0.08,
        "specular": 0.15,
        "shadow": 0.0,
        "refraction_x": 0.0,
        "refraction_y": 0.0,
    },
    "control": {
        "fill": 0.07,
        "blur": 14,
        "tint": 0.05,
        "dark_edge": 0.10,
        "specular": 0.20,
        "shadow": 0.08,
        "refraction_x": 1.0,
        "refraction_y": 0.5,
    },
    "popup": {
        "blur": 24,
        "diffusion": 0.14,
        "tint": 0.12,
        "dark_edge": 0.25,
        "specular": 0.48,
        "shadow": 0.20,
        "refraction_x": 2.0,
        "refraction_y": 0.8,
    },
    "active": {
        "tint": 0.16,
        "specular": 0.48,
        "dark_edge": 0.22,
        "scale": 1.015,
        "refraction_x": 2.2,
        "refraction_y": 1.0,
    },
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def blend_tint(base: QColor, tint: QColor, amount: float) -> QColor:
    """Linear-ish visual blend used for context-aware tinting."""
    a = _clamp01(amount)
    return QColor(
        round(base.red() * (1 - a) + tint.red() * a),
        round(base.green() * (1 - a) + tint.green() * a),
        round(base.blue() * (1 - a) + tint.blue() * a),
        base.alpha(),
    )


def image_average_color(image: QImage) -> QColor:
    """Cheap average color: collapse a tiny resized sample to 1x1."""
    if image.isNull():
        return QColor(128, 128, 128)
    sample = image.scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return QColor(sample.pixel(0, 0))


class SharedBackdropCache(QObject):
    """One backdrop capture shared by Drawer materials.

    IMPORTANT: update_cache() should receive the widget that is *behind* the
    Drawer (typically centralWidget/content host), not MainWindow when the
    Drawer is already visible. This prevents recursive self-capture.
    """

    _instance: Optional['SharedBackdropCache'] = None
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._source = None
        self._raw: Optional[QImage] = None
        self._blurred: Optional[QImage] = None
        self._source_size = QRect()
        self._generation = 0

    @classmethod
    def get_instance(cls) -> 'SharedBackdropCache':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def generation(self) -> int:
        return self._generation

    def update_cache(self, source_widget) -> None:
        if source_widget is None or not source_widget.isVisible():
            return

        pixmap = source_widget.grab(source_widget.rect())
        if pixmap.isNull():
            return

        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)

        # Normalize to logical widget size so callers can use QWidget geometry
        # directly even on high-DPI displays.
        logical_size = source_widget.size()
        if logical_size.width() > 0 and logical_size.height() > 0 and image.size() != logical_size:
            image = image.scaled(
                logical_size,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )

        # Fast diffusion approximation: downsample then upsample.
        # This is intentionally cheap enough to refresh on resize/scene changes.
        dw = max(1, image.width() // 8)
        dh = max(1, image.height() // 8)
        small = image.scaled(dw, dh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        blurred = small.scaled(image.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        self._source = source_widget
        self._raw = image
        self._blurred = blurred
        self._source_size = source_widget.rect()
        self._generation += 1
        self.changed.emit()

    def is_ready(self) -> bool:
        return self._blurred is not None and not self._blurred.isNull()

    def _widget_to_source_rect(self, widget, rect: QRect) -> QRect:
        if self._source is None:
            return QRect()
        global_top_left = widget.mapToGlobal(rect.topLeft())
        source_top_left = self._source.mapFromGlobal(global_top_left)
        return QRect(source_top_left, rect.size())

    def crop_for(self, widget, rect: QRect, offset_x: float = 0.0, offset_y: float = 0.0) -> QPixmap:
        if not self.is_ready():
            return QPixmap()

        src_rect = self._widget_to_source_rect(widget, rect)
        src_rect.translate(round(offset_x), round(offset_y))
        src_rect = src_rect.intersected(self._source_size)
        if src_rect.isEmpty():
            return QPixmap()

        return QPixmap.fromImage(self._blurred.copy(src_rect))

    def sample_color_for(self, widget, rect: QRect, offset_x: float = 0.0, offset_y: float = 0.0) -> QColor:
        if not self.is_ready():
            return QColor(128, 128, 128)
        src_rect = self._widget_to_source_rect(widget, rect)
        src_rect.translate(round(offset_x), round(offset_y))
        src_rect = src_rect.intersected(self._blurred.rect())
        if src_rect.isEmpty():
            return QColor(128, 128, 128)
        return image_average_color(self._blurred.copy(src_rect))


class LiquidMotionController(QObject):
    """Frame-rate-independent spring motion with material lag."""

    updated = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.x = self.y = self.w = self.h = 0.0
        self.scale = 1.0
        self.tint = 0.0
        self.specular = 0.0
        self.highlight_x = 0.0
        self.highlight_y = 0.0

        self._targets = {
            "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0,
            "scale": 1.0, "tint": 0.0, "specular": 0.0,
        }
        self._vel = {key: 0.0 for key in self._targets}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._clock.start()

    def set_immediate(self, x: float, y: float, w: float, h: float,
                      scale: float = 1.0, tint: float = 0.08,
                      specular: float = 0.20) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h
        self.scale, self.tint, self.specular = scale, tint, specular
        self.highlight_x, self.highlight_y = x, y
        for key, value in {
            "x": x, "y": y, "w": w, "h": h,
            "scale": scale, "tint": tint, "specular": specular,
        }.items():
            self._targets[key] = value
            self._vel[key] = 0.0
        self.updated.emit()

    def set_target(self, x: float, y: float, w: float, h: float,
                   scale: float = 1.0, tint: float = 0.08,
                   specular: float = 0.20) -> None:
        self._targets.update({
            "x": x, "y": y, "w": w, "h": h,
            "scale": scale, "tint": tint, "specular": specular,
        })
        if not self._timer.isActive():
            self._clock.restart()
            self._timer.start(16)

    @staticmethod
    def _spring(current: float, velocity: float, target: float, dt: float,
                stiffness: float, damping: float):
        # Semi-implicit Euler; stable and independent enough of frame rate for UI.
        acceleration = (target - current) * stiffness
        velocity += acceleration * dt
        velocity *= exp(-damping * dt)
        current += velocity * dt
        return current, velocity

    def _tick(self) -> None:
        dt_ms = min(34, max(1, self._clock.restart()))
        dt = dt_ms / 1000.0

        for key in ("x", "y", "w", "h"):
            current = getattr(self, key)
            current, self._vel[key] = self._spring(
                current, self._vel[key], self._targets[key], dt,
                stiffness=175.0, damping=15.5,
            )
            setattr(self, key, current)

        for key in ("scale", "tint", "specular"):
            current = getattr(self, key)
            current, self._vel[key] = self._spring(
                current, self._vel[key], self._targets[key], dt,
                stiffness=190.0, damping=18.0,
            )
            setattr(self, key, current)

        # A real 35 ms time constant gives perceptible but small visual lag.
        lag_tau = 0.035
        alpha = 1.0 - exp(-dt / lag_tau)
        self.highlight_x += (self.x - self.highlight_x) * alpha
        self.highlight_y += (self.y - self.highlight_y) * alpha

        self.updated.emit()

        settled = all(
            abs(self._targets[k] - getattr(self, k)) < (0.01 if k in ("scale", "tint", "specular") else 0.25)
            and abs(self._vel[k]) < (0.02 if k in ("scale", "tint", "specular") else 0.08)
            for k in self._targets
        )
        highlight_settled = hypot(self.x - self.highlight_x, self.y - self.highlight_y) < 0.2
        if settled and highlight_settled:
            self._timer.stop()
