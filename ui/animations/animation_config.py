from dataclasses import dataclass
from ui.animations.animation_types import (
    SubtitleAppearMode, 
    SubtitleDisappearMode, 
    SubtitleTextEffect
)

@dataclass
class SubtitleAnimationConfig:
    enabled: bool = True
    
    appear_mode: SubtitleAppearMode = SubtitleAppearMode.FADE
    disappear_mode: SubtitleDisappearMode = SubtitleDisappearMode.FADE
    
    fade_in_ms: int = 120
    fade_out_ms: int = 120
    
    text_effect: SubtitleTextEffect = SubtitleTextEffect.NORMAL
    
    reduced_motion: bool = False