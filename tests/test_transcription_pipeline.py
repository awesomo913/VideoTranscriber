import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import transcribe_video as tv


class TestTranscriptionPipeline(unittest.TestCase):
    def _make_media_file(self, root: Path, name: str = "clip.mp4") -> Path:
        media_path = root / name
        media_path.write_bytes(b"fake-media")
        return media_path

    def test_validate_media_path_checks_ffmpeg_and_audio_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            media_path = self._make_media_file(Path(tmp))

            with patch.object(tv, "check_ffmpeg", return_value=False):
                with self.assertRaises(EnvironmentError):
                    tv._validate_media_path(media_path)

            with patch.object(tv, "check_ffmpeg", return_value=True), patch.object(
                tv, "has_audio_stream", return_value=False
            ):
                with self.assertRaises(ValueError):
                    tv._validate_media_path(media_path)

            with patch.object(tv, "check_ffmpeg", return_value=True), patch.object(
                tv, "has_audio_stream", return_value=True
            ):
                tv._validate_media_path(media_path)

    def test_run_transcribe_attempt_calls_model_and_callbacks(self):
        input_path = Path("dummy.mp4")
        segments = [
            SimpleNamespace(start=0.0, end=0.2, text=" first "),
            SimpleNamespace(start=0.2, end=0.5, text=" second "),
        ]
        info = SimpleNamespace(duration=1.0, language="en")

        model = Mock()
        model.transcribe.return_value = (segments, info)

        on_segment_calls = []
        on_progress_calls = []

        returned_segments, returned_info = tv._run_transcribe_attempt(
            model,
            input_path,
            lambda count, text: on_segment_calls.append((count, text)),
            lambda current, total: on_progress_calls.append((current, total)),
        )

        model.transcribe.assert_called_once_with(
            str(input_path),
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        self.assertEqual(returned_segments, segments)
        self.assertIs(returned_info, info)
        self.assertEqual(on_segment_calls, [(1, "first"), (2, "second")])
        self.assertEqual(on_progress_calls, [(0.2, 1.0), (0.5, 1.0)])

    def test_transcribe_formats_very_short_clip_to_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media_path = self._make_media_file(root)
            output_dir = root / "out"

            segments = [SimpleNamespace(start=0.0, end=0.2, text=" hello ")]
            info = SimpleNamespace(duration=1.0, language="en")
            model = Mock()
            model.transcribe.return_value = (segments, info)

            with patch.object(tv, "_validate_media_path"), patch.object(
                tv, "_load_whisper", return_value=model
            ):
                out_path = tv.transcribe(media_path, timestamps=True, output_dir=output_dir)

            self.assertEqual(out_path.read_text(encoding="utf-8"), "[00:00:00] hello")

    def test_transcribe_silent_audio_writes_empty_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media_path = self._make_media_file(root)
            output_dir = root / "out"

            segments = [SimpleNamespace(start=0.0, end=1.0, text="   ")]
            info = SimpleNamespace(duration=1.0, language="en")
            model = Mock()
            model.transcribe.return_value = (segments, info)

            with patch.object(tv, "_validate_media_path"), patch.object(
                tv, "_load_whisper", return_value=model
            ):
                out_path = tv.transcribe(media_path, timestamps=True, output_dir=output_dir)

            self.assertEqual(out_path.read_text(encoding="utf-8"), "")

    def test_transcribe_model_failure_surfaces_handled_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            media_path = self._make_media_file(Path(tmp))

            with patch.object(tv, "_validate_media_path"), patch.object(
                tv, "_load_whisper", return_value=object()
            ), patch.object(
                tv,
                "_run_transcribe_attempt",
                side_effect=[(None, None), (None, None)],
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Transcription failed on both GPU and CPU"
                ):
                    tv.transcribe(media_path)

    def test_transcribe_batch_combined_output_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media_path = self._make_media_file(root)
            combined_path = root / "combined.txt"

            segment = SimpleNamespace(start=0.0, end=0.6, text=" batched line ")
            info = SimpleNamespace(duration=1.0, language="en")

            with patch.object(tv, "_whisper_model_class"), patch.object(
                tv, "_validate_media_path"
            ), patch.object(
                tv, "_load_whisper", return_value=object()
            ), patch.object(
                tv, "_run_transcribe_attempt", return_value=([segment], info)
            ):
                results = tv.transcribe_batch(
                    [media_path],
                    timestamps=False,
                    combined_path=combined_path,
                    write_individual_txts=False,
                )

            self.assertEqual(results, [(media_path, None)])
            combined_text = combined_path.read_text(encoding="utf-8")
            self.assertIn("Combined transcripts", combined_text)
            self.assertIn("File: clip.mp4", combined_text)
            self.assertIn("batched line", combined_text)


if __name__ == "__main__":
    unittest.main()
