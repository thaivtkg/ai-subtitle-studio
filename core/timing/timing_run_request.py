from dataclasses import dataclass


@dataclass
class TimingRunRequest:
    """Gói dữ liệu cấu hình để ném cho TimingBatchWorker thực thi"""
    video_path: str
    start_ms: int
    target_segment_count: int
    
    # Cấu hình an toàn cho Whisper Chunking
    overlap_ms: int = 800  # Lùi lại 800ms để bắt câu nói bị cắt ngang
    max_window_ms: int = 120000  # Tối đa 2 phút mỗi lần quét để tránh treo vô hạn nếu video im lặng
    
    # AI Config
    model_size: str = "base"
    compute_type: str = "float16"
    use_vad: bool = True
    min_silence_ms: int = 500