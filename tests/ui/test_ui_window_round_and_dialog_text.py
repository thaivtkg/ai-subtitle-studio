import pytest
from PySide6.QtWidgets import QApplication

from ui.dialogs.new_project_dialog import NewProjectDialog


def test_ac_text_01_browse_dir_button_width_not_clipped(qapp):
    """AC-TEXT-01: Nút duyệt thư mục không bị ép cứng 110px gây mất chữ cái 'C'"""
    dlg = NewProjectDialog()
    # Tìm nút Chọn Thư mục...
    btn_browse_dir = None
    for child in dlg.findChildren(object):
        if getattr(child, "text", None) and "Chọn Thư mục" in child.text():
            btn_browse_dir = child
            break

    assert btn_browse_dir is not None
    # Độ rộng tối thiểu >= 130px và không bị setFixedWidth 110
    assert btn_browse_dir.minimumWidth() >= 130 or btn_browse_dir.maximumWidth() > 110
    dlg.close()


def test_ac_round_01_window_corner_preference(qapp):
    """AC-ROUND-01: MainWindow có phương thức kích hoạt DWM bo tròn góc khi Normal"""
    from ui.Gui import MainWindow

    win = MainWindow()
    assert hasattr(win, "_apply_window_corner_preference")
    # Gọi không phát sinh ngoại lệ
    win._apply_window_corner_preference()
    win.close()
