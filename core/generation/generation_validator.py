from typing import List, Dict, Any
from core.generation.generation_candidate import GenerationCandidate

class GenerationValidator:
    @staticmethod
    def validate(parsed_json: Dict[str, Any], target_segs: List[Dict], request_id: str, model_id: str) -> List[GenerationCandidate]:
        candidates = []
        if not parsed_json or 'segments' not in parsed_json:
            raise ValueError("LỖI CẤU TRÚC: JSON không chứa mảng 'segments'.")

        generated_segments = parsed_json['segments']
        target_ids = [str(seg.get('id')) for seg in target_segs]
        
        # 1. Khớp số lượng chính xác
        if len(generated_segments) != len(target_ids):
            raise ValueError(f"AI TRẢ SAI SỐ LƯỢNG: Yêu cầu {len(target_ids)} câu, nhận được {len(generated_segments)} câu.")

        # 2. Quét Duplicate và Extra IDs
        generated_ids = []
        generated_dict = {}
        for item in generated_segments:
            gid = str(item.get('id'))
            if gid in generated_ids:
                raise ValueError(f"TRÙNG LẶP ID: AI trả về ID {gid} nhiều lần.")
            if gid not in target_ids:
                raise ValueError(f"ID LẠ (EXTRA): AI tự chế thêm ID {gid} không có trong bản gốc.")
            generated_ids.append(gid)
            generated_dict[gid] = item.get('text', '')

        # 3. Quét Missing và Ép Ordering
        for seg in target_segs:
            sid = str(seg.get('id'))
            if sid not in generated_ids:
                raise ValueError(f"THIẾU ID: AI bỏ sót không dịch câu {sid}.")
                
            gen_text = generated_dict.get(sid)
            if gen_text is None or not str(gen_text).strip():
                raise ValueError(f"CHUỖI RỖNG: AI trả về text rỗng cho câu {sid}.")

            candidates.append(GenerationCandidate(
                segment_id=sid,
                source_text=seg.get('text', ''),
                generated_text=gen_text,
                model_id=model_id,
                request_id=request_id,
                confidence=1.0,
                validation_status="PASSED",
                validation_errors=[]
            ))
            
        return candidates