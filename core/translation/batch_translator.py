import time
import random
from PySide6.QtCore import QObject, QRunnable, Signal
from core.translation.llm_translation_service import LLMTranslationService
from core.database.tm_manager import TranslationMemoryManager
from core.database.glossary_manager import GlossaryManager

class BatchTranslatorSignals(QObject):
    progress = Signal(int, int) # current_chunk, total_chunks
    chunk_completed = Signal(int, list) # chunk_index, translated_segments
    error = Signal(str)
    finished = Signal()

class TranslationBatchWorker(QRunnable):
    def __init__(
        self,
        service: LLMTranslationService,
        tm_manager: TranslationMemoryManager,
        glossary_manager: GlossaryManager,
        segments: list[dict],
        source_lang: str,
        target_lang: str,
        domain: str = "general",
        max_tokens_per_chunk: int = 1500,
        max_retries: int = 3
    ):
        super().__init__()
        self.service = service
        self.tm_manager = tm_manager
        self.glossary_manager = glossary_manager
        self.segments = segments
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.domain = domain
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.max_retries = max_retries
        
        self.signals = BatchTranslatorSignals()
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def _chunk_segments_dynamic(self) -> list[list[dict]]:
        """Cắt lô động dựa trên Token Counter để không làm tràn output LLM."""
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        # We need access to the token counter used by the prompt builder
        token_counter = self.service.prompt_builder._token_counter
        
        for seg in self.segments:
            idx = seg.get("stt", "1")
            start = seg.get("start", "00:00:00,000")
            end = seg.get("end", "00:00:00,000")
            text = seg.get("original_text", seg.get("text", ""))
            
            # Tính token ước lượng cho đoạn SRT
            seg_str = f"{idx}\n{start} --> {end}\n{text}\n\n"
            seg_tokens = token_counter.count(seg_str)
            
            if current_chunk and (current_tokens + seg_tokens > self.max_tokens_per_chunk):
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0
                
            current_chunk.append(seg)
            current_tokens += seg_tokens
            
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def _format_srt_chunk(self, chunk: list[dict]) -> str:
        lines = []
        for seg in chunk:
            idx = seg.get("stt", "1")
            start = seg.get("start", "00:00:00,000")
            end = seg.get("end", "00:00:00,000")
            text = seg.get("original_text", seg.get("text", ""))
            
            lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
        return "\n".join(lines)

    def run(self):
        try:
            # Prepare glossary for the whole domain
            glossary_map = self.glossary_manager.get_term_mappings(self.domain)
            glossary_list = [f"{k} -> {v}" for k, v in glossary_map.items()]
            
            chunks = self._chunk_segments_dynamic()
            total_chunks = len(chunks)
            
            for chunk_idx, chunk in enumerate(chunks):
                if self.is_cancelled:
                    break
                
                # Fetch TM Matches for this chunk
                tm_matches = []
                for seg in chunk:
                    orig = seg.get("original_text", "").strip()
                    if orig and orig != "[Unknown Source]":
                        matches = self.tm_manager.find_matches(orig)
                        # Take the top 1 exact/fuzzy match per sentence to save budget
                        if matches:
                            tm_matches.append(matches[0])
                            
                source_srt = self._format_srt_chunk(chunk)
                
                retries = 0
                success = False
                last_error = ""
                
                while retries <= self.max_retries and not success and not self.is_cancelled:
                    if retries > 0:
                        # Exponential Backoff with Jitter
                        base_delay = 2.0
                        jitter = random.uniform(0.1, 1.0)
                        backoff = (base_delay * (2 ** (retries - 1))) + jitter
                        time.sleep(backoff)
                        
                    result = self.service.translate_batch(
                        source_text=source_srt,
                        source_lang=self.source_lang,
                        target_lang=self.target_lang,
                        glossary=glossary_list,
                        tm_matches=tm_matches
                    )
                    
                    if result.error:
                        if getattr(result, "is_transient_error", False):
                            retries += 1
                            last_error = result.error
                            continue
                        else:
                            self.signals.error.emit(f"Chunk {chunk_idx + 1} Failed: {result.error}")
                            return
                    else:
                        # Alignment Validator
                        translated_segments = self._parse_and_validate(result.translated_text, chunk)
                        if translated_segments is None:
                            # Validation failed! Triggers retry (maybe LLM hallucinated the format)
                            retries += 1
                            last_error = "Alignment Validation Failed: Output segment count does not match input."
                            continue
                            
                        success = True
                        self.signals.chunk_completed.emit(chunk_idx, translated_segments)
                
                if not success and not self.is_cancelled:
                    self.signals.error.emit(f"Max retries exceeded on Chunk {chunk_idx + 1}. Last Error: {last_error}")
                    return
                    
                self.signals.progress.emit(chunk_idx + 1, total_chunks)
                
            self.signals.finished.emit()
            
        except Exception as e:
            self.signals.error.emit(str(e))

    def _parse_and_validate(self, srt_text: str, original_chunk: list[dict]) -> list[dict] | None:
        """Parse the translated SRT and validate against original chunk length."""
        from core.export.subtitle_parser import parse_srt_content
        
        try:
            parsed = parse_srt_content(srt_text)
            
            # Alignment Validator
            if len(parsed) != len(original_chunk):
                return None
                
            # Re-align with original chunk to maintain structure
            for i, o_seg in enumerate(original_chunk):
                # Optionally check if timing matches strictly or not, but typically LLM messes up timing strings lightly
                # We just map by index since numbering was instructed to be maintained.
                o_seg["text"] = parsed[i]["text"]
                
            return original_chunk
        except Exception:
            return None
