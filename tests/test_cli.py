"""CLI-level tests: argument parsing and main() wiring for --out-dir/--combined."""
from __future__ import annotations

from pathlib import Path

import pytest

import transcribe_video as tv


def _touch(path: Path) -> Path:
    path.write_bytes(b"\x00")
    return path


@pytest.fixture(autouse=True)
def patch_has_audio(monkeypatch):
    monkeypatch.setattr(tv, "has_audio_stream", lambda p: True)


@pytest.fixture(autouse=True)
def patch_model_loader(monkeypatch, fake_whisper_model):
    monkeypatch.setattr(tv, "_load_whisper", lambda *a: fake_whisper_model(*a))


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(tv.sys, "argv", ["transcribe_video.py", *argv])
    tv.main()


class TestArgParser:
    def test_default_model_is_small(self):
        args = tv._build_parser().parse_args(["clip.mp4"])
        assert args.model == "small"

    def test_out_dir_flag_short_and_long(self):
        args = tv._build_parser().parse_args(["clip.mp4", "-o", "D:/out"])
        assert args.out_dir == Path("D:/out")
        args2 = tv._build_parser().parse_args(["clip.mp4", "--out-dir", "D:/out"])
        assert args2.out_dir == Path("D:/out")

    def test_combined_flags(self):
        args = tv._build_parser().parse_args(["--dir", "x", "--combined-only"])
        assert args.combined_only is True
        assert args.combined is False

    def test_rejects_invalid_model_choice(self):
        with pytest.raises(SystemExit):
            tv._build_parser().parse_args(["clip.mp4", "--model", "huge"])

    def test_combined_out_help_describes_out_dir_default(self):
        """Regression guard: help text must match the --out-dir-based default."""
        parser = tv._build_parser()
        action = next(a for a in parser._actions if "--combined-out" in a.option_strings)
        assert "<out-dir>/merged_transcripts.txt" in action.help
        assert "Desktop" not in action.help


class TestMainOutDir:
    def test_single_file_respects_out_dir(self, tmp_path, monkeypatch):
        media = _touch(tmp_path / "clip.mp4")
        out_dir = tmp_path / "custom_out"
        _run_main(monkeypatch, [str(media), "--out-dir", str(out_dir)])
        assert (out_dir / "clip.txt").exists()

    def test_exits_nonzero_with_no_input_files(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            _run_main(monkeypatch, [])
        assert exc_info.value.code == 1

    def test_exits_nonzero_when_directory_missing(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            _run_main(monkeypatch, ["--dir", str(tmp_path / "nope")])
        assert exc_info.value.code == 1


class TestMainCombined:
    def test_combined_only_writes_merged_file_and_no_individuals(
        self, tmp_path, monkeypatch
    ):
        a = _touch(tmp_path / "a.mp4")
        b = _touch(tmp_path / "b.wav")
        out_dir = tmp_path / "out"
        combined_out = tmp_path / "merged.txt"
        _run_main(
            monkeypatch,
            [
                str(a), str(b),
                "--out-dir", str(out_dir),
                "--combined-only",
                "--combined-out", str(combined_out),
            ],
        )
        assert combined_out.exists()
        assert not (out_dir / "a.txt").exists()
        assert not (out_dir / "b.txt").exists()

    def test_combined_default_path_is_under_desktop(self, tmp_path, monkeypatch):
        a = _touch(tmp_path / "a.mp4")
        default_dir = tmp_path / "desktop"
        default_dir.mkdir()
        monkeypatch.setattr(tv, "default_transcript_output_dir", lambda: default_dir)
        _run_main(monkeypatch, [str(a), "--combined"])
        assert (default_dir / "merged_transcripts.txt").exists()
        assert (default_dir / "a.txt").exists()

    def test_combined_default_path_respects_out_dir(self, tmp_path, monkeypatch):
        """Regression test: --combined with --out-dir must not write to Desktop."""
        a = _touch(tmp_path / "a.mp4")
        default_dir = tmp_path / "desktop"
        default_dir.mkdir()
        out_dir = tmp_path / "custom_out"
        monkeypatch.setattr(tv, "default_transcript_output_dir", lambda: default_dir)
        _run_main(monkeypatch, [str(a), "--combined", "--out-dir", str(out_dir)])
        assert (out_dir / "merged_transcripts.txt").exists()
        assert not (default_dir / "merged_transcripts.txt").exists()

    def test_combined_only_default_path_respects_out_dir(self, tmp_path, monkeypatch):
        """Regression test: --combined-only with --out-dir must not write to Desktop."""
        a = _touch(tmp_path / "a.mp4")
        default_dir = tmp_path / "desktop"
        default_dir.mkdir()
        out_dir = tmp_path / "custom_out"
        monkeypatch.setattr(tv, "default_transcript_output_dir", lambda: default_dir)
        _run_main(monkeypatch, [str(a), "--combined-only", "--out-dir", str(out_dir)])
        assert (out_dir / "merged_transcripts.txt").exists()
        assert not (out_dir / "a.txt").exists()
        assert not default_dir.exists() or not any(default_dir.iterdir())

    def test_batch_exits_nonzero_when_any_file_fails(self, tmp_path, monkeypatch):
        good = _touch(tmp_path / "good.mp4")
        bad = _touch(tmp_path / "bad.mp4")
        monkeypatch.setattr(tv, "has_audio_stream", lambda p: p.name != "bad.mp4")
        with pytest.raises(SystemExit) as exc_info:
            _run_main(
                monkeypatch,
                [str(good), str(bad), "--out-dir", str(tmp_path / "out")],
            )
        assert exc_info.value.code == 1
