from PySide6.QtWidgets import QWidget, QStackedLayout, QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, Qt
from PySide6.QtGui import QAction

class AnimatedStack(QWidget):
    """
    Component thay thế QStackedWidget, cho phép CrossFade mượt mà giữa các page
    bằng cách render trực tiếp Widget thật (Live Widget Motion).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # [QUAN TRỌNG] StackAll cho phép các widget xếp chồng lên nhau và cùng hiển thị
        self.layout = QStackedLayout(self)
        self.layout.setStackingMode(QStackedLayout.StackAll)
        
        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.finished.connect(self._on_transition_finished)
        
        self.current_index = -1
        self.widgets = []
        self._is_transitioning = False

    def addWidget(self, widget: QWidget):
        # Mặc định ẩn tất cả các widget được thêm vào, trừ widget đầu tiên
        self.layout.addWidget(widget)
        self.widgets.append(widget)
        
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        widget.hide()
        
        if self.current_index == -1:
            self.current_index = 0
            widget.show()
            effect.setOpacity(1.0)
            
        return len(self.widgets) - 1

    def setCurrentIndex(self, index: int, duration: int = 180):
        if index == self.current_index or index < 0 or index >= len(self.widgets):
            return

        # 1. Xử lý Interruption: Hủy ngay transition đang chạy
        if self.anim_group.state() == QParallelAnimationGroup.Running:
            self.anim_group.stop()
            self._force_finish_transition()

        self._is_transitioning = True
        
        current_widget = self.widgets[self.current_index]
        target_widget = self.widgets[index]
        
        # Đảm bảo target widget hiển thị và nằm trên cùng
        target_widget.show()
        target_widget.raise_()

        self.anim_group.clear()

        # 2. Fade Out cho Widget hiện tại
        current_effect = current_widget.graphicsEffect()
        anim_out = QPropertyAnimation(current_effect, b"opacity")
        anim_out.setDuration(duration)
        anim_out.setStartValue(current_effect.opacity())
        anim_out.setEndValue(0.0)
        anim_out.setEasingCurve(QEasingCurve.OutCubic)
        self.anim_group.addAnimation(anim_out)

        # 3. Fade In cho Widget mục tiêu
        target_effect = target_widget.graphicsEffect()
        anim_in = QPropertyAnimation(target_effect, b"opacity")
        anim_in.setDuration(duration)
        anim_in.setStartValue(target_effect.opacity())
        anim_in.setEndValue(1.0)
        anim_in.setEasingCurve(QEasingCurve.OutCubic)
        self.anim_group.addAnimation(anim_in)

        # 4. Cập nhật con trỏ và kích hoạt
        self.target_index_cache = index
        self.anim_group.start()

    def _on_transition_finished(self):
        self._force_finish_transition()

    def _force_finish_transition(self):
        if not self._is_transitioning:
            return
            
        # Ẩn hoàn toàn widget cũ để giải phóng tài nguyên render
        old_widget = self.widgets[self.current_index]
        old_widget.hide()
        
        # Khóa trạng thái mục tiêu
        self.current_index = self.target_index_cache
        target_widget = self.widgets[self.current_index]
        target_widget.graphicsEffect().setOpacity(1.0)
        
        self._is_transitioning = False

    def currentWidget(self):
        if self.current_index >= 0 and self.current_index < len(self.widgets):
            return self.widgets[self.current_index]
        return None