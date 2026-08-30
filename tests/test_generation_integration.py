import unittest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.generation.generation_request import GenerationRequest
from core.generation.generation_batch import GenerationBatch
from core.generation.generation_candidate import GenerationCandidate
from core.generation.generation_checkpoint import GenerationCheckpoint
from core.generation.generation_checkpoint_manager import GenerationCheckpointManager
from core.generation.text_artifact_service import TextArtifactService
from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactType

# ==========================================
# 1. MOCK (GIẢ LẬP MÔI TRƯỜNG DỰ ÁN THỰC TẾ)
# ==========================================
class MockSource:
    def __init__(self):
        self.fingerprint = "source_hash_123"

class MockState:
    def __init__(self):
        self.timing_artifact_id = "timing_123"
        self.active_artifact_id = "timing_123"
        self.text_artifact_id = None

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
        
        # Đăng ký sẵn Timing Artifact
        timing_art = Artifact("timing_123", ArtifactType.TIMING, "dummy.srt", "now", "now", "proj_123", "READY")
        timing_art.revision = 5
        self.artifact_store.register(timing_art)

    def mark_dirty(self): pass

class MockDataProvider:
    def __init__(self):
        self.segments = {"seg_1": MockSegment("seg_1")}
    def get_segment(self, sid):
        return self.segments.get(sid)

class MockSegment:
    def __init__(self, sid):
        self.id = sid
        self.text = ""
        self.status = "timing_only"

# ==========================================
# 2. BỘ KIỂM THỬ TÍCH HỢP (INTEGRATION TESTS)
# ==========================================
class TestGenerationIntegration(unittest.TestCase):
    def setUp(self):
        # Tạo thư mục tạm trên ổ cứng để test Atomic Write thật sự
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
            project_id="proj_123", source_fingerprint="source_hash_123",
            timing_artifact_id="timing_123", text_artifact_id="text_123",
            request_id="req_1", generation_revision=5, next_segment_index=1,
            completed_batches=[], request_data={}, batches_data=[], active_batch=None, updated_at="now"
        )
        
        # Lưu file
        self.checkpoint_mgr.save_checkpoint(chk)
        
        # Nạp file
        loaded_chk = self.checkpoint_mgr.load_checkpoint()
        self.assertIsNotNone(loaded_chk)
        self.assertEqual(loaded_chk.project_id, "proj_123")
        self.assertEqual(loaded_chk.generation_revision, 5)
        
        # Xác minh đường dẫn vật lý
        chk_path = self.checkpoint_mgr._get_checkpoint_path()
        self.assertTrue(os.path.exists(chk_path), "File checkpoint.json không tồn tại trên ổ cứng!")

    def test_02_text_artifact_atomic_commit(self):
        """Chứng minh Candidate được lưu Atomic xuống Text Artifact và cập nhật RAM UI an toàn"""
        chk = GenerationCheckpoint(
            "proj_123", "source_hash_123", "timing_123", "text_123", "req_1", 5, 1, [], {}, [], None, "now"
        )
        candidates = [GenerationCandidate("seg_1", "", "Bản dịch test", "model_1", "req_1", 1.0, "PASSED", [])]
        
        # Thực hiện Commit
        success = self.text_service.commit_candidates(candidates, chk)
        self.assertTrue(success)
        
        # Kiểm tra dữ liệu UI Runtime
        seg = self.dp.get_segment("seg_1")
        self.assertEqual(seg.text, "Bản dịch test")
        self.assertEqual(seg.status, "draft")
        
        # Kiểm tra Artifact File
        art_id = self.ps.current_project.state.text_artifact_id
        self.assertIsNotNone(art_id)
        artifact = self.ps.artifact_store.get(art_id)
        self.assertEqual(artifact.revision, 1) # Text Revision phải tăng 1

    def test_03_stale_timing_guard_rejects_commit(self):
        """Chứng minh STALE GUARD chặn đứng việc ghi đè nếu Timeline bị User sửa"""
        chk = GenerationCheckpoint(
            "proj_123", "source_hash_123", "timing_123", "text_123", "req_1", 5, 1, [], {}, [], None, "now"
        )
        candidates = [GenerationCandidate("seg_1", "", "Dịch ngầm", "model_1", "req_1", 1.0, "PASSED", [])]
        
        # CỐ TÌNH: Giả lập người dùng bấm cắt/gộp Timeline làm tăng Revision lên 6
        self.ps.artifact_store.get("timing_123").revision = 6
        
        # TextService phải ném lỗi STALE_TIMING
        with self.assertRaises(RuntimeError) as context:
            self.text_service.commit_candidates(candidates, chk)
            
        self.assertTrue("STALE_TIMING" in str(context.exception))
        
        # Dữ liệu UI tuyệt đối không được phép đổi
        self.assertEqual(self.dp.get_segment("seg_1").text, "")

    def test_04_resume_identity_validation_failure(self):
        """Chứng minh Resume từ chối khôi phục nếu mở sai Dự án (Project/Source Mismatch)"""
        from core.generation.generation_service import GenerationService
        from core.ai.ai_engine import AIEngine
        class DummyAIEngine(AIEngine):
            def generate(self, req): pass
            def load_model(self, path): pass
            def unload_model(self): pass

        gen_service = GenerationService(DummyAIEngine(), self.ps, self.dp)
        
        chk = GenerationCheckpoint(
            "proj_123", "source_hash_123", "timing_123", "text_123", "req_1", 5, 1, [], {}, [], None, "now"
        )
        self.checkpoint_mgr.save_checkpoint(chk)
        
        # CỐ TÌNH: Giả lập mở một dự án khác (ID khác) nhưng thư mục vô tình trỏ tới Checkpoint cũ
        self.ps.current_project.project_id = "proj_HACKER_999"
        
        with self.assertRaises(ValueError) as context:
            gen_service.resume_generation([{"id": "seg_1", "text": ""}])
            
        self.assertTrue("Checkpoint thuộc về Project khác" in str(context.exception))

if __name__ == '__main__':
    unittest.main(verbosity=2)