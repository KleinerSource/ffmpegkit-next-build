import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BuildContractTest(unittest.TestCase):
    def test_only_public_c_headers_are_exposed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Makefile"
            path.write_text("HEADERS = avutil.h \\\n  frame.h \\\n  hwcontext_videotoolbox.h\nINTERNAL_HEADERS = cpu_internal.h\n", encoding="utf-8")
            self.assertEqual(build.public_headers(path, "libavutil"), ["avutil.h", "frame.h"])

    def test_official_pinned_sources(self):
        self.assertEqual(build.LOCK["sources"]["FFmpeg"]["git"], "https://github.com/FFmpeg/FFmpeg.git")
        self.assertEqual(build.LOCK["sources"]["FFmpegKitNext"]["git"], "https://github.com/arthenica/ffmpeg-kit-next.git")
        self.assertIn("--no-ffmpeg-kit-protocols", build.LOCK["options"])
        self.assertNotIn("latest", build.LOCK["release"])

    def test_missing_simulator_slice_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "libavutil.xcframework"
            path.mkdir()
            (path / "Info.plist").write_bytes(plistlib.dumps({"AvailableLibraries": [{
                "SupportedPlatform": "ios", "SupportedArchitectures": ["arm64"],
            }]}))
            with self.assertRaisesRegex(ValueError, "simulator"):
                build.validate_framework(path)


if __name__ == "__main__":
    unittest.main()
