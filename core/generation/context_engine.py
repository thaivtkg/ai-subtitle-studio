from typing import List, Dict, Tuple
from core.generation.context_policy import ContextPolicy

class SubtitleContextEngine:
    @staticmethod
    def build_context(all_segments: List[Dict], start_idx: int, end_idx: int, policy: ContextPolicy) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Xây dựng cửa sổ ngữ cảnh (Context Window) động cho một Batch.
        Trả về 3 tập hợp: (Ngữ cảnh trước, Khối mục tiêu, Ngữ cảnh sau).
        """
        total_segs = len(all_segments)
        
        # 1. Ràng buộc an toàn chỉ số mảng
        start_idx = max(0, min(start_idx, total_segs - 1))
        end_idx = max(0, min(end_idx, total_segs - 1))
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        # 2. Bóc tách Target (Tuyệt đối không Overlap giữa các Batch)
        target_segments = all_segments[start_idx : end_idx + 1]

        # 3. Trích xuất Context (Được phép Overlap)
        prev_start = max(0, start_idx - policy.before)
        previous_segments = all_segments[prev_start : start_idx] if start_idx > 0 else []

        next_end = min(total_segs, end_idx + 1 + policy.after)
        next_segments = all_segments[end_idx + 1 : next_end] if end_idx + 1 < total_segs else []

        # (Tương lai: Áp dụng cắt bớt context nếu vượt quá policy.max_chars)
        
        return previous_segments, target_segments, next_segments