import unittest
import sys
import os
import tempfile
import shutil
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.generation.generation_request import GenerationRequest
from core.generation.generation_batch import GenerationBatch
from core.generation.generation_candidate import GenerationCandidate
from core.generation.generation_checkpoint import GenerationCheckpoint
from core.generation.generation_checkpoint_manager import GenerationCheckpointManager
from core.generation.generation_service import GenerationService
from core.generation.text_artifact_service import TextArtifactService
from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactType, ArtifactStatus
from core.ai.ai_engine import AIEngine
from core.ai.ai_response import AIResponse

# ==========================================
# 1. MOCK DATA & SERVICES
# ==========================================
class MockSource:
    def __init__(self):
        self.fingerprint = "source_hash_123"

class MockState:
    def __init__(self):
        self.timing_artifact_id = "timing_123"
        self.active_artifact_id = "timing_123"
        self.text_artifact_id = "text_123"

class MockProject:
    def __init__(self, temp_dir):
        self.project_id = "proj_123"
        self.project_dir = temp_dir
        self.state = MockState()
        self.source = MockSource()
        self.state.timing = self.state

class MockArtifactStore:
    def __init__(self):
        self._store = {}
    def register(self, artifact):
        self._store[artifact.artifact_id] = artifact
    def get(self, art_id):
        return self._store.get(art_id)

class MockProjectService:
    def __init__(self, temp_dir):
        self.current_project = MockProject(temp_dir)
        self.artifact_store = MockArtifactStore()
        
        # Đăng ký sẵn Timing Artifact (Rev 5)
        timing_art = Artifact("timing_123", ArtifactType.TIMING, "dummy.srt", "now", "now", "proj_123", ArtifactStatus.READY)
        timing_art.revision = 5
        self.artifact_store.register(timing_art)

        # Đăng ký sẵn Text Artifact (Rev 0)
        text_dir = os.path.join(temp_dir, "artifacts", "text")
        os.makedirs(text_dir, exist_ok=True)
        text_path = os.path.join(text_dir, "text_123_text.json")
        text_art = Artifact("text_123", ArtifactType.TEXT, text_path, "now", "now", "proj_123", ArtifactStatus.READY)
        text_art.revision = 0
        self.artifact_store.register(text_art)

    def mark_dirty(self): pass

class MockSegment:
    def __init__(self, sid):
        self.id = sid
        self.text = ""
        self.status = "timing_only"

class MockDataProvider:
    def __init__(self):
        self.segments = {f"seg_{i}": MockSegment(f"seg_{i}") for i in range(1, 25)}
    def get_segment(self, sid):
        return self.segments.get(sid)


# ==========================================
# 2. BỘ TEST INTEGRATION HOÀN CHỈNH
# ==========================================
class TestGenerationIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ps = MockProjectService(self.test_dir)
        self.dp = MockDataProvider()
        self.checkpoint_mgr = GenerationCheckpointManager(self.ps)
        self.text_service = TextArtifactService(self.ps, self.dp)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_01_atomic_checkpoint_roundtrip(self):
        """Chứng minh file Checkpoint được ghi nguyên tử (Atomic) và nạp lại chuẩn xác"""
        chk = GenerationCheckpoint(
            project_id="proj_123",
            source_fingerprint="source_hash_123",
            timing_artifact_id="timing_123",
            text_artifact_id="text_123",
            timing_revision=5,
            text_revision=0,
            next_segment_index=1,
            completed_batches=[],
            request_data={"request_id": "req_1"},
            batches_data=[],
            active_batch=None,
            updated_at="now",
            status="RUNNING"
        )
        
        self.checkpoint_mgr.save_checkpoint(chk)
        loaded_chk = self.checkpoint_mgr.load_checkpoint()
        
        self.assertIsNotNone(loaded_chk)
        self.assertEqual(loaded_chk.project_id, "proj_123")
        self.assertEqual(loaded_chk.timing_revision, 5)
        self.assertEqual(loaded_chk.text_revision, 0)
        self.assertEqual(loaded_chk.status, "RUNNING")
        self.assertTrue(os.path.exists(self.checkpoint_mgr._get_checkpoint_path()))

    def test_02_text_artifact_atomic_commit(self):
        """Chứng minh Candidate được lưu Atomic xuống Text Artifact và cập nhật RAM UI an toàn"""
        chk = GenerationCheckpoint(
            project_id="proj_123",
            source_fingerprint="source_hash_123",
            timing_artifact_id="timing_123",
            text_artifact_id="text_123",
            timing_revision=5,
            text_revision=0,
            next_segment_index=1,
            completed_batches=[],
            request_data={"request_id": "req_1"},
            batches_data=[],
            active_batch=None,
            updated_at="now",
            status="RUNNING"
        )
        candidates = [GenerationCandidate("seg_1", "", "Bản dịch test", "model_1", "req_1", 1.0, "PASSED", [])]
        
        success = self.text_service.commit_candidates(candidates, chk)
        self.assertTrue(success)
        
        # UI Runtime phải có dữ liệu
        seg = self.dp.get_segment("seg_1")
        self.assertEqual(seg.text, "Bản dịch test")
        self.assertEqual(seg.status, "draft")
        
        # Text Artifact Revision phải tăng từ 0 lên 1
        artifact = self.ps.artifact_store.get("text_123")
        self.assertEqual(artifact.revision, 1)

    def test_03_stale_timing_guard_rejects_commit(self):
        """Chứng minh STALE GUARD chặn đứng việc ghi đè nếu Timeline bị User sửa"""
        chk = GenerationCheckpoint(
            project_id="proj_123",
            source_fingerprint="source_hash_123",
            timing_artifact_id="timing_123",
            text_artifact_id="text_123",
            timing_revision=5,
            text_revision=0,
            next_segment_index=1,
            completed_batches=[],
            request_data={"request_id": "req_1"},
            batches_data=[],
            active_batch=None,
            updated_at="now",
            status="RUNNING"
        )
        candidates = [GenerationCandidate("seg_1", "", "Dịch ngầm", "model_1", "req_1", 1.0, "PASSED", [])]
        
        # Giả lập Timeline bị sửa (Revision nhảy từ 5 lên 6)
        self.ps.artifact_store.get("timing_123").revision = 6
        
        with self.assertRaises(RuntimeError) as context:
            self.text_service.commit_candidates(candidates, chk)
            
        self.assertTrue("STALE_TIMING" in str(context.exception))
        self.assertEqual(self.dp.get_segment("seg_1").text, "")

    def test_04_resume_identity_validation_failure(self):
        """Chứng minh Resume từ chối khôi phục nếu mở sai Dự án hoặc sai Artifact"""
        class DummyAIEngine(AIEngine):
            def generate(self, req): pass
            def load_model(self, path): pass
            def unload_model(self): pass

        gen_service = GenerationService(DummyAIEngine(), self.ps, self.dp)
        
        chk = GenerationCheckpoint(
            project_id="proj_123",
            source_fingerprint="source_hash_123",
            timing_artifact_id="timing_123",
            text_artifact_id="text_123",
            timing_revision=5,
            text_revision=0,
            next_segment_index=1,
            completed_batches=[],
            request_data={"request_id": "req_1"},
            batches_data=[],
            active_batch=None,
            updated_at="now",
            status="RUNNING"
        )
        self.checkpoint_mgr.save_checkpoint(chk)
        
        # Giả lập ID dự án bị mismatch
        self.ps.current_project.project_id = "proj_HACKER_999"
        
        with self.assertRaises(ValueError) as context:
            gen_service.resume_generation([{"id": "seg_1", "text": ""}])
            
        self.assertTrue("Checkpoint thuộc về Project khác" in str(context.exception))

    def test_05_resume_skips_completed_batches_and_completes_session(self):
        """Chứng minh Resume bỏ qua batch cũ và tịnh tiến Checkpoint đến tận cùng"""
        from core.generation.generation_service import GenerationService
        from core.ai.ai_engine import AIEngine
        from core.ai.ai_response import AIResponse
        from workers.generation_worker import GenerationBatchWorker # Đưa Worker vào để Patch

        class MockAIEngineFast(AIEngine):
            def __init__(self): self.call_count = 0
            def generate(self, req):
                self.call_count += 1
                import re
                target_ids = re.findall(r"ID: (seg_\d+)", req.prompt)
                return AIResponse(req.request_id, "", parsed_json={"segments": [{"id": sid, "text": "D"} for sid in target_ids]})
            def load_model(self, path): pass
            def unload_model(self): pass

        mock_ai = MockAIEngineFast()
        gen_service = GenerationService(mock_ai, self.ps, self.dp)

        req_data = {
            "request_id": "req_1", "project_id": "proj_123", "source_fingerprint": "source_hash_123",
            "timing_artifact_id": "timing_123", "start_segment": 1, "end_segment": 20, "mode": "fill_text",
            "source_language": "vi", "target_language": "vi", "context_before": 3, "context_after": 3,
            "model_id": "mock_m", "temperature": 0.2, "max_tokens": 1000
        }
        b1_data = {"batch_id": "b1", "start_stt": 1, "end_stt": 10, "status": "PENDING", "revision": 0, "created_at": "now", "updated_at": "now"}
        b2_data = {"batch_id": "b2", "start_stt": 11, "end_stt": 20, "status": "PENDING", "revision": 0, "created_at": "now", "updated_at": "now"}

        chk = GenerationCheckpoint(
            "proj_123", "source_hash_123", "timing_123", "text_123", 5, 0, 11, ["b1"], req_data, [b1_data, b2_data], None, "now", "RUNNING"
        )
        self.checkpoint_mgr.save_checkpoint(chk)

        dummy_segs = [{"id": f"seg_{i}", "text": ""} for i in range(1, 21)]

        # --- TRICK: ÉP WORKER CHẠY ĐỒNG BỘ ĐỂ KIỂM THỬ SIGNAL ---
        original_start = GenerationBatchWorker.start
        GenerationBatchWorker.start = lambda self: self.run()

        try:
            # Action
            gen_service.resume_generation(dummy_segs)

            # Không cần wait() nữa vì code đã chạy đồng bộ
            self.assertEqual(gen_service.current_batches[0].status, "COMPLETED")
            self.assertEqual(mock_ai.call_count, 1)

            chk_final = self.checkpoint_mgr.load_checkpoint()
            self.assertEqual(chk_final.status, "COMPLETED")
            self.assertIsNone(chk_final.active_batch)
            self.assertEqual(chk_final.next_segment_index, 21)
            self.assertEqual(chk_final.completed_batches, ["b1", "b2"])
            
        finally:
            # Trả lại hàm start gốc để không ảnh hưởng các test khác
            GenerationBatchWorker.start = original_start
            gen_service.cancel_generation()

    def test_06_orchestration_persists_state_progression(self):
        """Chứng minh GenerationService cập nhật chuẩn xác next_segment, active_batch và text_revision xuống đĩa"""
        class DummyAI(AIEngine):
            def generate(self, req): pass
            def load_model(self, path): pass
            def unload_model(self): pass

        gen_service = GenerationService(DummyAI(), self.ps, self.dp)
        
        # Setup Initial State ngay trước khi B1 hoàn thành
        b1_data = {"batch_id": "b1", "start_stt": 1, "end_stt": 10, "status": "RUNNING", "revision": 0, "created_at": "now", "updated_at": "now"}
        chk = GenerationCheckpoint(
            "proj_123", "source_hash_123", "timing_123", "text_123", 5, 0, 1, [], {"request_id": "req_1"}, [b1_data], b1_data, "now", "RUNNING"
        )
        self.checkpoint_mgr.save_checkpoint(chk)
        
        # Bơm State vào RAM (Mô phỏng Worker đang chạy)
        gen_service.current_checkpoint = chk
        gen_service.current_batches = [GenerationBatch(**b1_data)]
        gen_service.current_request = GenerationRequest("req_1", "proj_123", "hash", "timing_123", 1, 10, "fill", "vi", "vi", 3, 3, "m", 0.2, 100)
        
        # Action: Main Thread nhận Signal từ Worker
        batch = gen_service.current_batches[0]
        candidates = [GenerationCandidate("seg_1", "", "Text", "m", "req_1", 1.0, "PASSED", [])]
        gen_service._sync_commit_batch_slot(batch, candidates, "req_1")
        
        # Verify Persistent State (Nạp lại từ đĩa)
        loaded = self.checkpoint_mgr.load_checkpoint()
        self.assertEqual(loaded.text_revision, 1)
        self.assertEqual(loaded.next_segment_index, 11)
        self.assertIsNone(loaded.active_batch)
        self.assertIn("b1", loaded.completed_batches)

    def test_07_stale_text_guard_rejects_commit(self):
        """Chứng minh STALE GUARD chặn đứng việc ghi đè nếu Text Artifact bị User sửa giữa chừng"""
        chk = GenerationCheckpoint("proj_123", "hash", "timing_123", "text_123", 5, 0, 1, [], {"request_id": "req_1"}, [], None, "now", "RUNNING")
        candidates = [GenerationCandidate("seg_1", "", "Dịch ngầm", "m", "req_1", 1.0, "PASSED", [])]

        # Giả lập Text Artifact bị sửa (Revision nhảy từ 0 lên 1)
        text_art = self.ps.artifact_store.get("text_123")
        text_art.revision = 1

        with self.assertRaises(RuntimeError) as context:
            self.text_service.commit_candidates(candidates, chk)

        self.assertTrue("STALE_TEXT" in str(context.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)