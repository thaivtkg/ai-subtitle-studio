from ui.animations.animation_config import SubtitleAnimationConfig
from ui.animations.animation_types import (
    SubtitleAnimationState,
    SubtitleAppearMode,
    SubtitleDisappearMode,
    SubtitleRenderInput,
    SubtitleTextEffect,
)
from ui.animations.subtitle_visual_state import SubtitleVisualState


class SubtitleAnimationController:
    def __init__(self, config: SubtitleAnimationConfig):
        self.config = config
        self.current_state = SubtitleVisualState()
        
    def update_config(self, new_config: SubtitleAnimationConfig):
        self.config = new_config

    def calculate_state(self, current_time_ms: int, render_input: SubtitleRenderInput | None) -> SubtitleVisualState:
        if not self.config.enabled or self.config.reduced_motion or not render_input or not render_input.text.strip():
            self.current_state.reset()
            if render_input:
                self.current_state.segment_id = render_input.segment_id
                self.current_state.animation_state = SubtitleAnimationState.VISIBLE
            return self.current_state

        start_ms = render_input.start_ms
        end_ms = render_input.end_ms
        text_len = len(render_input.text)
        seg_id = render_input.segment_id

        # Xử lý đổi phân đoạn
        if self.current_state.segment_id != seg_id:
            self.current_state.reset()
            self.current_state.segment_id = seg_id

        # Ranh giới thời gian: [start_ms, end_ms)
        if current_time_ms < start_ms or current_time_ms >= end_ms:
            self.current_state.animation_state = SubtitleAnimationState.HIDDEN
            self.current_state.opacity = 0.0
            self.current_state.y_offset = 0.0
            return self.current_state

        elapsed = current_time_ms - start_ms
        remaining = end_ms - current_time_ms
        duration = max(1, end_ms - start_ms)

        fade_in = self.config.fade_in_ms if self.config.appear_mode != SubtitleAppearMode.INSTANT else 0
        fade_out = self.config.fade_out_ms if self.config.disappear_mode != SubtitleDisappearMode.INSTANT else 0

        # State: ENTERING
        if elapsed < fade_in and fade_in > 0:
            self.current_state.animation_state = SubtitleAnimationState.ENTERING
            progress = elapsed / fade_in
            self.current_state.opacity = progress
            self.current_state.y_offset = 6.0 * (1.0 - progress) if self.config.appear_mode == SubtitleAppearMode.RISE else 0.0

        # State: EXITING
        elif remaining < fade_out and fade_out > 0:
            self.current_state.animation_state = SubtitleAnimationState.EXITING
            progress = remaining / fade_out
            self.current_state.opacity = progress
            self.current_state.y_offset = 6.0 * (1.0 - progress) if self.config.disappear_mode == SubtitleDisappearMode.DROP else 0.0

        # State: VISIBLE
        else:
            self.current_state.animation_state = SubtitleAnimationState.VISIBLE
            self.current_state.opacity = 1.0
            self.current_state.y_offset = 0.0

        # Content Effects
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