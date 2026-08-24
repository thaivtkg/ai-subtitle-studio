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
            current_idx = self.ui.stack.currentIndex()
            # Ánh xạ ngược từ Stack Index về Original Index của Sidebar
            original_idx = current_idx + 1 if current_idx > 1 else current_idx
            page_map = {0: "dashboard", 1: "workspace", 2: "editor", 3: "queue", 4: "draft", 5: "export"}
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

        # 4. Phục hồi Video và vị trí thời gian (Tích hợp thông qua QueueManager)
        try:
            import os
            # [CRITICAL FIX] Chuẩn hóa đường dẫn để tránh lỗi khác biệt gạch chéo (\ và /) trên Windows
            video_path = os.path.normpath(project.source.path)
            
            if os.path.exists(video_path):
                if video_path not in self.ui.queue_mgr.get_items():
                    self.ui.queue_mgr.add_video(video_path)
                
                # --- [FIX SPRINT 7] QUÉT TÌM ARTIFACT TRONG TẤT CẢ THƯ MỤC CON ---
                artifacts_dir = os.path.join(self.project_service.project_dir, "artifacts")
                latest_artifact_path = None
                
                if os.path.exists(artifacts_dir):
                    valid_files = []
                    # Dùng os.walk để quét sâu vào TẤT CẢ các thư mục con (như subtitles/, ...)
                    for root, dirs, files in os.walk(artifacts_dir):
                        for f in files:
                            if f.endswith(('.srt', '.ai-subtitle-draft', '.vtt')):
                                valid_files.append(os.path.join(root, f))
                                
                    if valid_files:
                        # Lấy file mới nhất được tạo ra
                        valid_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                        latest_artifact_path = os.path.normpath(valid_files[0])
                        
                        # Bơm đường dẫn file vào Queue
                        self.ui.queue_mgr.set_srt_for_video(video_path, latest_artifact_path)
                        print(f"[DEBUG] Đã nạp Artifact vào Queue: {latest_artifact_path}")
                # ------------------------------------------------------------------

                # Kích hoạt UI qua Queue Manager
                self.ui.on_queue_item_clicked(video_path)
                
                # [CRITICAL FIX] Ép nạp thẳng vào Editor để đề phòng QueueManager lỡ nhịp (Mất Focus)
                if latest_artifact_path and os.path.exists(latest_artifact_path):
                    if latest_artifact_path.endswith('.ai-subtitle-draft'):
                        self.ui.sub_editor.load_draft_file(latest_artifact_path)
                    else:
                        self.ui.sub_editor.load_srt_file(latest_artifact_path)
                    
                    self.ui.video_player.sub_controller.load_srt(latest_artifact_path)
                    print("[DEBUG] Đã ÉP nạp Artifact trực tiếp vào Inline Editor thành công!")
                
                # Đợi 500ms để Video nạp xong metadata, sau đó Seek đến đúng thời gian
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