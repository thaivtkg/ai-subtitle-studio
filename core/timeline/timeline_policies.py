class TextMergePolicy:
    """Chính sách nối chuỗi thông minh khi Merge Segments"""
    
    @staticmethod
    def execute(segments_text: list[str]) -> str:
        if not segments_text:
            return ""
            
        merged_text = segments_text[0].strip()
        
        for next_text in segments_text[1:]:
            next_text = next_text.strip()
            if not next_text:
                continue
                
            if not merged_text:
                merged_text = next_text
                continue
                
            # Kiểm tra ký tự cuối cùng của đoạn trước
            last_char = merged_text[-1]
            
            # Nếu kết thúc bằng dấu chấm câu kết thúc câu, thêm khoảng trắng
            if last_char in ('.', '!', '?', ',', ':', ';'):
                merged_text += " " + next_text
            # Nếu kết thúc bằng chữ cái hoặc số, thêm khoảng trắng
            elif last_char.isalnum():
                merged_text += " " + next_text
            else:
                # Fallback an toàn (có thể mở rộng cho ngôn ngữ CJK không dùng space sau này)
                merged_text += " " + next_text
                
        return merged_text.replace("  ", " ").strip()