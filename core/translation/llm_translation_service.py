import json
import urllib.request
import urllib.error
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

class TranslationProviderProtocol(Protocol):
    def translate(self, prompt: str) -> str:
        ...

class GeminiRESTProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        
    def translate(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("API Key is required for Gemini Provider")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,  # Low temperature for deterministic translation
                "topK": 32,
                "topP": 1,
            }
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "candidates" in result and result["candidates"]:
                    # Return the translated text
                    return result["candidates"][0]["content"]["parts"][0]["text"].strip()
                raise ValueError("Unexpected API response format.")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise RuntimeError(f"Gemini API Error: {e.code} - {error_body}")
        except Exception as e:
            raise RuntimeError(f"Translation failed: {str(e)}")


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
            # 1. Build the dynamic context prompt
            context = self.prompt_builder.build(
                source_text=source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary=glossary,
                tm_matches=tm_matches
            )
            
            # 2. Call the provider
            translated_text = self.provider.translate(context.prompt_text)
            
            return TranslationResult(
                translated_text=translated_text,
                prompt_context=context,
            )
        except Exception as e:
            return TranslationResult(
                translated_text="",
                prompt_context=None,
                error=str(e)
            )
