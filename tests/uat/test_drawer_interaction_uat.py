import pytest
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ui.Gui import MainWindow
from tests.uat.conftest import MockProjectService

@pytest.fixture
def gui_app(qapp, tmp_path):
    project_service = MockProjectService(str(tmp_path))
    window = MainWindow(project_service=project_service)
    window.resize(1000, 600)
    window.show()
    # Let event loop process the show event
    QTest.qWait(100)
    return window

def test_drawer_interaction_and_z_order(gui_app):
    window = gui_app
    
    # 1. Open Drawer
    window._toggle_ai_drawer()
    
    # Wait for animation
    QTest.qWait(500)
    
    assert window.overlay_host.isVisible()
    assert window.generation_drawer.pos().x() < window.width() - 50
    
    drawer = window.generation_drawer
    nav_list = drawer.findChild(object, "NavRail")
    dock_tabs = window.dock_tabs # QStackedWidget
    
    assert nav_list is not None
    assert dock_tabs is not None
    
    # 2. Click through tabs
    # Click Context (index 1)
    context_item_rect = nav_list.visualItemRect(nav_list.item(1))
    QTest.mouseClick(nav_list.viewport(), Qt.LeftButton, pos=context_item_rect.center())
    QTest.qWait(100)
    assert dock_tabs.currentIndex() == 1
    
    # Click Style (index 2)
    style_item_rect = nav_list.visualItemRect(nav_list.item(2))
    QTest.mouseClick(nav_list.viewport(), Qt.LeftButton, pos=style_item_rect.center())
    QTest.qWait(100)
    assert dock_tabs.currentIndex() == 2
    
    # Click Quality (index 3)
    quality_item_rect = nav_list.visualItemRect(nav_list.item(3))
    QTest.mouseClick(nav_list.viewport(), Qt.LeftButton, pos=quality_item_rect.center())
    QTest.qWait(100)
    assert dock_tabs.currentIndex() == 3
    
    # Click Log (index 4)
    log_item_rect = nav_list.visualItemRect(nav_list.item(4))
    QTest.mouseClick(nav_list.viewport(), Qt.LeftButton, pos=log_item_rect.center())
    QTest.qWait(100)
    assert dock_tabs.currentIndex() == 4
    
    # 3. Test Combobox interaction (in Style tab)
    # Go back to style tab
    QTest.mouseClick(nav_list.viewport(), Qt.LeftButton, pos=style_item_rect.center())
    QTest.qWait(100)
    assert dock_tabs.currentIndex() == 2
    
    style_page = window.page_settings
    assert style_page is not None
    combo = style_page.motion_preset_combo
    # Simulate combobox click/change - just set index programmatically since combobox popup is hard to QTest
    combo.setCurrentIndex(1)
    assert combo.currentIndex() == 1
    
    # 4. Click inside drawer should NOT close it
    # We click on the drawer surface
    QTest.mouseClick(drawer, Qt.LeftButton, pos=QPoint(50, 50))
    QTest.qWait(100)
    assert window.overlay_host.isVisible()
    assert window.generation_drawer.pos().x() < window.width() - 50
    
    # 5. Click outside drawer (on the scrim) SHOULD close it
    # Scrim is OverlayHost. Click at x=50, y=50 which is outside the drawer
    QTest.mouseClick(window.overlay_host, Qt.LeftButton, pos=QPoint(50, 50))
    
    QTest.qWait(500)
    assert not window.overlay_host.isVisible()
