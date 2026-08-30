from typing import List, Dict, Any
from core.generation.generation_candidate import GenerationCandidate

class GenerationValidator:
    @staticmethod
    def validate(parsed_json: Dict[str, Any], target_segs: List[Dict], expected_request_id: str, response_request_id: str, model_id: str = None) -> List[GenerationCandidate]:
        # Preserve the four-argument API used by older callers. New callers
        # pass the response request id explicitly as the fourth argument.
        if model_id is None:
            model_id = response_request_id
            response_request_id = expected_request_id

        # BLOCKER 9 & 10 FIXED: Kiểm tra chéo Request ID từ AIResponse
        if expected_request_id != response_request_id:
            raise ValueError("SAI IDENTITY: Response nhận được không thuộc về Request hiện tại.")

        if not parsed_json or 'segments' not in parsed_json:
            raise ValueError("LỖI CẤU TRÚC: JSON không chứa mảng 'segments'.")

        generated_segments = parsed_json['segments']
        target_ids = [str(seg.get('id')) for seg in target_segs]
        generated_ids = [str(item.get('id')) for item in generated_segments]
        
        # BLOCKER 8 FIXED: Ép Ordering và Exact Identity tuyệt đối
        if generated_ids != target_ids:
            raise ValueError("SAI CẤU TRÚC ID: AI trả về EXTRA, MISSING, DUPLICATE hoặc sai thứ tự ID so với bản gốc.")

        candidates = []
        for i, seg in enumerate(target_segs):
            sid = target_ids[i]
            gen_text = generated_segments[i].get('text', '')

            if gen_text is None or not str(gen_text).strip():
                raise ValueError(f"CHUỖI RỖNG: AI trả về text rỗng cho câu {sid}.")

            candidates.append(GenerationCandidate(
                segment_id=sid,
                source_text=seg.get('text', ''),
                generated_text=gen_text,
                model_id=model_id,
                request_id=expected_request_id,
                confidence=1.0,
                validation_status="PASSED",
                validation_errors=[]
            ))
            
        return candidates
