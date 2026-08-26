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
        project = self.project_service.current_project
        if not project:
            raise ValueError("Không có dự án nào đang mở.")
        video_path = project.source.path
        if not os.path.exists(video_path):
            raise FileNotFoundError("Không tìm thấy video gốc.")
        
        current_fp = self.project_service._generate_fingerprint(video_path)
        if current_fp.fingerprint != project.source.fingerprint:
            raise ValueError("Video gốc đã bị thay đổi (Sai lệch mã Hash).")

    def _validate_checkpoint_identity(self, checkpoint: TimingCheckpoint):
        """[S7.1-FIX-03] Kiểm tra chéo toàn bộ danh tính của Checkpoint"""
        project = self.project_service.current_project
        if checkpoint.project_id != project.project_id:
            raise ValueError("Checkpoint không thuộc về Dự án hiện tại.")
        if checkpoint.source_fingerprint != project.source.fingerprint:
            raise ValueError("Vân tay video trong Checkpoint không khớp với video gốc.")
        if checkpoint.timing_artifact_id != project.state.timing.timing_artifact_id:
            raise ValueError("ID của Timing Artifact không khớp với Checkpoint.")

    def start_timing(self, batch_size: int, settings: dict):
        self._validate_source_and_state()
        project = self.project_service.current_project
        timing_state = project.state.timing
        
        timing_state.batch_size = batch_size
        timing_state.next_segment_index = 1
        timing_state.completed_until = 0
        timing_state.timing_artifact_id = None
        timing_state.checkpoint_id = None
        timing_state.status = "RUNNING"
        
        # [S7.1-FIX-02] Tạo Active Batch thực sự
        import uuid
        from core.timing.timing_batch import TimingBatch, BatchStatus
        from datetime import datetime
        from dataclasses import asdict
        
        new_batch = TimingBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:8]}",
            start_segment=1,
            end_segment=batch_size,
            start_ms=0,
            end_ms=0,
            status=BatchStatus.RUNNING,
            revision=1,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.active_batch_data = asdict(new_batch)
        
        self.project_service.mark_dirty()
        self.state_changed_signal.emit("RUNNING", "Đang khởi tạo luồng Timing...")
        self._execute_run(start_ms=0, target_count=batch_size, settings=settings)

    # Bổ sung tham số batch_size
    def continue_timing(self, batch_size: int, settings: dict):
        self._validate_source_and_state()
        project = self.project_service.current_project
        timing_state = project.state.timing
        
        # [FIX S7.1] Cập nhật kích thước Batch mới từ UI
        timing_state.batch_size = batch_size
        
        checkpoint = self.project_service.load_timing_checkpoint()
        if not checkpoint:
            raise ValueError("Không tìm thấy dữ liệu Checkpoint.")
            
        self._validate_checkpoint_identity(checkpoint)
            
        artifact = self.project_service.artifact_store.get(checkpoint.timing_artifact_id)
        if not artifact or not os.path.exists(artifact.path):
            raise ValueError("Không tìm thấy file Artifact Timing.")
            
        if artifact.revision != checkpoint.timing_revision:
            raise ValueError(f"Dữ liệu Checkpoint bị cũ (Rev {checkpoint.timing_revision}).")

        from core.timing.timing_batch import TimingBatch, BatchStatus
        from datetime import datetime
        from dataclasses import asdict
        import uuid
        
        start_idx = checkpoint.next_segment_index
        new_batch = TimingBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:8]}",
            start_segment=start_idx,
            
            # [FIX S7.1] Tính toán end_segment theo batch_size mới
            end_segment=start_idx + batch_size - 1, 
            
            start_ms=checkpoint.last_completed_end_ms,
            end_ms=0,
            status=BatchStatus.RUNNING,
            revision=artifact.revision,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.active_batch_data = asdict(new_batch)

        timing_state.status = "RUNNING"
        self.project_service.mark_dirty()
        
        self.state_changed_signal.emit("RUNNING", f"Đang tiếp tục từ câu {start_idx}...")
        self._execute_run(start_ms=checkpoint.last_completed_end_ms, target_count=batch_size, settings=settings)

    # Bổ sung tham số batch_size
    def retry_timing(self, batch_size: int, settings: dict):
        self._validate_source_and_state()
        checkpoint = self.project_service.load_timing_checkpoint()
        
        if not checkpoint or not checkpoint.active_batch:
            raise ValueError("Không có Batch nào đang ở trạng thái lỗi để Retry.")
            
        self._validate_checkpoint_identity(checkpoint)
        
        if checkpoint.active_batch["status"] != "FAILED":
            raise ValueError("Batch hiện tại không ở trạng thái LỖI.")

        # [FIX S7.1] Cho phép giảm/tăng cấu hình Batch Size khi Retry để né vùng Audio lỗi
        checkpoint.active_batch["status"] = "RUNNING"
        checkpoint.active_batch["end_segment"] = checkpoint.active_batch["start_segment"] + batch_size - 1
        self.active_batch_data = checkpoint.active_batch
        
        project = self.project_service.current_project
        project.state.timing.batch_size = batch_size
        project.state.timing.status = "RUNNING"
        
        self.state_changed_signal.emit("RUNNING", f"Đang thử lại Batch lỗi từ câu {checkpoint.active_batch['start_segment']}...")
        self._execute_run(
            start_ms=checkpoint.active_batch["start_ms"], 
            target_count=batch_size, 
            settings=settings
        )
        
    def retry_timing(self, settings: dict):
        """[S7.1-FIX-02] Thử lại đúng Batch bị lỗi dựa trên dữ liệu Checkpoint"""
        self._validate_source_and_state()
        checkpoint = self.project_service.load_timing_checkpoint()
        
        if not checkpoint or not checkpoint.active_batch:
            raise ValueError("Không có Batch nào đang ở trạng thái lỗi để Retry.")
            
        self._validate_checkpoint_identity(checkpoint)
        
        if checkpoint.active_batch["status"] != "FAILED":
            raise ValueError("Batch hiện tại không ở trạng thái LỖI.")

        # Tái khởi động đúng batch đó
        checkpoint.active_batch["status"] = "RUNNING"
        self.active_batch_data = checkpoint.active_batch
        
        project = self.project_service.current_project
        project.state.timing.status = "RUNNING"
        
        self.state_changed_signal.emit("RUNNING", f"Đang thử lại Batch lỗi từ câu {checkpoint.active_batch['start_segment']}...")
        self._execute_run(
            start_ms=checkpoint.active_batch["start_ms"], 
            target_count=project.state.timing.batch_size, 
            settings=settings
        )

    def _on_worker_error(self, err: str):
        """Đánh dấu FAILED cho Active Batch và lưu Checkpoint"""
        if hasattr(self, 'active_batch_data') and self.active_batch_data:
            self.active_batch_data["status"] = "FAILED"
            
            # Cập nhật Checkpoint hiện tại để ghi nhận lỗi
            checkpoint = self.project_service.load_timing_checkpoint()
            if checkpoint:
                checkpoint.active_batch = self.active_batch_data
                self.project_service.save_timing_checkpoint(checkpoint)
                
        project = self.project_service.current_project
        if project:
            project.state.timing.status = "FAILED"
            self.project_service.save_project()
            
        self.error_signal.emit(err)
        self.state_changed_signal.emit("FAILED", "Lỗi xử lý AI. Vui lòng Retry Batch.")

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
        if not new_segments and not is_end_of_source:
            self.state_changed_signal.emit("READY", "Không có dữ liệu mới.")
            return

        project = self.project_service.current_project
        timing_state = project.state.timing
        
        # 1. Đọc và chuẩn bị dữ liệu Artifact
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

        start_index = timing_state.next_segment_index
        checkpoint = self.project_service.load_timing_checkpoint()
        last_end_ms = checkpoint.last_completed_end_ms if checkpoint else 0

        if existing_lines and existing_lines[-1].strip() != "":
            existing_lines.append("")

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

        if added_count == 0 and not is_end_of_source:
            self.state_changed_signal.emit("READY", "Sẵn sàng.")
            return

        # 2. Xây dựng Trạng thái (In-Memory)
        new_revision = current_revision + 1
        
        if hasattr(self, 'active_batch_data') and self.active_batch_data:
            self.active_batch_data["status"] = "COMPLETED"
            self.active_batch_data["end_ms"] = last_end_ms
            
        new_checkpoint = TimingCheckpoint(
            project_id=project.project_id,
            source_fingerprint=project.source.fingerprint,
            timing_artifact_id=timing_state.timing_artifact_id or "WILL_BE_SET",
            timing_revision=new_revision,
            batch_size=timing_state.batch_size,
            active_batch=None, # Clear active batch khi đã complete
            next_segment_index=start_index + added_count,
            last_completed_end_ms=last_end_ms,
            completed_batches=checkpoint.completed_batches if checkpoint else [],
            updated_at=datetime.now().isoformat()
        )
        
        if added_count > 0 and hasattr(self, 'active_batch_data'):
            new_checkpoint.completed_batches.append(self.active_batch_data["batch_id"])

        # 3. [S7.1-FIX-01] THỰC THI ATOMIC MULTI-FILE TRANSACTION
        try:
            # Phase 3.1: Ghi toàn bộ ra file tạm (.tmp)
            temp_artifact = artifact_path + ".tmp"
            with open(temp_artifact, 'w', encoding='utf-8') as f:
                f.write("\n".join(existing_lines))
                f.flush()
                os.fsync(f.fileno())
                
            # Phase 3.2: Cập nhật Domain State (RAM)
            artifact_metadata = {
                "batch_size": timing_state.batch_size,
                "completed_until": start_index + added_count - 1,
                "last_completed_end_ms": last_end_ms
            }

            if not timing_state.timing_artifact_id:
                new_art_id = str(uuid.uuid4())
                from core.artifacts.artifact_types import ArtifactType, ArtifactStatus
                from core.artifacts.artifact import Artifact
                art = Artifact(
                    artifact_id=new_art_id, artifact_type=ArtifactType.TIMING, path=artifact_path,
                    created_at=datetime.now().isoformat(), updated_at=datetime.now().isoformat(),
                    source_project_id=project.project_id, status=ArtifactStatus.READY,
                    revision=new_revision, metadata=artifact_metadata
                )
                self.project_service.artifact_store.register(art)
                timing_state.timing_artifact_id = new_art_id
                new_checkpoint.timing_artifact_id = new_art_id
            else:
                art = self.project_service.artifact_store.get(timing_state.timing_artifact_id)
                art.revision = new_revision
                art.metadata.update(artifact_metadata)
                
            project.state.active_artifact_id = timing_state.timing_artifact_id
            timing_state.completed_until = start_index + added_count - 1
            timing_state.next_segment_index = start_index + added_count
            timing_state.checkpoint_id = "checkpoint.json"
            
            if is_end_of_source:
                timing_state.status = "COMPLETED"
                project.state.timing_status = "READY"
            else:
                timing_state.status = "IDLE"
                project.state.timing_status = "DRAFT"

            # Phase 3.3: Replace nguyên tử toàn bộ file cấu hình
            os.replace(temp_artifact, artifact_path) # Commit SRT
            self.project_service.save_timing_checkpoint(new_checkpoint) # Commit Checkpoint
            self.project_service.save_project() # Commit State & Manifest
            
        except Exception as e:
            # Nếu có lỗi ghi đĩa, hệ thống ném exception, các file gốc không bị suy suyển.
            self.error_signal.emit(f"Lỗi khi Commit Batch: {str(e)}")
            self.state_changed_signal.emit("FAILED", "Lỗi ghi đĩa.")
            return

        # 4. Phát tín hiệu UI
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