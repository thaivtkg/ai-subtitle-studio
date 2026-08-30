from abc import ABC, abstractmethod
from core.ai.ai_request import AIRequest
from core.ai.ai_response import AIResponse

class AIEngine(ABC):
    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """Thực thi request và trả về AIResponse"""
        pass
        
    @abstractmethod
    def load_model(self, model_path: str):
        """Nạp model vào VRAM/RAM trước khi chạy chuỗi Batch"""
        pass
        
    @abstractmethod
    def unload_model(self):
        """Giải phóng bộ nhớ sau khi hoàn tất"""
        pass