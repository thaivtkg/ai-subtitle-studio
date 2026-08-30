from enum import Enum
import threading

class TimelineState(Enum):
    IDLE = 1
    PLAYBACK_SYNC = 2    # Đang nhận tín hiệu cập nhật từ Video Player
    USER_SEEKING = 3     # User đang kéo Playhead (chặn cập nhật từ Video)
    EDITING_PREVIEW = 4  # User đang kéo giãn/di chuyển Segment (Ghost preview)
    COMMITTING = 5       # Đang ghi dữ liệu vào ArtifactStore (Khóa toàn bộ UI)

class TimelineStateManager:
    """Quản lý trạng thái FSM, chặn race conditions trong môi trường đa luồng/sự kiện"""
    
    def __init__(self):
        self._current_state = TimelineState.IDLE
        self._lock = threading.Lock()
        
        # Ma trận chuyển đổi hợp lệ (Từ -> Danh sách Đích)
        self._valid_transitions = {
            TimelineState.IDLE: [TimelineState.PLAYBACK_SYNC, TimelineState.USER_SEEKING, TimelineState.EDITING_PREVIEW, TimelineState.COMMITTING],
            TimelineState.PLAYBACK_SYNC: [TimelineState.IDLE, TimelineState.USER_SEEKING],
            TimelineState.USER_SEEKING: [TimelineState.IDLE],
            TimelineState.EDITING_PREVIEW: [TimelineState.IDLE, TimelineState.COMMITTING],
            TimelineState.COMMITTING: [TimelineState.IDLE]
        }

    @property
    def current(self) -> TimelineState:
        with self._lock:
            return self._current_state

    def can_transition(self, target_state: TimelineState) -> bool:
        with self._lock:
            return target_state in self._valid_transitions[self._current_state]

    def transition_to(self, target_state: TimelineState) -> bool:
        """Thực hiện chuyển đổi trạng thái nếu hợp lệ, ném ngoại lệ nếu vi phạm Hợp đồng"""
        with self._lock:
            if target_state not in self._valid_transitions[self._current_state]:
                raise RuntimeError(f"[FSM Error] Chuyển trạng thái phi logic: {self._current_state.name} -> {target_state.name}")
            
            self._current_state = target_state
            return True
            
    def is_interaction_locked(self) -> bool:
        """Khóa tương tác UI nếu đang ghi dữ liệu hoặc đang phát Video"""
        with self._lock:
            return self._current_state in (TimelineState.COMMITTING, TimelineState.PLAYBACK_SYNC)