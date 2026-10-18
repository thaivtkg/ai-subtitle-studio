from typing import Dict, Any


class StylePresetResolver:
    """
    Quy đổi Style Preset (normal, loud, whisper) thành các thuộc tính trực quan
    (font_size, font_color, outline_width, bold, italic) dựa trên cấu hình global_style hiện tại.
    """

    @staticmethod
    def resolve_style(preset: str, global_style: Dict[str, Any]) -> Dict[str, Any]:
        """
        Quy tắc chuyển dịch:
        - loud: size * 1.20, màu vàng #FFE600, viền 3.5, bold True, italic False
        - whisper: size * 0.85, màu bạc #D0D0D0, viền 1.5, bold False, italic True
        - normal / mặc định: size gốc, màu trắng #FFFFFF, viền gốc (hoặc 2.0), bold False, italic False
        """
        base = dict(global_style or {})
        base_size = int(base.get("font_size", 20) or 20)
        font_name = base.get("font_name", "Segoe UI")

        preset_clean = (preset or "normal").lower().strip()

        if preset_clean == "loud":
            return {
                **base,
                "font_name": font_name,
                "font_size": int(round(base_size * 1.20)),
                "font_color": "#FFE600",
                "outline_width": 3.5,
                "bold": True,
                "italic": False,
            }
        elif preset_clean == "whisper":
            return {
                **base,
                "font_name": font_name,
                "font_size": int(round(base_size * 0.85)),
                "font_color": "#D0D0D0",
                "outline_width": 1.5,
                "bold": False,
                "italic": True,
            }
        else:  # normal or any other preset
            return {
                **base,
                "font_name": font_name,
                "font_size": base_size,
                "font_color": base.get("font_color", "#FFFFFF"),
                "outline_width": float(base.get("outline_width", 2.0) or 2.0),
                "bold": False,
                "italic": False,
            }
