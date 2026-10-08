import copy
from typing import List, Dict, Optional
import time

class GenerationCheckpoint:
    """
    Represents a full snapshot of the subtitle generation state at a specific milestone.
    """
    def __init__(
        self,
        checkpoint_id: str,
        project_id: str,
        source_fingerprint: str,
        generated_count: int,
        segments_snapshot: List[Dict],
        generation_range: Optional[Dict] = None,
        generation_request_id: Optional[str] = None,
        model_settings: Optional[Dict] = None,
    ):
        self.checkpoint_id = checkpoint_id
        self.project_id = project_id
        self.source_fingerprint = source_fingerprint
        self.created_at = time.time()
        
        self.generated_count = generated_count
        # Deep copy to ensure this snapshot is completely isolated from live edits
        self.segments_snapshot = copy.deepcopy(segments_snapshot)
        
        self.generation_range = generation_range
        self.generation_request_id = generation_request_id
        self.model_settings = model_settings or {}

    def has_manual_edits_compared_to(self, current_segments: List[Dict]) -> bool:
        """
        Detects if current_segments have manual edits compared to this checkpoint's snapshot.
        """
        if len(current_segments) != len(self.segments_snapshot):
            return True
            
        for cur, snap in zip(current_segments, self.segments_snapshot):
            # Check source tag if available
            if cur.get("source") == "manual" and snap.get("source") != "manual":
                return True
            # Structural diff
            if cur.get("start") != snap.get("start") or cur.get("end") != snap.get("end") or cur.get("text") != snap.get("text"):
                return True
                
        return False
