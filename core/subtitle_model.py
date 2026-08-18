class SubtitleStatus:
    """Định nghĩa các trạng thái của một segment phụ đề"""
    TIMING_ONLY = "timing_only" # Chỉ có khung thời gian, text rỗng
    DRAFT = "draft"             # Nháp (AI vừa điền, chưa duyệt)
    FINAL = "final"             # Người dùng đã chốt

class SubtitleSegment:
    """Mô hình dữ liệu cho một dòng phụ đề độc lập"""
    def __init__(self, segment_id, start_ms, end_ms, text="", status=SubtitleStatus.TIMING_ONLY):
        self.segment_id = segment_id
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text
        self.status = status

    @property
    def is_empty(self):
        """Kiểm tra xem nội dung text có rỗng hay không"""
        return not self.text.strip()

    def update_timestamp(self, start_ms, end_ms):
        """Cập nhật thời gian an toàn"""
        if start_ms >= end_ms:
            raise ValueError("Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc.")
        if start_ms < 0:
            raise ValueError("Thời gian không hợp lệ.")
        self.start_ms = start_ms
        self.end_ms = end_ms

    def update_text(self, text):
        """Cập nhật nội dung chữ. Tự động chuyển status nếu có chữ."""
        self.text = text
        if self.text.strip() and self.status == SubtitleStatus.TIMING_ONLY:
            self.status = SubtitleStatus.DRAFT

    def to_dict(self):
        """Xuất ra Dictionary để lưu file .ai-subtitle-draft sau này"""
        return {
            "id": self.segment_id,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "status": self.status
        }