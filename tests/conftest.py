"""Shared pytest fixtures for the VideoTranscriber test suite.

Nothing here opens a GUI window, downloads a Whisper model, or touches
the network — transcribe_video's model loader is mocked wherever a test
needs to exercise the transcribe()/transcribe_batch() pipeline.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


class FakeSegment:
    """Stand-in for a faster_whisper Segment (only the fields we read)."""

    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class FakeInfo(SimpleNamespace):
    """Stand-in for a faster_whisper TranscriptionInfo."""


class FakeWhisperModel:
    """
    Drop-in replacement for faster_whisper.WhisperModel.

    Records every call so tests can assert on device/compute_type, and
    returns a fixed, tiny set of segments so tests never depend on real
    model output or a model download.
    """

    instances: list[FakeWhisperModel] = []

    def __init__(self, model_name, device="auto", compute_type="auto"):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.transcribe_calls: list = []
        FakeWhisperModel.instances.append(self)

    def transcribe(self, path, **kwargs):
        self.transcribe_calls.append((path, kwargs))
        segments = [
            FakeSegment(0.0, 1.5, "hello world"),
            FakeSegment(1.5, 3.0, "this is a test"),
        ]
        info = FakeInfo(duration=3.0, language="en")
        return iter(segments), info


@pytest.fixture(autouse=True)
def _reset_fake_model_registry():
    FakeWhisperModel.instances.clear()
    yield
    FakeWhisperModel.instances.clear()


@pytest.fixture
def fake_whisper_model():
    return FakeWhisperModel


@pytest.fixture
def make_media_file(tmp_path):
    """Create an empty placeholder media file with a given extension."""

    def _make(name: str = "clip.mp4", content: bytes = b"\x00") -> Path:
        p = tmp_path / name
        p.write_bytes(content)
        return p

    return _make
