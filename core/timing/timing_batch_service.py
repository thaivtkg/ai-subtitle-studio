import os
import uuid
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactStatus, ArtifactType
from core.services.project_service import ProjectService
from core.timing.timing_checkpoint import TimingCheckpoint
from core.timing.timing_run_request import TimingRunRequest
from workers.TimingBatchWorker import TimingBatchWorker


class TimingBatchService(QObject):
    """
    [S7.1-T14] Service Điều phối Timing Batch.
    Tuân thủ tuyệt đối các Invariant: Không chạy lại batch đã hoàn thành, Source Guard, Checkpoint Stale Validation.
    """
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    batch_completed_signal = Signal(int, int) # (added_count, batch_size)
    timing_finished_signal = Signal()
    error_signal = Signal(str)
    state_changed_signal = Signal(str, str) # (Status, Message)

    def __init__(self, project_service: ProjectService):
        super().__init__()
        self.project_service = project_service
        self.worker = None
        self._current_settings = None

    def _validate_source_and_state(self):
        """[S7.1-T29] & [S7.1-E] Bức tường lửa bảo vệ Invariant"""
        project = self.project_service.current_project
        if not project:
            raise ValueError("Không có dự án nào đang mở.")
        video_path = project.source.path
        if not os.path.exists(video_path):
            raise FileNotFoundError("Không tìm thấy video gốc.")
        
        # Fast Fingerprint Validation
        current_fp = self.project_service._generate_fingerprint(video_path)
        if current_fp.fingerprint != project.source.fingerprint:
            raise ValueError("Video gốc đã bị thay đổi (Sai lệch mã Hash). Không thể tiếp tục để bảo vệ dữ liệu Timing cũ.")

    def start_timing(self, batch_size: int, settings: dict):
        """[S7.1-T15] Bắt đầu phiên Timing mới hoàn toàn (Xóa trắng state cũ)"""
        self._validate_source_and_state()
        
        project = self.project_service.current_project
        timing_state = project.state.timing
        
        # Reset State
        timing_state.batch_size = batch_size
        timing_state.next_segment_index = 1
        timing_state.completed_until = 0
        timing_state.timing_artifact_id = None
        timing_state.checkpoint_id = None
        timing_state.status = "RUNNING"
        
        self.project_service.mark_dirty()
        
        self.state_changed_signal.emit("RUNNING", "Đang khởi tạo luồng Timing...")
        self._execute_run(start_ms=0, target_count=batch_size, settings=settings)

    def continue_timing(self, settings: dict):
        """[S7.1-T16] Tiếp tục Timing từ Checkpoint gần nhất"""
        self._validate_source_and_state()
        project = self.project_service.current_project
        timing_state = project.state.timing
        
        checkpoint = self.project_service.load_timing_checkpoint()
        if not checkpoint:
            raise ValueError("Không tìm thấy dữ liệu Checkpoint. Vui lòng Bắt đầu Timing mới.")
            
        # [S7.1-E] Stale Checkpoint Validation
        artifact_id = checkpoint.timing_artifact_id
        artifact = self.project_service.artifact_store.get(artifact_id)
        
        if not artifact or not os.path.exists(artifact.path):
            raise ValueError("Không tìm thấy file Artifact Timing. Dữ liệu có thể đã bị xóa.")
            
        if artifact.revision != checkpoint.timing_revision:
            raise ValueError(f"Dữ liệu Checkpoint bị cũ (Rev {checkpoint.timing_revision}) so với Artifact hiện tại (Rev {artifact.revision}). Không thể Continue an toàn.")

        timing_state.status = "RUNNING"
        self.project_service.mark_dirty()
        
        self.state_changed_signal.emit("RUNNING", f"Đang tiếp tục từ câu {checkpoint.next_segment_index}...")
        self._execute_run(start_ms=checkpoint.last_completed_end_ms, target_count=timing_state.batch_size, settings=settings)

    def retry_timing(self, settings: dict):
        """[S7.1-T17] Thử lại Batch bị lỗi (Bản chất là Continue vì Checkpoint chưa nhích lên)"""
        self.continue_timing(settings)

    def cancel_timing(self):
        """[S7.1-T18] Hủy ngang tiến trình (Chỉ Dừng Worker, KHÔNG commit)"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            project = self.project_service.current_project
            if project:
                project.state.timing.status = "IDLE"
                self.project_service.mark_dirty()
            self.state_changed_signal.emit("READY", "Đã hủy tiến trình. Có thể Continue bất cứ lúc nào.")

    def _execute_run(self, start_ms: int, target_count: int, settings: dict):
        self._current_settings = settings
        project = self.project_service.current_project
        
        request = TimingRunRequest(
            video_path=project.source.path,
            start_ms=start_ms,
            target_segment_count=target_count,
            overlap_ms=800,  # Hardcode Invariant: Lùi 800ms để bắt câu đứt quãng
            model_size=settings.get("model_size", "base"),
            compute_type=settings.get("compute_type", "float16"),
            use_vad=settings.get("use_vad", True),
            min_silence_ms=settings.get("min_silence_ms", 500)
        )
        
        self.worker = TimingBatchWorker(request)
        self.worker.progress_signal.connect(self.progress_signal.emit)
        self.worker.log_signal.connect(self.log_signal.emit)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.error_signal.connect(self._on_worker_error)
        self.worker.start()

    def _on_worker_error(self, err: str):
        project = self.project_service.current_project
        if project:
            project.state.timing.status = "FAILED"
            self.project_service.save_project() # Xả state để ghi nhớ trạng thái lỗi
        self.error_signal.emit(err)
        self.state_changed_signal.emit("FAILED", "Lỗi xử lý AI. Dữ liệu các Batch trước vẫn an toàn.")

    def _on_worker_finished(self, new_segments: list, is_end_of_source: bool):
        """
        [S7.1-T19] Khâu Commit Nguyên Tử (Atomic Commit).
        Tuân thủ thứ tự: Ghi file Artifact -> Cập nhật ArtifactStore (Tăng Rev) -> Ghi Checkpoint -> Ghi State.
        Nếu sập giữa chừng, hệ thống vẫn Recoverable.
        """
        if not new_segments and not is_end_of_source:
            self.state_changed_signal.emit("READY", "Không có dữ liệu mới (Đã bị hủy ngầm).")
            return

        project = self.project_service.current_project
        timing_state = project.state.timing
        
        # 1. Đọc Artifact hiện tại để Append
        existing_lines = []
        artifact_path = ""
        current_revision = 0
        
        if timing_state.timing_artifact_id:
            old_art = self.project_service.artifact_store.get(timing_state.timing_artifact_id)
            if old_art and os.path.exists(old_art.path):
                artifact_path = old_art.path
                current_revision = old_art.revision
                existing_lines = self._read_draft_lines(artifact_path)

        if not artifact_path:
            safe_name = "".join(c if c.isalnum() else "_" for c in project.name)
            artifacts_dir = os.path.join(self.project_service.project_dir, "artifacts", "timing")
            os.makedirs(artifacts_dir, exist_ok=True)
            artifact_path = os.path.join(artifacts_dir, f"{safe_name}_timing.srt")

        # 2. Xử lý & Format Segments mới
        start_index = timing_state.next_segment_index
        checkpoint = self.project_service.load_timing_checkpoint()
        last_end_ms = checkpoint.last_completed_end_ms if checkpoint else 0

        # --- [FIX S7.1] Bơm dòng trống cách ly nếu file cũ bị mất ngắt dòng ---
        if existing_lines and existing_lines[-1].strip() != "":
            existing_lines.append("")
        # ----------------------------------------------------------------------

        added_count = 0
        for seg in new_segments:
            stt = start_index + added_count
            start_time_str = self._ms_to_time_str(seg["start_ms"])
            end_time_str = self._ms_to_time_str(seg["end_ms"])
            
            existing_lines.append(f"{stt}")
            existing_lines.append(f"{start_time_str} --> {end_time_str}")
            existing_lines.append("[ Chưa có nội dung ]")
            existing_lines.append("")
            
            last_end_ms = seg["end_ms"]
            added_count += 1

        # Tránh commit rỗng nếu không phải end_of_source
        if added_count == 0 and not is_end_of_source:
            self.state_changed_signal.emit("READY", "Sẵn sàng.")
            return

        # 3. Ghi File Artifact (Atomic Save)
        self._atomic_save_text(artifact_path, "\n".join(existing_lines))

        # 4. Đăng ký/Cập nhật ArtifactStore (Tăng Revision)
        new_revision = current_revision + 1
        artifact_metadata = {
            "batch_size": timing_state.batch_size,
            "completed_until": start_index + added_count - 1,
            "last_completed_end_ms": last_end_ms,
            "total_segments_so_far": start_index + added_count - 1
        }

        if not timing_state.timing_artifact_id:
            new_art_id = str(uuid.uuid4())
            art = Artifact(
                artifact_id=new_art_id,
                artifact_type=ArtifactType.TIMING, 
                path=artifact_path,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                source_project_id=project.project_id,
                status=ArtifactStatus.READY,
                revision=new_revision,
                metadata=artifact_metadata
            )
            self.project_service.artifact_store.register(art)
            timing_state.timing_artifact_id = new_art_id
        else:
            art = self.project_service.artifact_store.get(timing_state.timing_artifact_id)
            art.revision = new_revision
            art.metadata.update(artifact_metadata)
            art.updated_at = datetime.now().isoformat()

        project.state.active_artifact_id = timing_state.timing_artifact_id

        # 5. Cập nhật Checkpoint
        new_checkpoint = TimingCheckpoint(
            project_id=project.project_id,
            source_fingerprint=project.source.fingerprint,
            timing_artifact_id=timing_state.timing_artifact_id,
            timing_revision=new_revision,
            batch_size=timing_state.batch_size,
            active_batch_id=None,
            next_segment_index=start_index + added_count,
            last_completed_end_ms=last_end_ms,
            completed_batches=checkpoint.completed_batches if checkpoint else [],
            updated_at=datetime.now().isoformat()
        )
        if added_count > 0:
            new_checkpoint.completed_batches.append(f"batch_{start_index}_{start_index + added_count - 1}")
        
        self.project_service.save_timing_checkpoint(new_checkpoint)

        # 6. Cập nhật State & Xả đĩa
        timing_state.completed_until = start_index + added_count - 1
        timing_state.next_segment_index = start_index + added_count
        timing_state.checkpoint_id = "checkpoint.json"
        
        if is_end_of_source:
            timing_state.status = "COMPLETED"
            project.state.timing_status = "READY"
        else:
            timing_state.status = "IDLE"
            project.state.timing_status = "DRAFT"

        # Gọi hàm của ProjectService để lưu đồng loạt: state.json, workspace.json và manifest.json
        self.project_service.save_project() 

        # 7. Phát tín hiệu cho UI
        if added_count > 0:
            self.batch_completed_signal.emit(added_count, timing_state.batch_size)
            
        if is_end_of_source:
            self.timing_finished_signal.emit()
            self.state_changed_signal.emit("COMPLETED", "Đã hoàn tất Timing toàn bộ Video!")
        else:
            self.state_changed_signal.emit("READY", f"Đã lưu Checkpoint (Đến câu {timing_state.completed_until}).")

    # --- Utilities ---
    def _read_draft_lines(self, path):
        if not os.path.exists(path): return []
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().splitlines()

    def _atomic_save_text(self, path, content):
        temp_path = path + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)

    def _ms_to_time_str(self, ms: int) -> str:
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"