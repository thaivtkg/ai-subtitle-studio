from typing import List, Dict, Any
from core.generation.generation_candidate import GenerationCandidate

class GenerationValidator:
    @staticmethod
    def validate(parsed_json: Dict[str, Any], target_segs: List[Dict], request_id: str, model_id: str) -> List[GenerationCandidate]:
        candidates = []
        if not parsed_json or 'segments' not in parsed_json:
            return candidates

        # Map dữ liệu JSON AI trả về theo ID để đối chiếu
        generated_items = {str(item.get('id')): item.get('text', '') for item in parsed_json['segments']}

        for seg in target_segs:
            sid = str(seg.get('id'))
            gen_text = generated_items.get(sid)
            
            errors = []
            status = "PASSED"
            
            if gen_text is None:
                errors.append("AI bỏ sót Segment ID này.")
                status = "FAILED"
            elif not str(gen_text).strip():
                errors.append("AI trả về chuỗi rỗng.")
                status = "FAILED"
                
            candidates.append(GenerationCandidate(
                segment_id=sid,
                source_text=seg.get('text', ''),
                generated_text=gen_text if gen_text else "",
                model_id=model_id,
                request_id=request_id,
                confidence=1.0,
                validation_status=status,
                validation_errors=errors
            ))
            
        return candidates