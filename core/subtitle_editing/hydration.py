def _get_ms(seg, key):
    # Try start_ms/end_ms first, then start/end
    val = seg.get(f"{key}_ms")
    if val is not None:
        return int(val)
    val = seg.get(key)
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str) and ":" in val:
        # Fallback parse string "00:00:00,000" if necessary, but assume ms for now
        # SubEditor has a helper for this, but we'll try to keep it simple.
        try:
            import re
            match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", val.strip())
            if match:
                h, m, s, ms = map(int, match.groups())
                return ((h * 60 + m) * 60 + s) * 1000 + ms
        except:
            pass
    return 0


def hydrate_original_text(current_segments: list, shadow_segments: list, tolerance_ms: int = 100) -> list:
    """
    Hydrates the `original_text` of current_segments based on shadow_segments.
    Matches by timestamp to prevent 1-to-N poisoning from previous split/merge actions.
    
    Match conditions:
    1. Exact Match: abs(cur.start - shadow.start) <= tolerance AND abs(cur.end - shadow.end) <= tolerance
    2. Inside Match (Split): shadow.start - tolerance <= cur.start AND shadow.end + tolerance >= cur.end
    
    If no match, sets original_text = "[Unknown Source]".
    """
    for cur in current_segments:
        cur_start = _get_ms(cur, "start")
        cur_end = _get_ms(cur, "end")
        
        # If it already has a valid original text, don't overwrite
        orig = cur.get("original_text", "").strip()
        if orig and orig != "[Unknown Source]":
            continue
            
        matched_text = "[Unknown Source]"
        
        # Look for a match in shadow
        for shadow in shadow_segments:
            s_start = _get_ms(shadow, "start")
            s_end = _get_ms(shadow, "end")
            
            is_exact = abs(cur_start - s_start) <= tolerance_ms and abs(cur_end - s_end) <= tolerance_ms
            is_inside = (s_start - tolerance_ms) <= cur_start and (s_end + tolerance_ms) >= cur_end
            
            if is_exact or is_inside:
                matched_text = shadow.get("text", "[Unknown Source]")
                break
                
        cur["original_text"] = matched_text
        
    return current_segments
