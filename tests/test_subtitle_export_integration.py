import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _FakeStdout:
    def __iter__(self):
        return iter(())

    def close(self):
        return None


class _FakeProcess:
    def __init__(self, returncode):
        self.returncode = returncode
        self.stdout = _FakeStdout()

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self):
        return self.returncode


class TestSubtitleExportIntegrationContracts(unittest.TestCase):
    def _burn_hardsub(self):
        with patch.dict(sys.modules, {"torch": types.ModuleType("torch")}):
            from core.Backend import burn_hardsub
        return burn_hardsub

    def _paths(self, temp_dir):
        video = Path(temp_dir) / "video.mp4"
        srt = Path(temp_dir) / "source.srt"
        output = Path(temp_dir) / "rendered.mp4"
        video.write_bytes(b"video")
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\nline one\nline two\n",
            encoding="utf-8",
        )
        return str(video), str(srt), str(output)

    def test_bottom_export_keeps_existing_srt_force_style_path(self):
        from core.subtitle_placement import SubtitlePlacementState
        burn_hardsub = self._burn_hardsub()

        with tempfile.TemporaryDirectory() as temp_dir:
            video, srt, output = self._paths(temp_dir)
            process = _FakeProcess(0)
            with patch("core.runtime.runtime_paths.RuntimePaths.get_ffmpeg_exe", return_value="ffmpeg"), \
                    patch("subprocess.Popen", return_value=process) as popen:
                try:
                    burn_hardsub(
                        video,
                        srt,
                        output,
                        placement_state=SubtitlePlacementState(mode="bottom"),
                        video_resolution=(1920, 1080),
                    )
                except TypeError as exc:
                    self.fail(f"production hardsub placement API is missing: {exc}")

            command = popen.call_args.args[0]
            video_filter = command[command.index("-vf") + 1]
            self.assertIn("source.srt", video_filter)
            self.assertIn("force_style=", video_filter)
            self.assertNotIn(".ass", video_filter)

    def test_custom_export_reaches_production_hardsub_as_positioned_ass(self):
        from core import subtitle_ass
        from core.subtitle_placement import SubtitlePlacementState
        burn_hardsub = self._burn_hardsub()

        with tempfile.TemporaryDirectory() as temp_dir:
            video, srt, output = self._paths(temp_dir)
            process = _FakeProcess(0)
            created_ass = []
            real_temporary_ass_file = subtitle_ass.temporary_ass_file

            def capture_ass(text):
                holder = real_temporary_ass_file(text)
                created_ass.append(Path(holder.path).read_text(encoding="utf-8"))
                return holder

            with patch("core.runtime.runtime_paths.RuntimePaths.get_ffmpeg_exe", return_value="ffmpeg"), \
                    patch("subprocess.Popen", return_value=process) as popen, \
                    patch("core.subtitle_ass.temporary_ass_file", side_effect=capture_ass):
                try:
                    burn_hardsub(
                        video,
                        srt,
                        output,
                        placement_state=SubtitlePlacementState(mode="custom", x=0.25, y=0.75),
                        video_resolution=(1920, 1080),
                    )
                except TypeError as exc:
                    self.fail(f"production custom hardsub API is missing: {exc}")

            command = popen.call_args.args[0]
            video_filter = command[command.index("-vf") + 1]
            self.assertIn(".ass", video_filter)
            self.assertTrue(created_ass)
            self.assertIn(r"\an5\pos(480,810)", created_ass[0])
            self.assertIn("hello", created_ass[0])
            self.assertIn("line one", created_ass[0])
            self.assertIn("line two", created_ass[0])

    def test_export_uses_project_placement_state_at_worker_boundary(self):
        from core.project.project_state import ProjectState
        from core.subtitle_placement import SubtitlePlacementState
        from workers.TaskQueue import HardsubWorker

        project_state = ProjectState(
            subtitle_placement=SubtitlePlacementState(mode="custom", x=0.25, y=0.75)
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            video, srt, output = self._paths(temp_dir)
            try:
                worker = HardsubWorker(
                    video,
                    srt,
                    temp_dir,
                    42,
                    "white",
                    "Arial",
                    project_state=project_state,
                )
            except TypeError as exc:
                self.fail(f"hardsub worker has no project placement boundary: {exc}")

            errors = []
            worker.error_signal.connect(errors.append)
            with patch.dict(sys.modules, {"torch": types.ModuleType("torch")}), \
                    patch("workers.TaskQueue.psutil.cpu_percent", return_value=0.0), \
                    patch("workers.TaskQueue.get_video_duration", return_value=1.0), \
                    patch("workers.TaskQueue.OutputPathService.build_hardsub_path", return_value=output), \
                    patch("core.Backend.burn_hardsub") as burn:
                worker.run()

            self.assertEqual(errors, [])
            burn.assert_called_once()
            kwargs = burn.call_args.kwargs
            self.assertEqual(kwargs["video_path"], video.replace("\\", "/"))
            self.assertEqual(kwargs["srt_path"], srt.replace("\\", "/"))
            self.assertEqual(kwargs["output_path"], output.replace("\\", "/"))
            self.assertIs(kwargs["placement_state"], project_state.subtitle_placement)

    def test_custom_export_cleans_ass_through_success_failure_and_cancel(self):
        from core import subtitle_ass
        from core.subtitle_placement import SubtitlePlacementState
        burn_hardsub = self._burn_hardsub()

        with tempfile.TemporaryDirectory() as temp_dir:
            video, srt, output = self._paths(temp_dir)
            for outcome, returncode in (("success", 0), ("failure", 1), ("cancel", -15)):
                with self.subTest(outcome=outcome):
                    created_ass = []
                    real_temporary_ass_file = subtitle_ass.temporary_ass_file

                    def capture_ass(text):
                        holder = real_temporary_ass_file(text)
                        created_ass.append(Path(holder.path))
                        return holder

                    process = _FakeProcess(returncode)
                    with patch("core.runtime.runtime_paths.RuntimePaths.get_ffmpeg_exe", return_value="ffmpeg"), \
                            patch("subprocess.Popen", return_value=process), \
                            patch("core.subtitle_ass.temporary_ass_file", side_effect=capture_ass):
                        try:
                            if outcome == "failure":
                                try:
                                    burn_hardsub(
                                        video,
                                        srt,
                                        output,
                                        placement_state=SubtitlePlacementState(mode="custom", x=0.25, y=0.75),
                                        video_resolution=(1920, 1080),
                                    )
                                except TypeError as exc:
                                    self.fail(f"production custom hardsub API is missing: {exc}")
                                except Exception:
                                    pass
                                else:
                                    self.fail("FFmpeg failure was not propagated")
                            else:
                                burn_hardsub(
                                    video,
                                    srt,
                                    output,
                                    placement_state=SubtitlePlacementState(mode="custom", x=0.25, y=0.75),
                                    video_resolution=(1920, 1080),
                                )
                        except TypeError as exc:
                            self.fail(f"production custom hardsub API is missing: {exc}")

                    self.assertTrue(created_ass)
                    self.assertTrue(all(not path.exists() for path in created_ass))


if __name__ == "__main__":
    unittest.main()
