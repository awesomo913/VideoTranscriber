"""Tests for _validate_media_path, transcribe(), and transcribe_batch().

The Whisper model is always mocked via FakeWhisperModel (see conftest.py) —
no real model is loaded and nothing is downloaded.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import transcribe_video as tv


def _touch(path: Path, content: bytes = b"\x00") -> Path:
    path.write_bytes(content)
    return path


@pytest.fixture
def patch_has_audio(monkeypatch):
    """Default: every file 'has audio' unless a test overrides this."""
    monkeypatch.setattr(tv, "has_audio_stream", lambda p: True)


@pytest.fixture
def patch_model_loader(monkeypatch, fake_whisper_model):
    def _load(model_name, device, compute):
        return fake_whisper_model(model_name, device, compute)

    monkeypatch.setattr(tv, "_load_whisper", _load)
    return fake_whisper_model


class TestValidateMediaPath:
    def test_rejects_unsupported_extension(self, tmp_path):
        f = _touch(tmp_path / "song.xyz")
        with pytest.raises(ValueError, match="Unsupported format"):
            tv._validate_media_path(f)

    def test_rejects_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tv._validate_media_path(tmp_path / "ghost.mp4")

    def test_rejects_file_with_no_audio_stream(self, tmp_path, monkeypatch):
        f = _touch(tmp_path / "silent.mp4")
        monkeypatch.setattr(tv, "has_audio_stream", lambda p: False)
        with pytest.raises(ValueError, match="No audio stream"):
            tv._validate_media_path(f)

    def test_accepts_valid_file_with_audio(self, tmp_path, patch_has_audio):
        f = _touch(tmp_path / "clip.mp4")
        tv._validate_media_path(f)  # should not raise

    def test_never_mentions_ffmpeg_in_errors(self, tmp_path, monkeypatch):
        """Regression guard for the ffmpeg-requirement bugfix."""
        f = _touch(tmp_path / "silent.mp4")
        monkeypatch.setattr(tv, "has_audio_stream", lambda p: False)
        with pytest.raises(ValueError) as exc_info:
            tv._validate_media_path(f)
        assert "ffmpeg" not in str(exc_info.value).lower()


class TestTranscribeSingleFile:
    def test_writes_txt_with_timestamps(
        self, tmp_path, patch_has_audio, patch_model_loader
    ):
        media = _touch(tmp_path / "devlog.mp4")
        out_dir = tmp_path / "out"
        result = tv.transcribe(media, output_dir=out_dir)
        assert result == out_dir / "devlog.txt"
        text = result.read_text(encoding="utf-8")
        assert "[00:00:00] hello world" in text
        assert "[00:00:01] this is a test" in text

    def test_writes_txt_without_timestamps(
        self, tmp_path, patch_has_audio, patch_model_loader
    ):
        media = _touch(tmp_path / "devlog.mp4")
        out_dir = tmp_path / "out"
        result = tv.transcribe(media, output_dir=out_dir, timestamps=False)
        text = result.read_text(encoding="utf-8")
        assert text.splitlines() == ["hello world", "this is a test"]

    def test_uses_default_output_dir_when_not_given(
        self, tmp_path, patch_has_audio, patch_model_loader, monkeypatch
    ):
        media = _touch(tmp_path / "devlog.mp4")
        default_dir = tmp_path / "desktop"
        default_dir.mkdir()
        monkeypatch.setattr(tv, "default_transcript_output_dir", lambda: default_dir)
        result = tv.transcribe(media)
        assert result.parent == default_dir

    def test_cpu_fallback_when_gpu_raises_cuda_error(
        self, tmp_path, patch_has_audio, monkeypatch, fake_whisper_model
    ):
        calls = []

        class FlakyModel(fake_whisper_model):
            def transcribe(self, path, **kwargs):
                calls.append(self.device)
                if self.device == "auto":
                    raise RuntimeError("Library cublas64_12.dll not found")
                return super().transcribe(path, **kwargs)

        def _load(model_name, device, compute):
            return FlakyModel(model_name, device, compute)

        monkeypatch.setattr(tv, "_load_whisper", _load)
        media = _touch(tmp_path / "devlog.mp4")
        result = tv.transcribe(media, output_dir=tmp_path / "out")
        assert calls == ["auto", "cpu"]
        assert result.exists()

    def test_reraises_non_cuda_runtime_errors(
        self, tmp_path, patch_has_audio, monkeypatch, fake_whisper_model
    ):
        class BrokenModel(fake_whisper_model):
            def transcribe(self, path, **kwargs):
                raise RuntimeError("disk full")

        monkeypatch.setattr(tv, "_load_whisper", lambda *a: BrokenModel(*a))
        media = _touch(tmp_path / "devlog.mp4")
        with pytest.raises(RuntimeError, match="disk full"):
            tv.transcribe(media, output_dir=tmp_path / "out")


class TestTranscribeBatch:
    def test_writes_individual_txt_per_file(
        self, tmp_path, patch_has_audio, patch_model_loader
    ):
        a = _touch(tmp_path / "a.mp4")
        b = _touch(tmp_path / "b.wav")
        out_dir = tmp_path / "out"
        results = tv.transcribe_batch([a, b], output_dir=out_dir)
        assert len(results) == 2
        assert all(err is None for _, err in results)
        assert (out_dir / "a.txt").exists()
        assert (out_dir / "b.txt").exists()

    def test_combined_only_writes_no_individual_files(
        self, tmp_path, patch_has_audio, patch_model_loader
    ):
        a = _touch(tmp_path / "a.mp4")
        b = _touch(tmp_path / "b.wav")
        out_dir = tmp_path / "out"
        combined = tmp_path / "merged.txt"
        results = tv.transcribe_batch(
            [a, b],
            output_dir=out_dir,
            combined_path=combined,
            write_individual_txts=False,
        )
        assert all(err is None for _, err in results)
        assert not out_dir.exists() or not any(out_dir.iterdir())
        assert combined.exists()
        text = combined.read_text(encoding="utf-8")
        assert "a.mp4" in text
        assert "b.wav" in text
        assert "hello world" in text

    def test_combined_plus_individual_writes_both(
        self, tmp_path, patch_has_audio, patch_model_loader
    ):
        a = _touch(tmp_path / "a.mp4")
        out_dir = tmp_path / "out"
        combined = tmp_path / "merged.txt"
        tv.transcribe_batch(
            [a], output_dir=out_dir, combined_path=combined, write_individual_txts=True
        )
        assert (out_dir / "a.txt").exists()
        assert combined.exists()

    def test_write_individual_false_without_combined_path_raises(self, tmp_path):
        with pytest.raises(ValueError):
            tv.transcribe_batch(
                [tmp_path / "a.mp4"], write_individual_txts=False, combined_path=None
            )

    def test_empty_paths_returns_empty_list(self):
        assert tv.transcribe_batch([]) == []

    def test_continues_after_decode_error_and_closes_combined_file(
        self, tmp_path, patch_has_audio, patch_model_loader, monkeypatch
    ):
        bad = _touch(tmp_path / "bad.mp4")
        good = _touch(tmp_path / "good.mp4")
        real_attempt = tv._run_transcribe_attempt

        def _attempt(model, path, on_segment, on_progress=None):
            if Path(path).name == "bad.mp4":
                raise ValueError("corrupt stream mid-file")
            return real_attempt(model, path, on_segment, on_progress)

        monkeypatch.setattr(tv, "_run_transcribe_attempt", _attempt)
        combined = tmp_path / "merged.txt"
        results = tv.transcribe_batch(
            [bad, good], output_dir=tmp_path / "out", combined_path=combined
        )
        errs = [err for _, err in results]
        assert isinstance(errs[0], ValueError)
        assert errs[1] is None
        assert "good.mp4" in combined.read_text(encoding="utf-8")

    def test_open_error_is_reported_as_unreadable_not_silent(
        self, tmp_path, patch_model_loader, monkeypatch
    ):
        locked = _touch(tmp_path / "locked.mp4")

        def _raise(p):
            raise tv.MediaOpenError(f"Could not read '{p.name}': permission denied")

        monkeypatch.setattr(tv, "has_audio_stream", _raise)
        results = tv.transcribe_batch([locked], output_dir=tmp_path / "out")
        assert "permission denied" in str(results[0][1])

    def test_continues_after_one_file_fails_validation(
        self, tmp_path, patch_model_loader, monkeypatch
    ):
        good = _touch(tmp_path / "good.mp4")
        bad = _touch(tmp_path / "bad.mp4")

        def _has_audio(p):
            return p.name != "bad.mp4"

        monkeypatch.setattr(tv, "has_audio_stream", _has_audio)
        out_dir = tmp_path / "out"
        results = tv.transcribe_batch([bad, good], output_dir=out_dir)
        errs = [err for _, err in results]
        assert sum(1 for e in errs if e is None) == 1
        assert sum(1 for e in errs if e is not None) == 1
        assert (out_dir / "good.txt").exists()

    def test_calls_on_file_callback_for_each_path(
        self, tmp_path, patch_has_audio, patch_model_loader
    ):
        a = _touch(tmp_path / "a.mp4")
        b = _touch(tmp_path / "b.wav")
        seen = []
        tv.transcribe_batch(
            [a, b],
            output_dir=tmp_path / "out",
            on_file=lambda i, total, p: seen.append((i, total, p.name)),
        )
        assert seen == [(1, 2, "a.mp4"), (2, 2, "b.wav")]
