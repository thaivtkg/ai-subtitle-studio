from core.services.project_service import ProjectService
from PySide6.QtCore import QTimer

class WorkspaceService:
    """Service chịu trách nhiệm đồng bộ giữa Giao diện (Qt UI) và Trạng thái Dự án (Project State)"""
    
    def __init__(self, main_window, project_service: ProjectService):
        self.ui = main_window  # Tham chiếu đến class MainWindow (Gui.py)
        self.project_service = project_service

    def capture_workspace(self) -> None:
        """Thu thập (chụp) trạng thái hiện tại của UI và đẩy vào ProjectState"""
        project = self.project_service.current_project
        if not project:
            return

        workspace = project.state.workspace

        # 1. Chụp trang hiện tại trên Sidebar (Dashboard, Workspace, Export...)
        try:
            # [FIX SPRINT 7.1] Tránh dùng .currentIndex() của AnimatedStack 
            original_idx = getattr(self.ui, '_active_nav_index', 0)
            page_map = {0: "dashboard", 1: "workspace", 2: "editor", 3: "queue", 4: "draft", 5: "export", 6: "settings"}
            workspace.active_page = page_map.get(original_idx, "dashboard")
        except Exception as e:
            print(f"Lỗi capture trang: {e}")

        # 2. Chụp Tab hiện tại (Inline Editor, AI Generation, Live Log)
        try:
            if hasattr(self.ui, 'bottom_tabs'):
                tab_idx = self.ui.bottom_tabs.currentIndex()
                tab_map = {0: "inline_editor", 1: "ai_generation", 2: "live_log"}
                workspace.active_tab = tab_map.get(tab_idx, "inline_editor")
        except Exception as e:
            print(f"Lỗi capture tab: {e}")

        # 3. Chụp vị trí thanh thời gian của Video Player
        try:
            if hasattr(self.ui, 'video_player') and self.ui.video_player.player:
                workspace.playback_position_ms = self.ui.video_player.player.position()
        except Exception as e:
            print(f"Lỗi capture thời gian: {e}")

        # 4. Chụp trạng thái Bật/Tắt hiển thị Phụ đề (Preview)
        try:
            if hasattr(self.ui, 'video_player') and hasattr(self.ui.video_player, 'sub_controller'):
                workspace.subtitle_preview_enabled = getattr(self.ui.video_player.sub_controller, 'is_enabled', True)
        except Exception as e:
            print(f"Lỗi capture subtitle toggle: {e}")


    def restore_workspace(self) -> None:
        """Phục hồi giao diện (UI) dựa trên dữ liệu từ ProjectState"""
        project = self.project_service.current_project
        if not project:
            return

        workspace = project.state.workspace

        # 1. Phục hồi trang trên Sidebar (Sử dụng đúng hàm switch_page của Gui.py)
        try:
            page_map = {"dashboard": 0, "workspace": 1, "editor": 2, "queue": 3, "draft": 4, "export": 5}
            target_idx = page_map.get(workspace.active_page, 0)
            self.ui.switch_page(target_idx)
        except Exception as e:
            print(f"Lỗi khi khôi phục trang: {e}")

        # 2. Phục hồi Tab dưới đáy (AI Generation / Inline Editor)
        try:
            if hasattr(self.ui, 'bottom_tabs'):
                tab_map = {"inline_editor": 0, "ai_generation": 1, "live_log": 2}
                self.ui.bottom_tabs.setCurrentIndex(tab_map.get(workspace.active_tab, 0))
        except Exception as e:
            print(f"Lỗi khi khôi phục Tab: {e}")

        # 3. Phục hồi trạng thái hiển thị phụ đề (Chỉ can thiệp logic Core)
        try:
            if hasattr(self.ui, 'video_player') and hasattr(self.ui.video_player, 'sub_controller'):
                self.ui.video_player.sub_controller.is_enabled = workspace.subtitle_preview_enabled
                # Ép làm mới giao diện Video
                if not workspace.subtitle_preview_enabled:
                    self.ui.video_player.subtitle_overlay.clear_subtitle()
        except Exception as e:
            print(f"Lỗi khi khôi phục Preview Subtitle: {e}")

        # 4. Phục hồi Video và nạp Artifact qua ID (Tích hợp thông qua QueueManager)
        try:
            import os
            video_path = os.path.normpath(project.source.path)
            
            if os.path.exists(video_path):
                if video_path not in self.ui.queue_mgr.get_items():
                    self.ui.queue_mgr.add_video(video_path)
                
                # --- [S7-FIX-03] TRUY VẤN ARTIFACT TỪ KHO BẰNG ID, KHÔNG QUÉT ĐĨA ---
                active_art_id = project.state.active_artifact_id
                target_artifact_path = None
                
                if active_art_id:
                    artifact = self.project_service.artifact_store.get(active_art_id)
                    if artifact and os.path.exists(artifact.path):
                        target_artifact_path = os.path.normpath(artifact.path)
                        self.ui.queue_mgr.set_srt_for_video(video_path, target_artifact_path)
                        print(f"[DEBUG] Đã resolve Artifact ID {active_art_id} -> {target_artifact_path}")
                    else:
                        print(f"[WARN] Artifact ID '{active_art_id}' không tìm thấy trên ổ đĩa!")
                # ------------------------------------------------------------------

                # Kích hoạt UI qua Queue Manager
                self.ui.on_queue_item_clicked(video_path)
                
                # Ép nạp thẳng vào Editor
                if target_artifact_path:
                    if target_artifact_path.endswith('.ai-subtitle-draft'):
                        self.ui.sub_editor.load_draft_file(target_artifact_path)
                    else:
                        self.ui.sub_editor.load_srt_file(target_artifact_path)
                    
                    self.ui.video_player.sub_controller.load_srt(target_artifact_path)
                    print("[DEBUG] Đã ÉP nạp Artifact trực tiếp vào Inline Editor thành công!")
                
                # Seek video mượt mà
                from PySide6.QtCore import QTimer
                QTimer.singleShot(500, lambda: self._apply_video_position(workspace.playback_position_ms))
            else:
                print(f"Không tìm thấy file video gốc: {video_path}")
        except Exception as e:
            print(f"Lỗi khi khôi phục Video: {e}")

    def _apply_video_position(self, position_ms: int):
        """Hàm phụ trợ để Seek video mượt mà sau khi load"""
        if hasattr(self.ui, 'video_player') and self.ui.video_player.player:
            self.ui.video_player.set_position(position_ms)
            self.ui.video_player.position_changed(position_ms) # Ép update frame