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
        media_player = getattr(self.player, "player", self.player)
        if hasattr(media_player, "playingChanged"):
            media_player.playingChanged.connect(self._on_player_playing_changed)
        elif hasattr(self.player, "playbackStateChanged"):
            self.player.playbackStateChanged.connect(self.on_player_state_changed)
        
        # 2. Chiều từ Timeline -> Video Player
        self.timeline.seek_requested.connect(self.on_timeline_seek_requested)
        self.timeline.play_segment_requested.connect(self.play_selected_segment)
        self.timeline.workflow_reset.connect(self.cancel_segment_playback)
        self.timeline.timing_edit_started.connect(self.cancel_segment_playback)

    def cancel_segment_playback(self):
        self.player.cancel_segment_playback(pause=True)

    def play_selected_segment(self):
        rng = self._selected_range()
        if rng:
            self.player.play_segment(rng[0], rng[1])

    def _selected_range(self):
        segment = self.timeline.focused_segment
        return (segment.start_ms, segment.end_ms) if segment else None

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

    def _on_player_playing_changed(self, playing: bool):
        """Khi video chuyển sang trạng thái playing == True, bật lại Auto-scroll và kéo màn hình về vị trí kim đỏ nếu nằm ngoài viewport."""
        if playing:
            self.timeline.reset_auto_scroll()
            # Lấy vị trí kim đỏ hiện tại
            pos_ms = 0
            media_player = getattr(self.player, "player", self.player)
            if hasattr(media_player, "position"):
                pos_ms = media_player.position()
            elif hasattr(self.player, "get_position"):
                pos_ms = self.player.get_position()
            elif hasattr(self.timeline, "container") and hasattr(self.timeline.container, "track"):
                pos_ms = getattr(self.timeline.container.track, "current_playhead_ms", 0)

            # Nếu vị trí hiện tại của kim đỏ đang nằm ngoài khung nhìn, center lại
            if hasattr(self.timeline, "pixels_per_second") and hasattr(self.timeline, "viewport"):
                x = int((pos_ms / 1000.0) * self.timeline.pixels_per_second)
                sb = self.timeline.horizontalScrollBar().value()
                vw = self.timeline.viewport().width()
                if x < sb or x > sb + vw:
                    self.timeline.center_on_time(pos_ms)
            elif hasattr(self.timeline, "center_on_time"):
                self.timeline.center_on_time(pos_ms)

    def on_player_state_changed(self, state):
        """Khi người dùng bấm Play trở lại, tự động kích hoạt lại Auto-scroll"""
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlayingState:
            self._on_player_playing_changed(True)  
