"""
Tests for GPU detection and model-construction-time GPU->CPU fallback.

Nothing here loads a real model or touches real ctranslate2 CUDA calls — the
faster_whisper model class and ctranslate2 module are both faked.
"""
from __future__ import annotations

import logging
import sys

import pytest

import transcribe_video as tv

# Captured before the autouse `_default_cuda_available` fixture (conftest.py)
# patches tv._cuda_available for every test — TestCudaAvailable below exercises
# the real implementation directly instead of the per-test stub.
_real_cuda_available = tv._cuda_available


class _FlakyConstructWM:
    """Fake WhisperModel class: raises a CUDA-flavored error on 'auto', else OK."""

    def __init__(self, model_name, device="auto", compute_type="auto"):
        if device == "auto":
            raise RuntimeError("Library cublas64_12.dll not found")
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type


class _NonCudaBrokenWM:
    """Fake WhisperModel class: raises a non-CUDA RuntimeError regardless of device."""

    def __init__(self, model_name, device="auto", compute_type="auto"):
        raise RuntimeError("disk full")


def _fake_ctranslate2(count=None, raises: Exception | None = None):
    class _Fake:
        @staticmethod
        def get_cuda_device_count():
            if raises is not None:
                raise raises
            return count

    return _Fake()


class TestCudaAvailable:
    def test_true_when_devices_present(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ctranslate2", _fake_ctranslate2(count=2))
        assert _real_cuda_available() is True

    def test_false_when_no_devices(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ctranslate2", _fake_ctranslate2(count=0))
        assert _real_cuda_available() is False

    def test_fails_open_and_logs_when_check_itself_raises(self, monkeypatch, caplog):
        monkeypatch.setitem(
            sys.modules,
            "ctranslate2",
            _fake_ctranslate2(raises=OSError("no native ctranslate2 lib")),
        )
        with caplog.at_level(logging.WARNING, logger=tv.logger.name):
            assert _real_cuda_available() is True
        assert "Could not check CUDA device count" in caplog.text


class TestLoadWhisperWithFallback:
    def test_skips_gpu_attempt_entirely_when_no_cuda_device(self, monkeypatch, caplog):
        """LOW bug fix: no CUDA device at all -> go straight to CPU, no GPU attempt."""
        monkeypatch.setattr(tv, "_cuda_available", lambda: False)
        monkeypatch.setattr(tv, "_whisper_model_class", lambda: _FlakyConstructWM)
        with caplog.at_level(logging.INFO, logger=tv.logger.name):
            model, used_cpu = tv._load_whisper_with_fallback("small")
        assert used_cpu is True
        assert model.device == "cpu"
        assert model.compute_type == "int8"
        assert "No compatible GPU found — using CPU." in caplog.text

    def test_falls_back_to_cpu_when_gpu_construction_raises_cuda_error(
        self, monkeypatch, caplog
    ):
        """MEDIUM bug fix: construction-time (not just transcribe-time) CUDA failure."""
        monkeypatch.setattr(tv, "_cuda_available", lambda: True)
        monkeypatch.setattr(tv, "_whisper_model_class", lambda: _FlakyConstructWM)
        with caplog.at_level(logging.INFO, logger=tv.logger.name):
            model, used_cpu = tv._load_whisper_with_fallback("small")
        assert used_cpu is True
        assert model.device == "cpu"
        assert model.compute_type == "int8"
        # Underlying exception text must be logged, not hidden.
        assert "GPU model load failed" in caplog.text
        assert "cublas64_12.dll" in caplog.text
        # User-facing wording must be the calm, non-scary INFO message.
        assert "No compatible GPU found — using CPU." in caplog.text

    def test_user_facing_fallback_message_is_info_not_warning(self, monkeypatch, caplog):
        monkeypatch.setattr(tv, "_cuda_available", lambda: True)
        monkeypatch.setattr(tv, "_whisper_model_class", lambda: _FlakyConstructWM)
        with caplog.at_level(logging.DEBUG, logger=tv.logger.name):
            tv._load_whisper_with_fallback("small")
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("No compatible GPU found — using CPU." in r.message for r in info_records)

    def test_reraises_non_cuda_construction_errors(self, monkeypatch):
        monkeypatch.setattr(tv, "_cuda_available", lambda: True)
        monkeypatch.setattr(tv, "_whisper_model_class", lambda: _NonCudaBrokenWM)
        with pytest.raises(RuntimeError, match="disk full"):
            tv._load_whisper_with_fallback("small")

    def test_uses_gpu_when_available_and_construction_succeeds(
        self, monkeypatch, fake_whisper_model
    ):
        monkeypatch.setattr(tv, "_cuda_available", lambda: True)
        monkeypatch.setattr(tv, "_whisper_model_class", lambda: fake_whisper_model)
        model, used_cpu = tv._load_whisper_with_fallback("small")
        assert used_cpu is False
        assert model.device == "auto"


class TestTranscribeTimeFallbackLogging:
    """transcribe()/transcribe_batch() still fall back when transcribe() itself raises."""

    def test_transcribe_logs_underlying_exception_and_calm_message(
        self, tmp_path, monkeypatch, fake_whisper_model, caplog
    ):
        monkeypatch.setattr(tv, "has_audio_stream", lambda p: True)

        class FlakyModel(fake_whisper_model):
            def transcribe(self, path, **kwargs):
                if self.device == "auto":
                    raise RuntimeError("Library cublas64_12.dll not found")
                return super().transcribe(path, **kwargs)

        monkeypatch.setattr(tv, "_load_whisper", lambda *a: FlakyModel(*a))
        media = tmp_path / "devlog.mp4"
        media.write_bytes(b"\x00")

        with caplog.at_level(logging.INFO, logger=tv.logger.name):
            result = tv.transcribe(media, output_dir=tmp_path / "out")

        assert result.exists()
        assert "GPU transcription failed" in caplog.text
        assert "cublas64_12.dll" in caplog.text
        assert "No compatible GPU found — using CPU." in caplog.text
