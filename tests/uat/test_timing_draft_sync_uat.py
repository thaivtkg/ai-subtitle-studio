import pytest
from PySide6.QtWidgets import QApplication
from ui.Gui import MainWindow
from core.subtitle_generation.generation_service import SubtitleGenerationService
from tests.uat.conftest import MockProjectService, generate_fake_segments
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
import os
import copy

def test_timing_draft_sync_after_rollback(qapp, temp_project_dir):
    """
    Test that explicitly verifies the 'Timing Draft' state, 'Timeline Render State',
    and 'Table/Editor' are perfectly synchronized after a Rollback.
    """
    
    # Setup Mock properly
    project_service = MockProjectService(temp_project_dir)
    gui = MainWindow(project_service=project_service)
    
    gen_service = SubtitleGenerationService(gui.generation_panel, project_service)
    gui.generation_panel.generation_service = gen_service
    
    # Generate 100 segments (Initial Checkpoint)
    segments_100 = generate_fake_segments(100)
    gui.sub_editor.all_segments = copy.deepcopy(segments_100)
    gen_service.create_history_checkpoint(segments_100, is_initial=True)
    
    gui.timeline_data_provider.load_runtime_data(gui.sub_editor.all_segments, 3600000)
    gui.timeline_widget.load_project_data(3600000, gui.timeline_data_provider.get_all_segments(), None)
    gui.undo_manager.state_changed.emit()
    qapp.processEvents()
    
    assert len(gui.sub_editor.all_segments) == 100
    assert gui.sub_editor.table.rowCount() == 100
    assert len(gui.timeline_data_provider.get_all_segments()) == 100
    assert len(gui.timeline_widget.container.track.segments) == 100
    
    original_seg = dict(gui.sub_editor.all_segments[10])
    
    # Simulate an edit directly
    gui.sub_editor.all_segments[10]['start'] += 1000
    
    gui.timeline_data_provider.load_runtime_data(gui.sub_editor.all_segments, 3600000)
    gui.timeline_widget.load_project_data(3600000, gui.timeline_data_provider.get_all_segments(), None)
    qapp.processEvents()
    
    assert gui.sub_editor.all_segments[10]['start'] == original_seg['start'] + 1000
    assert gui.timeline_data_provider.get_all_segments()[10].start_ms == original_seg['start'] + 1000
    assert gui.timeline_widget.container.track.segments[10].start_ms == original_seg['start'] + 1000
    
    segments_130 = generate_fake_segments(130)
    gui.sub_editor.all_segments = copy.deepcopy(segments_130)
    gen_service.create_history_checkpoint(segments_130, is_initial=False)
    
    gui.timeline_data_provider.load_runtime_data(gui.sub_editor.all_segments, 3600000)
    gui.timeline_widget.load_project_data(3600000, gui.timeline_data_provider.get_all_segments(), None)
    gui.undo_manager.state_changed.emit()
    qapp.processEvents()
    
    assert len(gui.timeline_data_provider.get_all_segments()) == 130
    
    # ROLLBACK to initial state
    cp_initial = gen_service.initial_state
    gen_service.execute_rollback(0, gui.sub_editor.all_segments, gui.undo_manager, checkpoint_id=cp_initial.checkpoint_id)
    
    gui.sub_editor.render_page()
    gui.timeline_data_provider.load_runtime_data(gui.sub_editor.all_segments, 3600000)
    gui.timeline_widget.load_project_data(3600000, gui.timeline_data_provider.get_all_segments(), None)
    gui.undo_manager.state_changed.emit()
    qapp.processEvents()
    
    snapshot_data = cp_initial.segments_snapshot
    
    assert len(gui.sub_editor.all_segments) == 100
    assert gui.sub_editor.all_segments[10]['start'] == original_seg['start']
    assert snapshot_data[10]['start'] == original_seg['start']
    
    assert gui.sub_editor.table.rowCount() == 100
    
    timeline_draft_data = gui.timeline_data_provider.get_all_segments()
    assert len(timeline_draft_data) == 100
    assert timeline_draft_data[10].start_ms == original_seg['start']
    
    timeline_render_data = gui.timeline_widget.container.track.segments
    assert len(timeline_render_data) == 100
    assert timeline_render_data[10].start_ms == original_seg['start']
    
    gui.sub_editor.current_index = 10
    gui.sub_editor._load_current_editor()
    
    from ui.SubEditor import ms_to_time_str
    expected_start_str = ms_to_time_str(original_seg['start'])
    assert gui.sub_editor.inp_start.text() == expected_start_str
    
    print("ALL 5 LAYERS ARE SYNCED AFTER ROLLBACK!")
    
    gui.undo_manager.undo()
    gui.timeline_data_provider.load_runtime_data(gui.sub_editor.all_segments, 3600000)
    gui.timeline_widget.load_project_data(3600000, gui.timeline_data_provider.get_all_segments(), None)
    gui.undo_manager.state_changed.emit()
    qapp.processEvents()
    
    assert len(gui.sub_editor.all_segments) == 130
    assert len(gui.timeline_data_provider.get_all_segments()) == 130
    assert len(gui.timeline_widget.container.track.segments) == 130
    
    gui.undo_manager.redo()
    gui.timeline_data_provider.load_runtime_data(gui.sub_editor.all_segments, 3600000)
    gui.timeline_widget.load_project_data(3600000, gui.timeline_data_provider.get_all_segments(), None)
    gui.undo_manager.state_changed.emit()
    qapp.processEvents()
    
    assert len(gui.sub_editor.all_segments) == 100
    assert len(gui.timeline_data_provider.get_all_segments()) == 100
    assert len(gui.timeline_widget.container.track.segments) == 100
    
    print("Undo/Redo correctly propagates to Timing Draft and Timeline Render State.")
