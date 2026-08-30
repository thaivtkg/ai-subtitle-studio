from dataclasses import dataclass

@dataclass
class ContextPolicy:
    before: int = 3       # Số câu ngữ cảnh trước
    after: int = 3        # Số câu ngữ cảnh sau
    max_chars: int = 6000 # Cầu chì bảo vệ: Giới hạn tối đa số ký tự đẩy vào LLM