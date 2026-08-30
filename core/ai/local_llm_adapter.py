from core.ai.ai_engine import AIEngine
from core.ai.ai_request import AIRequest
from core.ai.ai_response import AIResponse
from core.ai.output_parser import OutputParser

class LocalLLMAdapter(AIEngine):
    def __init__(self):
        self._model_loaded = False
        
    def load_model(self, model_path: str):
        # TODO: Tích hợp thư viện llama_cpp_python tại đây
        self._model_loaded = True
        
    def unload_model(self):
        self._model_loaded = False
        
    def generate(self, request: AIRequest) -> AIResponse:
        if not self._model_loaded:
            return AIResponse(request_id=request.request_id, raw_text="", error="Model not loaded")
            
        # TODO: Gọi inference thật tại đây. Dưới đây là Mock response để test logic
        mock_raw_output = """
        ```json
        {
          "segments": [
            {
              "id": "mock_id",
              "text": "Đây là kết quả dịch giả lập."
            }
          ]
        }
        ```
        """
        
        parsed_data = OutputParser.extract_json(mock_raw_output)
        
        return AIResponse(
            request_id=request.request_id,
            raw_text=mock_raw_output,
            parsed_json=parsed_data,
            error=None if parsed_data else "Failed to parse JSON"
        )