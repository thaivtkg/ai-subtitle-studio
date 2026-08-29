from core.timeline.timeline_state import TimelineState


class TimelineVideoSync:
    """[S8-T31 -> T34] Cầu nối đồng bộ Video Player và Timeline an toàn"""
    
    def __init__(self, video_player, timeline_widget, state_manager):
        self.player = video_player
        self.timeline = timeline_widget
        self.state_manager = state_manager
        self._is_syncing = False
        
        # 1. Chiều từ Video Player -> Timeline
        self.player.timeline_position_changed.connect(self.on_player_position_changed)
        # Giả định player của bạn có tín hiệu stateChanged (Play/Pause)
        # self.player.stateChanged.connect(self.on_player_state_changed)
        
        # 2. Chiều từ Timeline -> Video Player
        self.timeline.seek_requested.connect(self.on_timeline_seek_requested)

    def on_player_position_changed(self, position_ms: int):
        """Khi Video chạy, nhích Kim thời gian trên Timeline"""
        
        # Nếu người dùng đang giữ chuột kéo segment hoặc chủ động Seek -> Bỏ qua Video
        if self.state_manager.current in (TimelineState.EDITING_PREVIEW, TimelineState.USER_SEEKING):
            return
            
        self._is_syncing = True
        self.timeline.update_playhead(position_ms)
        self._is_syncing = False

    def on_timeline_seek_requested(self, target_ms: int):
        """Khi click vào Timeline, ép Video tua đến đoạn đó"""
        if self._is_syncing: 
            return # Tránh Feedback Loop
            
        if self.state_manager.can_transition(TimelineState.USER_SEEKING):
            self.state_manager.transition_to(TimelineState.USER_SEEKING)
            try:
                self.player.set_position(target_ms)
            finally:
                self.state_manager.transition_to(TimelineState.IDLE)

    def on_player_state_changed(self, state):
        """Khi người dùng bấm Play trở lại, tự động kích hoạt lại Auto-scroll"""
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlayingState:
            self.timeline.reset_auto_scroll()  
