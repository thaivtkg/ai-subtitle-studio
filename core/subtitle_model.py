class SubtitleStatus:
    """ Trạng thái vòng đời của một Segment trong Pipeline """
    TIMING_ONLY = "timing_only" # Artifact cấp 1: Chỉ có thời gian
    DRAFT = "draft"             # Artifact cấp 2: Đã điền Text (Transcript/Translation) nhưng chưa chốt
    FINAL = "final"             # Artifact cấp cuối: Người dùng đã Approve

class SegmentType:
    """ Phân loại Segment để hỗ trợ Overlap/WhisperX sau này (v0.3) """
    NORMAL = "normal"
    OVERLAP = "overlap"
    WHISPER = "whisper"
    THOUGHT = "thought"

class SubtitleSegment:
    """ 
    Thực thể cốt lõi mang dữ liệu qua các Artifact Pipeline.
    Không ràng buộc tuyến tính (Cho phép Overlap).
    """
    def __init__(self, segment_id, start_ms, end_ms, text="", status=SubtitleStatus.TIMING_ONLY, metadata=None):
        self.segment_id = segment_id
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text
        self.status = status
        
        # Mở rộng cho v0.3: Lưu trữ Source, Speaker ID, Confidence Score, v.v.
        self.metadata = metadata if metadata is not None else {
            "type": SegmentType.NORMAL,
            "speaker": None,
            "confidence": 1.0
        }

    @property
    def is_empty(self):
        """ Kiểm tra xem nội dung Artifact đã có Text hay chưa """
        return not self.text.strip()

    def update_timestamp(self, start_ms, end_ms):
        """ 
        Cập nhật thời gian cho Segment.
        Chỉ kiểm tra tính hợp lệ của chính nó. KHÔNG kiểm tra Overlap với Segment khác.
        """
        if start_ms >= end_ms:
            raise ValueError(f"Thời gian bắt đầu ({start_ms}) phải nhỏ hơn thời gian kết thúc ({end_ms}).")
        if start_ms < 0:
            raise ValueError("Thời gian không được âm.")
        self.start_ms = start_ms
        self.end_ms = end_ms

    def update_text(self, text):
        """ Bước chuyển đổi từ Timing Artifact -> Transcript Artifact """
        self.text = text
        if self.text.strip() and self.status == SubtitleStatus.TIMING_ONLY:
            self.status = SubtitleStatus.DRAFT

    def to_dict(self):
        """ Xuất dữ liệu chuẩn bị cho .ai-subtitle-draft (Persistence - Sprint 7) """
        return {
            "id": self.segment_id,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "status": self.status,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data):
        """ Phục hồi Object từ dữ liệu thô """
        return cls(
            segment_id=data.get("id"),
            start_ms=data.get("start_ms", 0),
            end_ms=data.get("end_ms", 0),
            text=data.get("text", ""),
            status=data.get("status", SubtitleStatus.TIMING_ONLY),
            metadata=data.get("metadata")
        )