import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from transcribe_video import _validate_media_path, supported_formats_text


class ValidateMediaPathTests(unittest.TestCase):
    @patch("transcribe_video.has_audio_stream", return_value=True)
    @patch("transcribe_video.check_ffmpeg", return_value=True)
    def test_supported_file_passes_validation(self, _mock_ffmpeg, _mock_audio):
        with tempfile.TemporaryDirectory() as tmpdir:
            media = Path(tmpdir) / "clip.mp3"
            media.write_bytes(b"not-empty")
            _validate_media_path(media)

    def test_missing_file_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.mp3"
            with self.assertRaises(FileNotFoundError):
                _validate_media_path(missing)

    def test_empty_file_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media = Path(tmpdir) / "empty.wav"
            media.touch()
            with self.assertRaisesRegex(ValueError, "File is empty"):
                _validate_media_path(media)

    def test_unsupported_file_fails_with_supported_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media = Path(tmpdir) / "notes.txt"
            media.write_text("hello", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Supported formats"):
                _validate_media_path(media)
            self.assertIn(".mp3", supported_formats_text())


if __name__ == "__main__":
    unittest.main()
