import re

with open('ui/SubEditor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Using regex to find the block
old_block = r"""            row = self\._get_row_by_id\(seg_id\)
            if row >= 0:
                abs_idx = self\._get_absolute_index\(row\)
                if abs_idx >= 0:
                    self\.all_segments\[abs_idx\]\["start"\] = ms_to_time_str\(new_start_ms\)
                    self\.all_segments\[abs_idx\]\["end"\] = ms_to_time_str\(new_end_ms\)
                self\._set_table_item\(row, self\.COL_START, ms_to_time_str\(new_start_ms\)\)
                self\._set_table_item\(row, self\.COL_END, ms_to_time_str\(new_end_ms\)\)
                dur_ms = max\(0, new_end_ms - new_start_ms\)
                self\._set_table_item\(row, self\.COL_DUR, f"\{dur_ms / 1000:\.3f\} s"\)"""

new_block = """            abs_idx = -1
            for i, seg in enumerate(self.all_segments):
                if seg.get("id") == seg_id:
                    abs_idx = i
                    break
            
            if abs_idx >= 0:
                self.all_segments[abs_idx]["start"] = ms_to_time_str(new_start_ms)
                self.all_segments[abs_idx]["end"] = ms_to_time_str(new_end_ms)
                
                page = abs_idx // self.group_size if self.group_size > 0 else 0
                if self.group_size == 0 or page == self.current_page:
                    row = abs_idx % self.group_size if self.group_size > 0 else abs_idx
                    self._set_table_item(row, self.COL_START, ms_to_time_str(new_start_ms))
                    self._set_table_item(row, self.COL_END, ms_to_time_str(new_end_ms))
                    dur_ms = max(0, new_end_ms - new_start_ms)
                    self._set_table_item(row, self.COL_DUR, f"{dur_ms / 1000:.3f} s")"""

new_content = re.sub(old_block, new_block, content)

if new_content != content:
    with open('ui/SubEditor.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Fixed _get_absolute_index bug!')
else:
    print('Could not find the block to replace')
