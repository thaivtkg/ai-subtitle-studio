from typing import List, Dict, Tuple
from core.generation.context_policy import ContextPolicy

class SubtitleContextEngine:
    @staticmethod
    def build_context(all_segments: List[Dict], start_stt: int, end_stt: int, policy: ContextPolicy) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        total_segs = len(all_segments)
        
        # CHUẨN HÓA: 1-based (STT) sang 0-based (Index Mảng)
        start_idx = max(0, start_stt - 1)
        end_idx = min(total_segs - 1, end_stt - 1)
        
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        target_segments = all_segments[start_idx : end_idx + 1]

        prev_start = max(0, start_idx - policy.before)
        previous_segments = all_segments[prev_start : start_idx] if start_idx > 0 else []

        next_end = min(total_segs, end_idx + 1 + policy.after)
        next_segments = all_segments[end_idx + 1 : next_end] if end_idx + 1 < total_segs else []

        # BLOCKER FIXED: Cầu chì bảo vệ tràn Token/VRAM (max_chars)
        def get_chars(segs): return sum(len(str(s.get('text', ''))) for s in segs)
        
        while previous_segments or next_segments:
            total_chars = get_chars(previous_segments) + get_chars(target_segments) + get_chars(next_segments)
            if total_chars <= policy.max_chars:
                break
                
            # Cắt bỏ context xa nhất (Ưu tiên cắt phần tương lai trước, quá khứ sau)
            if next_segments:
                next_segments.pop() 
            elif previous_segments:
                previous_segments.pop(0) 
                
        return previous_segments, target_segments, next_segments