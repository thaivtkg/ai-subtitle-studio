import json
import urllib.request
import urllib.error
import socket
from typing import Protocol, List
from dataclasses import dataclass
from core.database.tm_manager import TMMatch
from core.translation.agentic_prompt_builder import AgenticPromptBuilder, AgenticPromptContext

@dataclass
class TranslationResult:
    translated_text: str
    prompt_context: AgenticPromptContext
    usage_tokens: int = 0
    error: str = None
    is_transient_error: bool = False

class TranslationProviderProtocol(Protocol):
    def translate(self, prompt: str) -> str:
        ...

class GeminiRESTProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", temperature: float = 0.1, top_k: int = 32, top_p: float = 1.0, timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.timeout = timeout
        
    def translate(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("API Key is required for Gemini Provider")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": self.temperature,
                "topK": self.top_k,
                "topP": self.top_p,
            }
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "candidates" in result and result["candidates"]:
                    return result["candidates"][0]["content"]["parts"][0]["text"].strip()
                raise ValueError("Unexpected API response format.")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            # 429 Too Many Requests, 500 Internal Server Error, 503 Service Unavailable are transient
            is_transient = e.code in (429, 500, 503)
            raise RuntimeError(f"Gemini API Error {e.code}: {error_body}") from e
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            # Network-level transient errors
            raise RuntimeError(f"Network error during API call: {str(e)}") from e
        except Exception as e:
            # Catch-all for JSON parsing errors or logic errors
            raise RuntimeError(f"Translation failed: {str(e)}") from e


class LLMTranslationService:
    def __init__(self, provider: TranslationProviderProtocol, prompt_builder: AgenticPromptBuilder):
        self.provider = provider
        self.prompt_builder = prompt_builder

    def translate_batch(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary: List[str] = None,
        tm_matches: List[TMMatch] = None,
    ) -> TranslationResult:
        """
        Translates a batch of subtitles using Agentic Prompting.
        """
        try:
            context = self.prompt_builder.build(
                source_text=source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary=glossary,
                tm_matches=tm_matches
            )
            
            translated_text = self.provider.translate(context.prompt_text)
            
            return TranslationResult(
                translated_text=translated_text,
                prompt_context=context,
            )
        except RuntimeError as e:
            err_msg = str(e).lower()
            is_transient = "network error" in err_msg or "error 429" in err_msg or "error 500" in err_msg or "error 503" in err_msg
            return TranslationResult(
                translated_text="",
                prompt_context=None,
                error=str(e),
                is_transient_error=is_transient
            )
        except Exception as e:
            return TranslationResult(
                translated_text="",
                prompt_context=None,
                error=f"Critical error: {str(e)}",
                is_transient_error=False
            )
