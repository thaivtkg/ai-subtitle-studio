from core.ai.ai_engine import AIEngine
from core.ai.ai_request import AIRequest
from core.ai.ai_response import AIResponse
from core.ai.output_parser import OutputParser

class LocalLLMAdapter(AIEngine):
    def __init__(self):
        self.llm = None
        
    def load_model(self, model_path: str):
        if self.llm: return
        try:
            from llama_cpp import Llama
            # Nạp model với Context Window mặc định, khai thác tối đa GPU
            self.llm = Llama(model_path=model_path, n_ctx=4096, n_gpu_layers=-1, verbose=False)
        except ImportError:
            raise ImportError("BLOCKER: Cần cài đặt thư viện 'llama-cpp-python'")
        except Exception as e:
            raise RuntimeError(f"Lỗi nạp Model GGUF: {str(e)}")
            
    def unload_model(self):
        if self.llm:
            del self.llm
            self.llm = None
            
    def generate(self, request: AIRequest) -> AIResponse:
        if not self.llm:
            return AIResponse(request_id=request.request_id, raw_text="", error="Model chưa được nạp.")
            
        try:
            response = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": request.system_instruction},
                    {"role": "user", "content": request.prompt}
                ],
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            raw_text = response['choices'][0]['message']['content']
            parsed_data = OutputParser.extract_json(raw_text)
            
            return AIResponse(
                request_id=request.request_id,
                raw_text=raw_text,
                parsed_json=parsed_data,
                error=None if parsed_data else "Failed to parse JSON"
            )
        except Exception as e:
             return AIResponse(request_id=request.request_id, raw_text="", error=str(e))