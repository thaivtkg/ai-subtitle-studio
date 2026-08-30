from typing import List
from core.generation.generation_candidate import GenerationCandidate
from core.generation.generation_checkpoint import GenerationCheckpoint

class TextArtifactService:
    def __init__(self, project_service, data_provider):
        self.project_service = project_service
        self.data_provider = data_provider

    def commit_candidates(self, candidates: List[GenerationCandidate], checkpoint: GenerationCheckpoint) -> bool:
        project = self.project_service.current_project
        if not project:
            return False

        # 1. RÚT MÃ REVISION CỦA TIMELINE HIỆN TẠI
        art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(art_id)
        
        if not timing_artifact:
            raise RuntimeError("Không tìm thấy Timing Artifact.")

        # 2. KIỂM TRA BẢO MẬT (STALE GUARD)
        # Nếu Timeline bị chỉnh sửa (cắt, gộp, kéo giãn), revision sẽ nhảy số.
        if timing_artifact.revision != checkpoint.generation_revision:
            raise RuntimeError("STALE_TIMING: Dữ liệu Timeline đã bị thay đổi trong lúc AI đang sinh chữ. Đã hủy bản dịch này để bảo vệ dự án.")

        # 3. COMMIT DỮ LIỆU VÀO TIMELINE
        for candidate in candidates:
            if candidate.validation_status == "PASSED":
                seg = self.data_provider.get_segment(candidate.segment_id)
                if seg:
                    seg.text = candidate.generated_text
                    seg.status = "DRAFT" # Phân loại vòng đời: Chữ do AI điền luôn là DRAFT

        self.project_service.mark_dirty()
        return True