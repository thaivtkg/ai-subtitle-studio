from typing import List, Dict

class PromptBuilder:
    @staticmethod
    def build_context_prompt(previous_segs: List[Dict], target_segs: List[Dict], next_segs: List[Dict], task_instruction: str) -> str:
        prompt = f"{task_instruction}\n\n"
        
        if previous_segs:
            prompt += "--- CONTEXT BEFORE ---\n"
            for s in previous_segs:
                prompt += f"[{s.get('start', '')} - {s.get('end', '')}]: {s.get('text', '')}\n"
                
        prompt += "\n--- TARGET SEGMENTS (YOU MUST PROCESS THESE) ---\n"
        for s in target_segs:
            prompt += f"ID: {s.get('id')} | [{s.get('start', '')} - {s.get('end', '')}]: {s.get('text', '')}\n"
            
        if next_segs:
            prompt += "\n--- CONTEXT AFTER ---\n"
            for s in next_segs:
                prompt += f"[{s.get('start', '')} - {s.get('end', '')}]: {s.get('text', '')}\n"
                
        prompt += """
\n--- OUTPUT FORMAT ---
You MUST return ONLY a valid JSON object matching this schema exactly. No conversational text.
{
  "segments": [
    {
      "id": "<segment_id_from_target>",
      "text": "<generated_text>"
    }
  ]
}
"""
        return prompt.strip()