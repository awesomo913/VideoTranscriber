"""Tests for pure helper functions: timestamps, output paths, audio-stream check."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

import transcribe_video as tv


class TestFormatTimestamp:
    def test_zero_seconds(self):
        assert tv.format_timestamp(0) == "[00:00:00]"

    def test_sub_minute(self):
        assert tv.format_timestamp(42) == "[00:00:42]"

    def test_minutes_and_seconds(self):
        assert tv.format_timestamp(125) == "[00:02:05]"

    def test_hours(self):
        assert tv.format_timestamp(3661) == "[01:01:01]"

    def test_truncates_fractional_seconds(self):
        assert tv.format_timestamp(59.9) == "[00:00:59]"


class TestOutputTxtPath:
    def test_creates_output_dir(self, tmp_path):
        out_dir = tmp_path / "does" / "not" / "exist"
        result = tv._output_txt_path(Path("devlog.mp4"), out_dir)
        assert out_dir.is_dir()
        assert result == out_dir / "devlog.txt"

    def test_no_collision_uses_plain_stem(self, tmp_path):
        result = tv._output_txt_path(Path("devlog.mp4"), tmp_path)
        assert result.name == "devlog.txt"

    def test_collision_adds_hash_suffix(self, tmp_path):
        existing = tmp_path / "devlog.txt"
        existing.write_text("already here")
        result = tv._output_txt_path(tmp_path / "devlog.mp4", tmp_path)
        assert result.name != "devlog.txt"
        assert result.name.startswith("devlog_")
        assert result.name.endswith(".txt")

    def test_collision_hash_is_stable_for_same_input(self, tmp_path):
        existing = tmp_path / "devlog.txt"
        existing.write_text("already here")
        input_path = tmp_path / "devlog.mp4"
        r1 = tv._output_txt_path(input_path, tmp_path)
        r2 = tv._output_txt_path(input_path, tmp_path)
        assert r1 == r2

    def test_never_overwrites_when_hash_suffixed_name_also_exists(self, tmp_path):
        """
        Regression test: re-running on the same stem twice used to silently
        overwrite the hash-suffixed transcript from the second run.
        """
        input_path = tmp_path / "devlog.mp4"
        (tmp_path / "devlog.txt").write_text("run 1")
        hashed = tv._output_txt_path(input_path, tmp_path)
        hashed.write_text("run 2")

        result = tv._output_txt_path(input_path, tmp_path)

        assert result != (tmp_path / "devlog.txt")
        assert result != hashed
        assert result.name.startswith("devlog_")
        assert result.name.endswith("_2.txt")
        # Nothing already on disk was touched by just computing the path.
        assert (tmp_path / "devlog.txt").read_text() == "run 1"
        assert hashed.read_text() == "run 2"

    def test_never_overwrites_across_many_repeated_collisions(self, tmp_path):
        input_path = tmp_path / "devlog.mp4"
        (tmp_path / "devlog.txt").write_text("run 1")
        hashed = tv._output_txt_path(input_path, tmp_path)
        hashed.write_text("run 2")

        seen_paths = {tmp_path / "devlog.txt", hashed}
        for i in range(5):
            p = tv._output_txt_path(input_path, tmp_path)
            assert p not in seen_paths
            p.write_text(f"run {i + 3}")
            seen_paths.add(p)

        # Every file written above must still exist, untouched by later calls.
        for path in seen_paths:
            assert path.exists()


class TestDefaultTranscriptOutputDir:
    def test_falls_back_to_home_when_desktop_missing(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home_without_desktop"
        fake_home.mkdir()
        monkeypatch.setattr(tv.sys, "platform", "linux")
        monkeypatch.setattr(tv.Path, "home", staticmethod(lambda: fake_home))
        result = tv.default_transcript_output_dir()
        assert result == fake_home.resolve()

    def test_uses_desktop_when_present(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home_with_desktop"
        (fake_home / "Desktop").mkdir(parents=True)
        monkeypatch.setattr(tv.sys, "platform", "linux")
        monkeypatch.setattr(tv.Path, "home", staticmethod(lambda: fake_home))
        result = tv.default_transcript_output_dir()
        assert result == (fake_home / "Desktop").resolve()

    def test_windows_uses_userprofile_env(self, monkeypatch, tmp_path):
        fake_profile = tmp_path / "winhome"
        (fake_profile / "Desktop").mkdir(parents=True)
        monkeypatch.setattr(tv.sys, "platform", "win32")
        monkeypatch.setenv("USERPROFILE", str(fake_profile))
        result = tv.default_transcript_output_dir()
        assert result == (fake_profile / "Desktop").resolve()


class TestHasAudioStream:
    def test_true_when_container_has_audio_stream(self, monkeypatch, tmp_path):
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"\x00")

        class FakeStreams:
            audio = [object()]

        class FakeContainer:
            streams = FakeStreams()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(tv.av, "open", lambda path: FakeContainer())
        assert tv.has_audio_stream(media) is True

    def test_false_when_container_has_no_audio_stream(self, monkeypatch, tmp_path):
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"\x00")

        class FakeStreams:
            audio: list = []

        class FakeContainer:
            streams = FakeStreams()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(tv.av, "open", lambda path: FakeContainer())
        assert tv.has_audio_stream(media) is False

    def test_raises_media_open_error_when_file_cannot_be_opened(self, monkeypatch, tmp_path):
        media = tmp_path / "corrupt.mp4"
        media.write_bytes(b"not real media")

        def _raise(path):
            raise OSError("bad file")

        monkeypatch.setattr(tv.av, "open", _raise)
        with pytest.raises(tv.MediaOpenError, match="bad file"):
            tv.has_audio_stream(media)


class TestSetupLogging:
    def test_writes_log_file_under_localappdata(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(tv.setup_logging, "_done", False, raising=False)
        path = tv.setup_logging()
        assert path == tmp_path / "VideoTranscriber" / "logs" / "app.log"
        tv.logger.warning("hello log")
        for h in logging.getLogger().handlers:
            h.flush()
        assert "hello log" in path.read_text(encoding="utf-8")
