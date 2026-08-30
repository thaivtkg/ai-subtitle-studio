import json
import re
from typing import Optional, Dict, Any

class OutputParser:
    @staticmethod
    def extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
        # Tìm block JSON nằm trong cặp ```json ... ```
        json_match = re.search(r"```(?:json)?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
        content = json_match.group(1).strip() if json_match else raw_text.strip()
        
        # Lọc bỏ text rác có thể dính trước dấu { hoặc sau dấu }
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            clean_json_str = content[start_idx:end_idx+1]
            try:
                return json.loads(clean_json_str)
            except json.JSONDecodeError:
                return None
        return None