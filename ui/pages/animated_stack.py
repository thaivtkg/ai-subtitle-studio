from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedLayout, QWidget


class AnimatedStack(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QStackedLayout(self)
        self.layout.setStackingMode(QStackedLayout.StackAll)
        
        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.finished.connect(self._on_transition_finished)
        
        self.current_index = -1
        self.target_index = -1
        self.widgets: list[QWidget] = []

    def addWidget(self, widget: QWidget) -> int:
        self.layout.addWidget(widget)
        self.widgets.append(widget)
        
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        widget.hide()
        
        if self.current_index == -1:
            self.current_index = 0
            self.target_index = 0
            widget.show()
            effect.setOpacity(1.0)
            
        return len(self.widgets) - 1

    def setCurrentIndex(self, index: int, duration: int = 180):
        if index < 0 or index >= len(self.widgets) or index == self.current_index:
            return

        # Interruption-safe: Nếu đang chạy animation, dừng ngay và reset toàn bộ state phụ
        if self.anim_group.state() == QParallelAnimationGroup.Running:
            self.anim_group.stop()
            for i, w in enumerate(self.widgets):
                if i != self.current_index and i != index:
                    w.hide()
                    if w.graphicsEffect():
                        w.graphicsEffect().setOpacity(0.0)

        current_w = self.widgets[self.current_index]
        target_w = self.widgets[index]
        self.target_index = index
        
        target_w.show()
        target_w.raise_()

        self.anim_group.clear()

        c_effect = current_w.graphicsEffect()
        t_effect = target_w.graphicsEffect()

        anim_out = QPropertyAnimation(c_effect, b"opacity")
        anim_out.setDuration(duration)
        anim_out.setStartValue(c_effect.opacity())
        anim_out.setEndValue(0.0)
        anim_out.setEasingCurve(QEasingCurve.OutCubic)

        anim_in = QPropertyAnimation(t_effect, b"opacity")
        anim_in.setDuration(duration)
        anim_in.setStartValue(t_effect.opacity())
        anim_in.setEndValue(1.0)
        anim_in.setEasingCurve(QEasingCurve.OutCubic)

        self.anim_group.addAnimation(anim_out)
        self.anim_group.addAnimation(anim_in)
        self.anim_group.start()

    def _on_transition_finished(self):
        # Đồng bộ trạng thái cuối cùng
        for i, w in enumerate(self.widgets):
            if i == self.target_index:
                w.show()
                if w.graphicsEffect():
                    w.graphicsEffect().setOpacity(1.0)
            else:
                w.hide()
                if w.graphicsEffect():
                    w.graphicsEffect().setOpacity(0.0)
        self.current_index = self.target_index

    def currentWidget(self) -> QWidget | None:
        if 0 <= self.current_index < len(self.widgets):
            return self.widgets[self.current_index]
        return None