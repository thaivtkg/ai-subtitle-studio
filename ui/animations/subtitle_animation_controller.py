from ui.animations.animation_types import (
    SubtitleAnimationState, 
    SubtitleTextEffect, 
    SubtitleAppearMode,
    SubtitleDisappearMode
)
from ui.animations.animation_config import SubtitleAnimationConfig
from ui.animations.subtitle_visual_state import SubtitleVisualState

class SubtitleAnimationController:
    def __init__(self, config: SubtitleAnimationConfig):
        self.config = config
        self.current_state = SubtitleVisualState()
        
    def update_config(self, new_config: SubtitleAnimationConfig):
        self.config = new_config

    def calculate_state(self, current_time_ms: int, segment: dict) -> SubtitleVisualState:
        if not self.config.enabled or self.config.reduced_motion or not segment:
            self.current_state.reset()
            if segment:
                self.current_state.segment_id = segment.get('stt')
                self.current_state.animation_state = SubtitleAnimationState.VISIBLE
            return self.current_state

        start_ms = segment.get('start_ms', 0)
        end_ms = segment.get('end_ms', 0)
        text_len = len(segment.get('text', ''))
        seg_id = segment.get('stt')

        # Xử lý Interruption: Nếu nhảy sang segment khác, reset state ngay lập tức
        if self.current_state.segment_id != seg_id:
            self.current_state.reset()
            self.current_state.segment_id = seg_id

        # 1. State: HIDDEN
        if current_time_ms < start_ms or current_time_ms > end_ms:
            self.current_state.animation_state = SubtitleAnimationState.HIDDEN
            self.current_state.opacity = 0.0
            self.current_state.y_offset = 0.0
            return self.current_state

        elapsed = current_time_ms - start_ms
        remaining = end_ms - current_time_ms
        duration = max(1, end_ms - start_ms)

        fade_in = self.config.fade_in_ms if self.config.appear_mode != SubtitleAppearMode.INSTANT else 0
        fade_out = self.config.fade_out_ms if self.config.disappear_mode != SubtitleDisappearMode.INSTANT else 0

        # 2. State: ENTERING (Fade / Rise)
        if elapsed < fade_in and fade_in > 0:
            self.current_state.animation_state = SubtitleAnimationState.ENTERING
            progress = elapsed / fade_in
            self.current_state.opacity = progress
            if self.config.appear_mode == SubtitleAppearMode.RISE:
                self.current_state.y_offset = 6.0 * (1.0 - progress) # +6px -> 0px
            else:
                self.current_state.y_offset = 0.0

        # 3. State: EXITING (Fade / Drop)
        elif remaining < fade_out and fade_out > 0:
            self.current_state.animation_state = SubtitleAnimationState.EXITING
            progress = remaining / fade_out
            self.current_state.opacity = progress
            if self.config.disappear_mode == SubtitleDisappearMode.DROP:
                self.current_state.y_offset = 6.0 * (1.0 - progress) # 0px -> +6px
            else:
                self.current_state.y_offset = 0.0

        # 4. State: VISIBLE
        else:
            self.current_state.animation_state = SubtitleAnimationState.VISIBLE
            self.current_state.opacity = 1.0
            self.current_state.y_offset = 0.0

        # Xử lý Content Effects (Reveal & Highlight) trong vùng Content Interval an toàn
        content_duration = max(1, duration - fade_in - fade_out)
        content_elapsed = max(0, elapsed - fade_in)
        content_progress = min(1.0, content_elapsed / content_duration)

        if self.config.text_effect == SubtitleTextEffect.REVEAL or self.config.appear_mode == SubtitleAppearMode.REVEAL:
            self.current_state.visible_chars = int(text_len * content_progress)
        else:
            self.current_state.visible_chars = -1

        if self.config.text_effect == SubtitleTextEffect.HIGHLIGHT:
            self.current_state.highlight_chars = int(text_len * content_progress)
        else:
            self.current_state.highlight_chars = 0

        return self.current_state   