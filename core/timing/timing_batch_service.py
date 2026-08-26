import os
import json
import uuid
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from dataclasses import asdict

from core.services.project_service import ProjectService
from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactType, ArtifactStatus
from core.timing.timing_checkpoint import TimingCheckpoint
from core.timing.timing_batch import TimingBatch, BatchStatus
from core.timing.timing_run_request import TimingRunRequest
from workers.TimingBatchWorker import TimingBatchWorker

class TimingBatchService(QObject):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    batch_completed_signal = Signal(int, int)
    timing_finished_signal = Signal()
    error_signal = Signal(str)
    state_changed_signal = Signal(str, str)

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
        project = self.project_service.current_project
        if checkpoint.project_id != project.project_id:
            raise ValueError("Checkpoint không thuộc về Dự án hiện tại.")
        if checkpoint.source_fingerprint != project.source.fingerprint:
            raise ValueError("Vân tay video trong Checkpoint không khớp với video gốc.")
        if checkpoint.timing_artifact_id and checkpoint.timing_artifact_id != project.state.timing.timing_artifact_id:
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
        
        # [S7.1-FIX-05] Khởi tạo và Lưu ngay Active Batch trước khi Worker chạy
        new_batch = TimingBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:8]}",
            start_segment=1,
            end_segment=batch_size,
            start_ms=0,
            end_ms=0,
            status=BatchStatus.RUNNING.value,
            revision=1,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.active_batch_data = asdict(new_batch)
        
        checkpoint = TimingCheckpoint(
            project_id=project.project_id,
            source_fingerprint=project.source.fingerprint,
            timing_artifact_id="",
            timing_revision=1,
            batch_size=batch_size,
            active_batch=self.active_batch_data,
            next_segment_index=1,
            last_completed_end_ms=0,
            completed_batches=[]
        )
        self.project_service.save_timing_checkpoint(checkpoint)
        
        self.project_service.mark_dirty()
        self.state_changed_signal.emit("RUNNING", "Đang khởi tạo luồng Timing...")
        self._execute_run(start_ms=0, target_count=batch_size, settings=settings)

    def continue_timing(self, batch_size: int, settings: dict):
        self._validate_source_and_state()
        project = self.project_service.current_project
        timing_state = project.state.timing
        timing_state.batch_size = batch_size
        
        checkpoint = self.project_service.load_timing_checkpoint()
        if not checkpoint:
            raise ValueError("Không tìm thấy dữ liệu Checkpoint.")
            
        self._validate_checkpoint_identity(checkpoint)
            
        artifact = self.project_service.artifact_store.get(checkpoint.timing_artifact_id)
        if not artifact or not os.path.exists(artifact.path):
            raise ValueError("Không tìm thấy file Artifact Timing.")
            
        # Tự động phục hồi nếu phát hiện Crash giữa giao dịch file
        if artifact.revision != checkpoint.timing_revision:
            if checkpoint.timing_revision == artifact.revision + 1:
                self.log_signal.emit("[Recovery] Phát hiện Crash khi đang Commit. Đang đồng bộ lại Revision...")
                artifact.revision = checkpoint.timing_revision
            else:
                raise ValueError(f"Dữ liệu Checkpoint bị cũ (Rev {checkpoint.timing_revision} vs {artifact.revision}).")

        start_idx = checkpoint.next_segment_index
        
        # [S7.1-FIX-05] Cập nhật Checkpoint với Batch tiếp theo trước khi chạy
        new_batch = TimingBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:8]}",
            start_segment=start_idx,
            end_segment=start_idx + batch_size - 1,
            start_ms=checkpoint.last_completed_end_ms,
            end_ms=0,
            status=BatchStatus.RUNNING.value,
            revision=artifact.revision,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.active_batch_data = asdict(new_batch)
        
        checkpoint.active_batch = self.active_batch_data
        checkpoint.batch_size = batch_size
        self.project_service.save_timing_checkpoint(checkpoint)

        timing_state.status = "RUNNING"
        self.project_service.mark_dirty()
        
        self.state_changed_signal.emit("RUNNING", f"Đang tiếp tục từ câu {start_idx}...")
        self._execute_run(start_ms=checkpoint.last_completed_end_ms, target_count=batch_size, settings=settings)

    # [S7.1-FIX-04] Dọn dẹp chỉ giữ một hàm Retry duy nhất
    def retry_timing(self, batch_size: int, settings: dict):
        self._validate_source_and_state()
        checkpoint = self.project_service.load_timing_checkpoint()
        
        if not checkpoint or not checkpoint.active_batch:
            raise ValueError("Không có Batch nào đang ở trạng thái lỗi để Retry.")
            
        self._validate_checkpoint_identity(checkpoint)
        
        # Cho phép sửa Batch Size khi Retry
        checkpoint.active_batch["status"] = "RUNNING"
        checkpoint.active_batch["end_segment"] = checkpoint.active_batch["start_segment"] + batch_size - 1
        self.active_batch_data = checkpoint.active_batch
        
        self.project_service.save_timing_checkpoint(checkpoint)
        
        project = self.project_service.current_project
        project.state.timing.batch_size = batch_size
        project.state.timing.status = "RUNNING"
        
        self.state_changed_signal.emit("RUNNING", f"Đang thử lại Batch lỗi từ câu {checkpoint.active_batch['start_segment']}...")
        self._execute_run(start_ms=checkpoint.active_batch["start_ms"], target_count=batch_size, settings=settings)

    def cancel_timing(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            project = self.project_service.current_project
            if project:
                project.state.timing.status = "IDLE"
                
                # Đánh dấu Cancelled vào checkpoint
                checkpoint = self.project_service.load_timing_checkpoint()
                if checkpoint and checkpoint.active_batch:
                    checkpoint.active_batch["status"] = "CANCELLED"
                    self.project_service.save_timing_checkpoint(checkpoint)
                    
                self.project_service.mark_dirty()
            self.state_changed_signal.emit("READY", "Đã hủy tiến trình.")

    def _execute_run(self, start_ms: int, target_count: int, settings: dict):
        self._current_settings = settings
        project = self.project_service.current_project
        request = TimingRunRequest(
            video_path=project.source.path,
            start_ms=start_ms,
            target_segment_count=target_count,
            overlap_ms=800,
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
        if hasattr(self, 'active_batch_data') and self.active_batch_data:
            self.active_batch_data["status"] = "FAILED"
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

    def _on_worker_finished(self, new_segments: list, is_end_of_source: bool):
        if not new_segments and not is_end_of_source:
            self.state_changed_signal.emit("READY", "Không có dữ liệu mới.")
            return

        project = self.project_service.current_project
        timing_state = project.state.timing
        
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
            active_batch=None, # Xóa active batch vì đã hoàn tất an toàn
            next_segment_index=start_index + added_count,
            last_completed_end_ms=last_end_ms,
            completed_batches=checkpoint.completed_batches if checkpoint else [],
            updated_at=datetime.now().isoformat()
        )
        if added_count > 0 and hasattr(self, 'active_batch_data'):
            new_checkpoint.completed_batches.append(self.active_batch_data["batch_id"])

        # Cập nhật Memory State
        artifact_metadata = {
            "batch_size": timing_state.batch_size,
            "completed_until": start_index + added_count - 1,
            "last_completed_end_ms": last_end_ms
        }

        if not timing_state.timing_artifact_id:
            new_art_id = str(uuid.uuid4())
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

        # [S7.1-FIX-06] THỰC THI ATOMIC MULTI-FILE TRANSACTION CỰC KỲ AN TOÀN
        try:
            srt_content = "\n".join(existing_lines)
            self._commit_transaction(artifact_path, srt_content, new_checkpoint)
        except Exception as e:
            self.error_signal.emit(f"Lỗi khi Commit Batch (Disk Error): {str(e)}")
            self.state_changed_signal.emit("FAILED", "Lỗi lưu đĩa. Dữ liệu cũ vẫn an toàn.")
            return

        if added_count > 0:
            self.batch_completed_signal.emit(added_count, timing_state.batch_size)
        if is_end_of_source:
            self.timing_finished_signal.emit()
            self.state_changed_signal.emit("COMPLETED", "Đã hoàn tất Timing toàn bộ Video!")
        else:
            self.state_changed_signal.emit("READY", f"Đã lưu Checkpoint (Đến câu {timing_state.completed_until}).")

    def _commit_transaction(self, srt_path, srt_content, checkpoint_obj):
        """[S7.1-FIX-06] Giao dịch 2 pha (Two-Phase Commit) cho 4 file cốt lõi"""
        project = self.project_service.current_project
        proj_dir = self.project_service.project_dir

        chk_path = os.path.join(proj_dir, "artifacts", "timing", "checkpoint.json")
        man_path = os.path.join(proj_dir, "artifacts", "manifest.json")
        state_path = os.path.join(proj_dir, "state.json")

        chk_data = json.dumps(asdict(checkpoint_obj), ensure_ascii=False, indent=2)
        man_data = json.dumps(self.project_service.artifact_store.to_dict(proj_dir), ensure_ascii=False, indent=2)
        state_dict = {
            "timing_status": project.state.timing_status,
            "text_status": project.state.text_status,
            "export_status": project.state.export_status,
            "active_artifact_id": project.state.active_artifact_id,
            "selected_segment_id": project.state.selected_segment_id,
            "dirty": False,
            "timing": asdict(project.state.timing)
        }
        state_data = json.dumps(state_dict, ensure_ascii=False, indent=2)

        # PHA 1: Viết ra RAM và ép xuống đĩa vật lý qua file tạm
        self._write_tmp_fsync(srt_path + ".tmp", srt_content)
        self._write_tmp_fsync(chk_path + ".tmp", chk_data)
        self._write_tmp_fsync(man_path + ".tmp", man_data)
        self._write_tmp_fsync(state_path + ".tmp", state_data)

        # PHA 2: Chuyển đổi trạng thái chớp nhoáng (Microsecond replace)
        os.replace(srt_path + ".tmp", srt_path)
        os.replace(chk_path + ".tmp", chk_path)
        os.replace(man_path + ".tmp", man_path)
        os.replace(state_path + ".tmp", state_path)

        project.state.dirty = False

    def _write_tmp_fsync(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

    def _read_draft_lines(self, path):
        if not os.path.exists(path): return []
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().splitlines()

    def _ms_to_time_str(self, ms: int) -> str:
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"