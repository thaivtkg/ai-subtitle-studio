import time
import random
from PySide6.QtCore import QObject, QRunnable, Signal
from core.translation.llm_translation_service import LLMTranslationService
from core.database.tm_manager import TranslationMemoryManager
from core.database.glossary_manager import GlossaryManager
from core.subtitle_quality.auto_qc_service import AutoQCService

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
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        token_counter = self.service.prompt_builder._token_counter
        
        for seg in self.segments:
            idx = seg.get("stt", "1")
            start = seg.get("start", "00:00:00,000")
            end = seg.get("end", "00:00:00,000")
            text = seg.get("original_text", seg.get("text", ""))
            
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

    def _extract_previous_context(self, previous_chunk: list[dict]) -> str:
        if not previous_chunk:
            return ""
        # Take the last 3 segments to provide context
        context_segs = previous_chunk[-3:]
        lines = []
        for seg in context_segs:
            text = seg.get("original_text", seg.get("text", ""))
            lines.append(text)
        return " ".join(lines)

    def run(self):
        try:
            glossary_map = self.glossary_manager.get_term_mappings(self.domain)
            glossary_list = [f"{k} -> {v}" for k, v in glossary_map.items()]
            
            chunks = self._chunk_segments_dynamic()
            total_chunks = len(chunks)
            previous_context = ""
            
            for chunk_idx, chunk in enumerate(chunks):
                if self.is_cancelled:
                    break
                
                tm_matches = []
                for seg in chunk:
                    orig = seg.get("original_text", "").strip()
                    if orig and orig != "[Unknown Source]":
                        matches = self.tm_manager.find_matches(orig)
                        if matches:
                            tm_matches.append(matches[0])
                            
                source_srt = self._format_srt_chunk(chunk)
                
                retries = 0
                success = False
                last_error = ""
                translated_segments = None
                
                while retries <= self.max_retries and not success and not self.is_cancelled:
                    if retries > 0:
                        base_delay = 2.0
                        jitter = random.uniform(0.1, 1.0)
                        backoff = (base_delay * (2 ** (retries - 1))) + jitter
                        import time
                        time.sleep(backoff)
                        
                    try:
                        result = self.service.translate_batch(
                            source_text=source_srt,
                            source_lang=self.source_lang,
                            target_lang=self.target_lang,
                            glossary=glossary_list,
                            tm_matches=tm_matches,
                            previous_context=previous_context
                        )
                    except Exception as loop_e:
                        err_str = str(loop_e).lower()
                        if "network" in err_str or "transient" in err_str or "timeout" in err_str or "connection" in err_str:
                            retries += 1
                            last_error = str(loop_e)
                            continue
                        else:
                            self.signals.error.emit(f"Chunk {chunk_idx + 1} Failed: {loop_e}")
                            return
                    
                    if result.error:
                        if getattr(result, "is_transient_error", False):
                            retries += 1
                            last_error = result.error
                            continue
                        else:
                            self.signals.error.emit(f"Chunk {chunk_idx + 1} Failed: {result.error}")
                            return
                    else:
                        parsed_segs = self._parse_and_validate(result.translated_text, chunk)
                        if parsed_segs is None:
                            retries += 1
                            last_error = "Alignment Validation Failed: Output segment count does not match input."
                            continue
                            
                        translated_segments = parsed_segs
                        success = True
                
                # Handle Fallback if max retries exceeded
                if not success and not self.is_cancelled:
                    if "Alignment Validation Failed" in last_error:
                        # Fallback: Copy original text and inject metadata
                        translated_segments = []
                        for seg in chunk:
                            fallback_seg = seg.copy()
                            fallback_seg["text"] = fallback_seg.get("original_text", fallback_seg.get("text", ""))
                            fallback_seg["metadata"] = {"qc_flags": ["alignment_failed_fallback"]}
                            translated_segments.append(fallback_seg)
                    else:
                        self.signals.error.emit(f"Max retries exceeded on Chunk {chunk_idx + 1}. Last Error: {last_error}")
                        return
                
                # Apply AutoQC to the translated segments
                for seg in translated_segments:
                    src_text = seg.get("original_text", seg.get("text", ""))
                    tgt_text = seg.get("text", "")
                    
                    qc_flags = AutoQCService.evaluate_segment(src_text, tgt_text, glossary_map)
                    
                    if qc_flags:
                        metadata = seg.get("metadata", {})
                        existing_flags = metadata.get("qc_flags", [])
                        existing_flags.extend(qc_flags)
                        metadata["qc_flags"] = existing_flags
                        seg["metadata"] = metadata
                
                # Emit completion for this chunk
                self.signals.chunk_completed.emit(chunk_idx, translated_segments)
                self.signals.progress.emit(chunk_idx + 1, total_chunks)
                
                # Prepare context for next chunk
                previous_context = self._extract_previous_context(chunk)
                
            self.signals.finished.emit()
            
        except Exception as e:
            self.signals.error.emit(str(e))

    def _parse_and_validate(self, srt_text: str, original_chunk: list[dict]) -> list[dict] | None:
        from core.export.subtitle_parser import parse_srt_content
        
        try:
            parsed = parse_srt_content(srt_text)
            
            if len(parsed) != len(original_chunk):
                return None
                
            result_chunk = []
            for i, o_seg in enumerate(original_chunk):
                new_seg = o_seg.copy()
                new_seg["text"] = parsed[i]["text"]
                result_chunk.append(new_seg)
                
            return result_chunk
        except Exception:
            return None
