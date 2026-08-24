from dataclasses import dataclass
from ui.animations.animation_types import SubtitleAnimationState

@dataclass
class SubtitleVisualState:
    segment_id: str | int | None = None
    
    # Render Properties
    opacity: float = 1.0
    y_offset: float = 0.0      # Độ lệch trục Y (Rise: +6 -> 0, Drop: 0 -> +6)
    visible_chars: int = -1    # -1: Hiển thị toàn bộ chuỗi
    highlight_chars: int = 0   # Số ký tự được đánh dấu màu highlight
    
    # Lifecycle Tracking
    animation_state: SubtitleAnimationState = SubtitleAnimationState.HIDDEN
    
    def reset(self):
        """Khôi phục trạng thái về mặc định khi segment đổi hoặc kết thúc"""
        self.segment_id = None
        self.opacity = 1.0
        self.y_offset = 0.0
        self.visible_chars = -1
        self.highlight_chars = 0
        self.animation_state = SubtitleAnimationState.HIDDEN