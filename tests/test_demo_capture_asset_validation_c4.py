import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureTarget,
    HoldAction,
    OutputFormat,
    OutputSpec,
)
from core.demo_capture.registry import DemoScenarioRegistry
from core.demo_capture.validation import AssetValidationPolicy, TutorialAssetValidator


def write_png(path, size=(4, 3)):
    Image.new("RGBA", size, (10, 20, 30, 255)).save(path, format="PNG")


def write_gif(path, sizes=((4, 3), (4, 3)), durations=(100, 100), optimize=False):
    colors = ((255, 0, 0), (0, 0, 255), (0, 255, 0))
    frames = [Image.new("RGBA", size, color + (255,)) for size, color in zip(sizes, colors)]
    frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=optimize,
    )


class TestTutorialAssetValidatorC4(unittest.TestCase):
    def test_tc220_valid_png_decodes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.png"
            write_png(path)
            TutorialAssetValidator().validate_file(path, OutputSpec("asset.png", OutputFormat.PNG))

    def test_tc221_valid_gif_decodes_and_obeys_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.gif"
            write_gif(path)
            TutorialAssetValidator().validate_file(path, OutputSpec("asset.gif", OutputFormat.GIF))

    def test_tc221_delta_frames_inside_canvas_are_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "delta.gif"
            write_gif(path, sizes=((100, 100), (90, 90)), optimize=True)
            TutorialAssetValidator().validate_file(path, OutputSpec("delta.gif", OutputFormat.GIF))

    def test_tc222_extension_magic_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.png"
            write_gif(path)
            with self.assertRaises(CaptureRunError):
                TutorialAssetValidator().validate_file(path, OutputSpec("asset.png", OutputFormat.PNG))

    def test_tc223_corrupt_asset_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\ncorrupt")
            with self.assertRaises(CaptureRunError):
                TutorialAssetValidator().validate_file(path, OutputSpec("asset.png", OutputFormat.PNG))

    def test_tc224_each_limit_is_enforced(self):
        cases = (
            ("max_width", 3, (4, 3), "asset.png"),
            ("max_height", 2, (4, 3), "asset.png"),
            ("max_pixels", 11, (4, 3), "asset.png"),
            ("max_png_bytes", 1, (4, 3), "asset.png"),
            ("max_gif_frames", 1, ((4, 3), (4, 3)), "asset.gif"),
            ("max_gif_duration_ms", 100, ((4, 3), (4, 3)), "asset.gif"),
        )
        for field, limit, size, filename in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / filename
                if filename.endswith(".png"):
                    write_png(path, size)
                    output = OutputSpec(filename, OutputFormat.PNG)
                else:
                    write_gif(path, size)
                    output = OutputSpec(filename, OutputFormat.GIF)
                policy = AssetValidationPolicy(**{field: limit})
                with self.assertRaises(CaptureRunError):
                    TutorialAssetValidator(policy).validate_file(path, output)

    def test_tc225_gif_frame_dimensions_must_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.gif"
            write_gif(path, sizes=((100, 100), (100, 100)))
            data = bytearray(path.read_bytes())
            image_descriptors = [index for index, value in enumerate(data) if value == 0x2C]
            second_descriptor = image_descriptors[1]
            data[second_descriptor + 5:second_descriptor + 7] = (105).to_bytes(2, "little")
            data[second_descriptor + 7:second_descriptor + 9] = (105).to_bytes(2, "little")
            path.write_bytes(data)
            with self.assertRaises(CaptureRunError):
                TutorialAssetValidator().validate_file(path, OutputSpec("asset.gif", OutputFormat.GIF))

    def test_tc226_registry_asset_must_exist(self):
        scenario = CaptureScenario(
            id="demo",
            target=CaptureTarget("anchor"),
            profile=CaptureProfile(),
            actions=(HoldAction(10),),
            output=OutputSpec("missing.png", OutputFormat.PNG),
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CaptureRunError) as error:
                TutorialAssetValidator().validate_registry_assets(
                    DemoScenarioRegistry((scenario,)), Path(directory)
                )
            self.assertEqual(error.exception.error_code, CaptureErrorCode.ASSET_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
