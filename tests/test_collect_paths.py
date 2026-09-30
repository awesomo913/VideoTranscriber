"""Tests for collect_paths() — file/folder discovery, extension filtering, dedup."""
from __future__ import annotations

from pathlib import Path

import pytest

import transcribe_video as tv


def _touch(path: Path, content: bytes = b"\x00") -> Path:
    path.write_bytes(content)
    return path


class TestCollectPathsExplicitFiles:
    def test_returns_explicit_files_in_order(self, tmp_path):
        a = _touch(tmp_path / "a.mp4")
        b = _touch(tmp_path / "b.wav")
        result = tv.collect_paths([a, b])
        assert result == [a, b]

    def test_deduplicates_explicit_files(self, tmp_path):
        a = _touch(tmp_path / "a.mp4")
        result = tv.collect_paths([a, a])
        assert result == [a]

    def test_empty_input_returns_empty_list(self):
        assert tv.collect_paths([]) == []


class TestCollectPathsDirectory:
    def test_finds_supported_extensions_only(self, tmp_path):
        _touch(tmp_path / "video.mp4")
        _touch(tmp_path / "notes.txt")
        _touch(tmp_path / "audio.wav")
        result = tv.collect_paths([], directory=tmp_path)
        names = sorted(p.name for p in result)
        assert names == ["audio.wav", "video.mp4"]

    def test_non_recursive_ignores_subfolders(self, tmp_path):
        _touch(tmp_path / "top.mp4")
        sub = tmp_path / "sub"
        sub.mkdir()
        _touch(sub / "nested.mp4")
        result = tv.collect_paths([], directory=tmp_path, recursive=False)
        assert [p.name for p in result] == ["top.mp4"]

    def test_recursive_includes_subfolders(self, tmp_path):
        _touch(tmp_path / "top.mp4")
        sub = tmp_path / "sub"
        sub.mkdir()
        _touch(sub / "nested.mp4")
        result = tv.collect_paths([], directory=tmp_path, recursive=True)
        names = sorted(p.name for p in result)
        assert names == ["nested.mp4", "top.mp4"]

    def test_raises_for_missing_directory(self, tmp_path):
        with pytest.raises(NotADirectoryError):
            tv.collect_paths([], directory=tmp_path / "nope")

    def test_directory_and_explicit_files_combined_and_deduped(self, tmp_path):
        dir_file = _touch(tmp_path / "a.mp4")
        explicit = tmp_path / "a.mp4"  # same file, passed explicitly too
        other = _touch(tmp_path / "b.mp3")
        result = tv.collect_paths([explicit, other], directory=tmp_path)
        resolved = {p.resolve() for p in result}
        assert resolved == {dir_file.resolve(), other.resolve()}
        assert len(result) == 2


class TestCollectPathsSkippedMedia:
    def test_reports_unrecognized_media_like_extensions(self, tmp_path):
        _touch(tmp_path / "clip.mp4")
        _touch(tmp_path / "weird.mts")  # media-ish but unsupported
        skipped: list = []
        found = tv.collect_paths([], directory=tmp_path, folder_skipped_media=skipped)
        assert [p.name for p in found] == ["clip.mp4"]
        assert [p.name for p in skipped] == ["weird.mts"]

    def test_does_not_report_common_non_media_suffixes(self, tmp_path):
        _touch(tmp_path / "readme.md")
        _touch(tmp_path / "cover.jpg")
        _touch(tmp_path / "archive.zip")
        skipped: list = []
        tv.collect_paths([], directory=tmp_path, folder_skipped_media=skipped)
        assert skipped == []

    def test_skipped_media_not_collected_when_list_not_provided(self, tmp_path):
        _touch(tmp_path / "clip.mp4")
        _touch(tmp_path / "weird.mts")
        found = tv.collect_paths([], directory=tmp_path)
        assert [p.name for p in found] == ["clip.mp4"]
