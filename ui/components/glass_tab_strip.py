from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRect, QSize, QTimer, QPoint
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QBrush, QIcon
from PySide6.QtWidgets import QTabBar, QStyle, QStyleOptionTab

from ui.core.liquid_materials import MATERIALS, SharedBackdropCache, LiquidMotionController, blend_tint


class GlassTabStrip(QTabBar):
    """Liquid Glass tab strip: one moving active capsule, one shared backdrop."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.ElideNone)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._cache = SharedBackdropCache.get_instance()
        self._cache.changed.connect(self.update)
        self._motion = LiquidMotionController(self)
        self._motion.updated.connect(self.update)
        self.currentChanged.connect(self._sync_active)
        self._hover_index = -1
        self._press_index = -1

        QTimer.singleShot(0, self._prime)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(hint.width() + 8, max(40, hint.height() + 8))

    def _prime(self) -> None:
        if self.count() > 0:
            self._sync_active(self.currentIndex())

    def _active_target_rect(self, index: int) -> QRect:
        base = self.tabRect(index)
        pad_x = 5
        pad_y = 4
        return base.adjusted(-pad_x, -pad_y, pad_x, pad_y)

    def _sync_active(self, index: int) -> None:
        if index < 0 or index >= self.count():
            return
        rect = self._active_target_rect(index)
        self._motion.set_target(
            rect.x(), rect.y(), rect.width(), rect.height(),
            scale=1.015,
            tint=MATERIALS["active"]["tint"],
            specular=MATERIALS["active"]["specular"],
        )

    def tabSizeHint(self, index: int) -> QSize:
        base = super().tabSizeHint(index)
        icon_w = self.tabIcon(index).availableSizes()[0].width() if not self.tabIcon(index).isNull() and self.tabIcon(index).availableSizes() else 0
        return QSize(max(base.width(), icon_w + 36), 34)

    def _capsule_rect(self) -> QRect:
        if self.w <= 0 or self.h <= 0:
            return QRect()
        scale = self._motion.scale
        cx = self._motion.x + self._motion.w * 0.5
        cy = self._motion.y + self._motion.h * 0.5
        w = self._motion.w * scale
        h = self._motion.h * scale
        return QRect(round(cx - w / 2), round(cy - h / 2), round(w), round(h))

    def _rounded_path(self, rect: QRect, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path

    def _draw_active_glass(self, painter: QPainter) -> None:
        rect = self._capsule_rect()
        if rect.isEmpty():
            return

        material = MATERIALS["active"]
        radius = rect.height() * 0.5
        path = self._rounded_path(rect, radius)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipPath(path)

        # 1) Backdrop diffusion + small optical displacement.
        backdrop = self._cache.crop_for(
            self, rect,
            material["refraction_x"],
            material["refraction_y"],
        )
        if not backdrop.isNull():
            painter.setOpacity(0.92)
            painter.drawPixmap(rect, backdrop)

            # Subtle secondary offset pass = faux refraction thickness.
            shifted = self._cache.crop_for(
                self, rect,
                -material["refraction_x"] * 0.45,
                -material["refraction_y"] * 0.45,
            )
            if not shifted.isNull():
                painter.setOpacity(0.10)
                painter.drawPixmap(rect, shifted)

            context = self._cache.sample_color_for(self, rect)
            context = blend_tint(QColor(242, 246, 255), context, self._motion.tint)
            context.setAlpha(round(255 * 0.16))
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.fillPath(path, context)
        else:
            fill = QColor(235, 240, 250, 34)
            painter.fillPath(path, fill)

        painter.restore()

        # 2) Darkened lower edge; no hard black border.
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipPath(path)
        edge_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        edge_grad.setColorAt(0.00, QColor(0, 0, 0, 0))
        edge_grad.setColorAt(0.58, QColor(0, 0, 0, 8))
        edge_grad.setColorAt(1.00, QColor(0, 0, 0, round(255 * material["dark_edge"])))
        painter.fillPath(path, QBrush(edge_grad))
        painter.restore()

        # 3) Thin specular arc: concentrated around the upper third.
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        alpha = round(255 * max(0.0, min(1.0, self._motion.specular)))
        highlight = QPainterPath()
        x1 = rect.left() + rect.width() * 0.12
        x2 = rect.left() + rect.width() * 0.72
        y = rect.top() + rect.height() * 0.05
        highlight.moveTo(x1, y + rect.height() * 0.05)
        highlight.cubicTo(
            x1 + rect.width() * 0.18, rect.top() - rect.height() * 0.02,
            x2 - rect.width() * 0.12, rect.top() + rect.height() * 0.05,
            x2, y + rect.height() * 0.10,
        )
        painter.setPen(QPen(QColor(255, 255, 255, alpha), 1.15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(highlight)

        # Soft top glow just inside the edge.
        glow = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        glow.setColorAt(0.00, QColor(255, 255, 255, min(90, alpha)))
        glow.setColorAt(0.18, QColor(255, 255, 255, min(26, alpha // 3)))
        glow.setColorAt(0.52, QColor(255, 255, 255, 0))
        painter.setClipPath(path)
        painter.fillPath(path, QBrush(glow))
        painter.restore()

        # 4) Fine outer edge, extremely subtle.
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255, 42), 0.8))
        painter.drawPath(path)
        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Tab strip base: deliberately quieter than the active capsule.
        base_path = self._rounded_path(self.rect().adjusted(2, 3, -2, -3), 16)
        painter.fillPath(base_path, QColor(255, 255, 255, 12))
        painter.setPen(QPen(QColor(255, 255, 255, 20), 0.8))
        painter.drawPath(base_path)

        self._draw_active_glass(painter)

        # Text/icon layer is always rendered last.
        for i in range(self.count()):
            rect = self.tabRect(i)
            selected = i == self.currentIndex()
            enabled = self.isTabEnabled(i)
            color = QColor(250, 252, 255, 245 if selected else 185)
            if not enabled:
                color.setAlpha(85)

            icon = self.tabIcon(i)
            text = self.tabText(i)
            content = rect.adjusted(10, 0, -10, 0)

            if not icon.isNull():
                icon_size = QSize(18, 18)
                icon_rect = QRect(content.left(),
                                  content.center().y() - icon_size.height() // 2,
                                  icon_size.width(), icon_size.height())
                mode = QStyle.State_Enabled if enabled else QStyle.State_None
                icon.paint(painter, icon_rect, Qt.AlignCenter,
                           QIcon.Mode.Normal if enabled else QIcon.Mode.Disabled,
                           QIcon.State.On if selected else QIcon.State.Off)
                content.setLeft(icon_rect.right() + 7)

            painter.setPen(color)
            painter.drawText(content, Qt.AlignCenter, text)

        painter.end()

    def mouseMoveEvent(self, event) -> None:
        self._hover_index = self.tabAt(event.position().toPoint())
        super().mouseMoveEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover_index = -1
        super().leaveEvent(event)
        self.update()

    def mousePressEvent(self, event) -> None:
        self._press_index = self.tabAt(event.position().toPoint())
        if self._press_index >= 0:
            self._motion._targets["scale"] = 0.985
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self._press_index = -1
        self._sync_active(self.currentIndex())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, lambda: self._sync_active(self.currentIndex()))
