import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.generation.context_policy import ContextPolicy
from core.generation.context_engine import SubtitleContextEngine
from core.generation.generation_request import GenerationRequest
from core.generation.generation_planner import GenerationPlanner
from core.generation.generation_validator import GenerationValidator
from core.generation.generation_candidate import GenerationCandidate

class TestGenerationCore(unittest.TestCase):
    def setUp(self):
        # Tạo dữ liệu giả lập 10 câu phụ đề
        self.segments = [{"id": f"seg_{i}", "text": f"Câu số {i}"} for i in range(1, 11)]

    # ==========================================
    # 1. TEST CONTEXT ENGINE (Lệch Index & Max Chars)
    # ==========================================
    def test_01_context_engine_indexing_and_limits(self):
        policy = ContextPolicy(before=2, after=2, max_chars=1000)
        
        # Yêu cầu dịch từ câu 4 đến câu 6 (STT 1-based)
        prev_s, target_s, next_s = SubtitleContextEngine.build_context(self.segments, 4, 6, policy)
        
        # Target phải là mảng index 3, 4, 5 (Tức câu 4, 5, 6)
        self.assertEqual(len(target_s), 3)
        self.assertEqual(target_s[0]['id'], "seg_4")
        self.assertEqual(target_s[-1]['id'], "seg_6")
        
        # Context trước phải là câu 2, 3
        self.assertEqual(len(prev_s), 2)
        self.assertEqual(prev_s[0]['id'], "seg_2")
        
        # Context sau phải là câu 7, 8
        self.assertEqual(len(next_s), 2)
        self.assertEqual(next_s[0]['id'], "seg_7")

    def test_02_context_engine_max_chars_cutoff(self):
        # Ép max_chars cực nhỏ để test cầu chì tự động chặt đuôi
        policy_strict = ContextPolicy(before=3, after=3, max_chars=40) 
        prev_s, target_s, next_s = SubtitleContextEngine.build_context(self.segments, 5, 5, policy_strict)
        
        # Khối Target (Câu 5) dài ~10 ký tự. Ngữ cảnh xung quanh sẽ bị cắt bớt để không lố 40 ký tự
        total_chars = sum(len(s['text']) for s in prev_s + target_s + next_s)
        self.assertTrue(total_chars <= 40, "LỖI: Context Engine không tôn trọng max_chars!")

    # ==========================================
    # 2. TEST PLANNER (Phân mảnh Batch)
    # ==========================================
    def test_03_generation_planner_batching(self):
        req = GenerationRequest(
            request_id="req_1", project_id="p1", source_fingerprint="f1", timing_artifact_id="t1",
            start_segment=21, end_segment=45, mode="fill_text", source_language="vi", target_language="vi",
            context_before=3, context_after=3, model_id="qwen", temperature=0.2, max_tokens=1000
        )
        
        # Batch size 10 cho 25 câu -> Phải đẻ ra 3 Batch
        batches = GenerationPlanner.create_plan(req, batch_size=10)
        self.assertEqual(len(batches), 3)
        
        self.assertEqual(batches[0].start_index, 21)
        self.assertEqual(batches[0].end_index, 30)
        
        self.assertEqual(batches[1].start_index, 31)
        self.assertEqual(batches[1].end_index, 40)
        
        self.assertEqual(batches[2].start_index, 41)
        self.assertEqual(batches[2].end_index, 45) # Batch cuối chỉ có 5 câu

    # ==========================================
    # 3. TEST VALIDATOR (Bộ lọc Rác AI)
    # ==========================================
    def test_04_validator_rejects_extra_and_missing_ids(self):
        target_segs = [{"id": "seg_1", "text": ""}, {"id": "seg_2", "text": ""}]
        
        # AI chế thêm ID 'seg_3' và thiếu mất 'seg_2'
        invalid_json = {
            "segments": [
                {"id": "seg_1", "text": "Dịch chuẩn"},
                {"id": "seg_3", "text": "Câu AI tự chế"}
            ]
        }
        
        with self.assertRaises(ValueError) as context:
            GenerationValidator.validate(invalid_json, target_segs, "req_1", "model_1")
        self.assertTrue("EXTRA" in str(context.exception) or "TRẢ SAI SỐ LƯỢNG" in str(context.exception))

    def test_05_validator_rejects_empty_text(self):
        target_segs = [{"id": "seg_1", "text": ""}]
        empty_text_json = {"segments": [{"id": "seg_1", "text": "   "}]}
        
        with self.assertRaises(ValueError) as context:
            GenerationValidator.validate(empty_text_json, target_segs, "req_1", "model_1")
        self.assertTrue("CHUỖI RỖNG" in str(context.exception))

if __name__ == '__main__':
    unittest.main(verbosity=2)