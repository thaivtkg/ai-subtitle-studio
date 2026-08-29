import unittest
import uuid
import sys
import os

# Đảm bảo import được các module từ thư mục gốc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.timeline.timeline_data_provider import TimelineDataProvider
from core.timeline.timeline_commands import (
    MoveSegmentCommand, 
    ResizeStartCommand, 
    SplitSegmentCommand, 
    MergeSegmentsCommand, 
    DeleteSegmentCommand
)

# ==========================================
# 1. MOCK (GIẢ LẬP) CÁC DEPENDENCY CỦA CORE
# ==========================================
class MockArtifact:
    def __init__(self):
        self.revision = 0

class MockArtifactStore:
    def __init__(self):
        self._store = {"valid_art_id": MockArtifact()}
    def get(self, art_id):
        return self._store.get(art_id)

class MockTimingState:
    def __init__(self):
        self.timing_artifact_id = "valid_art_id"

class MockProjectState:
    def __init__(self):
        self.active_artifact_id = "valid_art_id"
        self.timing = MockTimingState()

class MockProject:
    def __init__(self):
        self.state = MockProjectState()

class MockProjectService:
    def __init__(self):
        self.current_project = MockProject()
        self.artifact_store = MockArtifactStore()
        self.is_dirty = False
    def mark_dirty(self):
        self.is_dirty = True


# ==========================================
# 2. TEST SUITE CHỨNG MINH 100% PASS
# ==========================================
class TestTimelineCommands(unittest.TestCase):
    def setUp(self):
        self.ps = MockProjectService()
        self.dp = TimelineDataProvider()
        
        # Nạp dữ liệu giả lập (2 segment liền kề)
        raw_data = [
            {"id": "seg_1", "start_ms": 0, "end_ms": 5000, "text": "Câu một"},
            {"id": "seg_2", "start_ms": 5000, "end_ms": 10000, "text": "Câu hai"}
        ]
        self.dp.load_runtime_data(raw_data, 15000)

    def test_01_move_undo_redo_exact_state(self):
        """Chứng minh Move Command giữ đúng trạng thái khi Undo/Redo"""
        cmd = MoveSegmentCommand(self.ps, self.dp, "seg_1", 1000)
        self.assertTrue(cmd.can_execute())
        
        cmd.execute()
        self.assertEqual(self.dp.get_segment("seg_1").start_ms, 1000)
        self.assertEqual(self.dp.get_segment("seg_1").end_ms, 6000)
        
        cmd.undo()
        self.assertEqual(self.dp.get_segment("seg_1").start_ms, 0, "Undo không khôi phục đúng start_ms")
        
        cmd.redo()
        self.assertEqual(self.dp.get_segment("seg_1").start_ms, 1000, "Redo không khôi phục đúng start_ms")

    def test_02_split_structural_integrity(self):
        """Chứng minh Split tạo khối mới và Undo xóa sạch khối đó"""
        cmd = SplitSegmentCommand(self.ps, self.dp, "seg_1", 2500)
        self.assertTrue(cmd.can_execute())
        cmd.execute()
        
        # Sau khi cắt, phải có 3 khối. Khối 1 end ở 2500
        self.assertEqual(len(self.dp.get_all_segments()), 3)
        self.assertEqual(self.dp.get_segment("seg_1").end_ms, 2500)
        
        cmd.undo()
        # Khôi phục đúng 2 khối, Khối 1 về lại 5000
        self.assertEqual(len(self.dp.get_all_segments()), 2, "Bóng ma khối mới chưa bị xóa khi Undo")
        self.assertEqual(self.dp.get_segment("seg_1").end_ms, 5000)

    def test_03_merge_text_and_timing_integrity(self):
        """Chứng minh Merge gộp chữ chuẩn và Redo tái lập đúng Snapshot"""
        cmd = MergeSegmentsCommand(self.ps, self.dp, ["seg_1", "seg_2"])
        self.assertTrue(cmd.can_execute())
        cmd.execute()
        
        self.assertEqual(len(self.dp.get_all_segments()), 1)
        seg1 = self.dp.get_segment("seg_1")
        self.assertEqual(seg1.end_ms, 10000)
        self.assertEqual(seg1.text, "Câu một Câu hai")
        
        cmd.undo()
        self.assertEqual(len(self.dp.get_all_segments()), 2)
        self.assertEqual(self.dp.get_segment("seg_2").text, "Câu hai")
        
        cmd.redo()
        self.assertEqual(len(self.dp.get_all_segments()), 1)

    def test_04_delete_restoration(self):
        """Chứng minh Delete có thể Undo để khôi phục khối"""
        cmd = DeleteSegmentCommand(self.ps, self.dp, ["seg_2"])
        cmd.execute()
        
        self.assertIsNone(self.dp.get_segment("seg_2"))
        
        cmd.undo()
        self.assertIsNotNone(self.dp.get_segment("seg_2"))
        self.assertEqual(self.dp.get_segment("seg_2").end_ms, 10000)

    def test_05_revision_failure_rollback(self):
        """Chứng minh tính Atomic (Transaction fail nếu Artifact mất)"""
        # Cố tình làm hỏng ID Artifact để gây lỗi
        self.ps.current_project.state.timing.timing_artifact_id = "invalid_id"
        
        cmd = MoveSegmentCommand(self.ps, self.dp, "seg_1", 1000)
        with self.assertRaises(RuntimeError) as context:
            cmd.execute()
            
        self.assertTrue("Lỗi Integrity" in str(context.exception))
        # Vì lỗi, trạng thái dữ liệu phải bị chặn lại không được đổi
        self.assertEqual(self.ps.artifact_store.get("valid_art_id").revision, 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)