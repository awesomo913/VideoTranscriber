#!/usr/bin/env python3
"""
transcribe_video.py — Offline video/audio transcription using faster-whisper.

Can be used as a CLI script OR imported as a module by transcribe_gui.py.

Supported: .mp4 .mp3 .wav .m4a .webm .ogg .flac .aac .mpeg .mov .mkv .avi
Output: by default <Desktop>/<same-stem>.txt (see default_transcript_output_dir);
        use --out-dir to override. Optional [HH:MM:SS] segment markers.

Setup:
    winget install ffmpeg          (Windows) / brew install ffmpeg (Mac)
    uv pip install faster-whisper

Usage:
    python transcribe_video.py devlog.mp4
    python transcribe_video.py a.mp4 b.wav c.mp3
    python transcribe_video.py --dir ./recordings
    python transcribe_video.py --dir ./recordings --recursive
    python transcribe_video.py devlog.mp4 --model base --no-timestamps
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac", ".aac", ".mpeg",
    ".mov", ".mkv", ".avi",
}

# When scanning a folder, do not noise-report these extensions as "skipped media"
_SKIP_REPORT_SUFFIXES = {
    ".txt", ".md", ".json", ".xml", ".srt", ".vtt", ".csv", ".pdf", ".url", ".ini",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".ico", ".svg",
    ".zip", ".rar", ".7z", ".exe", ".dll", ".lnk",
}
DEFAULT_MODEL = "small"
MODEL_SIZES = {"tiny": "75 MB", "base": "145 MB", "small": "480 MB",
               "medium": "1.5 GB", "large-v3": "3 GB"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def default_transcript_output_dir() -> Path:
    """
    Folder where .txt transcripts are written by default (Windows: Desktop).
    Falls back to home if Desktop is missing.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("USERPROFILE", str(Path.home())))
        desktop = base / "Desktop"
    else:
        desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        return desktop.resolve()
    return Path.home().resolve()


def _output_txt_path(input_path: Path, output_dir: Path) -> Path:
    """Build a unique .txt path under output_dir (hash suffix if name collides)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    candidate = output_dir / f"{stem}.txt"
    if not candidate.exists():
        return candidate
    short = hashlib.sha1(str(input_path.resolve()).encode("utf-8")).hexdigest()[:8]
    return output_dir / f"{stem}_{short}.txt"


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]"


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def has_audio_stream(file_path: Path) -> bool:
    """Return True if the file contains at least one audio stream."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", "-select_streams", "a", str(file_path)],
            capture_output=True, text=True, timeout=10,
        )
        streams = json.loads(result.stdout).get("streams", [])
        return len(streams) > 0
    except Exception:
        return True  # if ffprobe fails, let faster-whisper try anyway


# ---------------------------------------------------------------------------
# Core transcription (importable)
# ---------------------------------------------------------------------------

def _whisper_model_class():
    try:
        from faster_whisper import WhisperModel
        return WhisperModel
    except ImportError:
        raise ImportError("Run: uv pip install faster-whisper")


def _load_whisper(model_name: str, device: str, compute: str):
    WM = _whisper_model_class()
    return WM(model_name, device=device, compute_type=compute)


def _run_transcribe_attempt(
    model: object,
    input_path: Path,
    on_segment: Optional[Callable[[int, str], None]],
) -> Union[Tuple[list, object], Tuple[None, None]]:
    """Return (segments, info) or (None, None) if CUDA failed and CPU should be tried."""
    try:
        segs, inf = model.transcribe(str(input_path), beam_size=5)
        collected = []
        for seg in segs:
            collected.append(seg)
            if on_segment:
                on_segment(len(collected), seg.text.strip()[:60])
    except RuntimeError as exc:
        keywords = ("cublas", "cuda", "cufft", "dll", "library")
        if any(k in str(exc).lower() for k in keywords):
            return None, None
        raise
    return collected, inf


def _lines_from_segments(segments: list, timestamps: bool) -> List[str]:
    """Turn Whisper segments into transcript lines (non-empty text only)."""
    lines: List[str] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        prefix = f"{format_timestamp(seg.start)} " if timestamps else ""
        lines.append(f"{prefix}{text}")
    return lines


def _write_transcript_text(
    input_path: Path,
    segments: list,
    info: object,
    timestamps: bool,
    output_dir: Optional[Path] = None,
    lines: Optional[List[str]] = None,
) -> Path:
    if lines is None:
        lines = _lines_from_segments(segments, timestamps)
    out_dir = output_dir if output_dir is not None else default_transcript_output_dir()
    output_path = _output_txt_path(input_path, out_dir)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    duration = str(timedelta(seconds=int(info.duration)))
    logger.info("Done — %d segments | %s | lang: %s", len(lines), duration, info.language)
    logger.info("Saved: %s", output_path)
    return output_path


def _validate_media_path(input_path: Path) -> None:
    if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format: {input_path.suffix!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")
    if not check_ffmpeg():
        raise EnvironmentError(
            "ffmpeg not found. Install it:\n"
            "  Windows: winget install ffmpeg\n"
            "  Mac:     brew install ffmpeg\n"
            "  Linux:   sudo apt install ffmpeg"
        )
    if not has_audio_stream(input_path):
        raise ValueError(
            f"No audio stream found in '{input_path.name}'. "
            "This file is video-only and cannot be transcribed."
        )


def collect_paths(
    files: List[Path],
    directory: Optional[Path] = None,
    recursive: bool = False,
    folder_skipped_media: Optional[List[Path]] = None,
) -> List[Path]:
    """
    Build a sorted, de-duplicated list of media paths from explicit files
    and/or an optional directory scan.

    If *folder_skipped_media* is a list, append paths under *directory* that look
    like files (have an extension) but are not in SUPPORTED_EXTENSIONS, excluding
    common non-media types (``_SKIP_REPORT_SUFFIXES``). Callers can show these in
    the UI so users know why a video did not enter the queue.
    """
    out: List[Path] = []
    seen: set = set()
    if directory is not None:
        d = Path(directory)
        if not d.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        pattern = "**/*" if recursive else "*"
        for p in sorted(d.glob(pattern)):
            if not p.is_file():
                continue
            suf = p.suffix.lower()
            if suf in SUPPORTED_EXTENSIONS:
                r = p.resolve()
                if r not in seen:
                    seen.add(r)
                    out.append(p)
            elif (
                folder_skipped_media is not None
                and suf
                and suf not in _SKIP_REPORT_SUFFIXES
            ):
                folder_skipped_media.append(p)
    for f in files:
        p = Path(f)
        r = p.resolve()
        if r not in seen:
            seen.add(r)
            out.append(p)
    return out


def transcribe(
    input_path: Path,
    model_name: str = DEFAULT_MODEL,
    timestamps: bool = True,
    on_segment: Optional[Callable[[int, str], None]] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Transcribe *input_path* and write a .txt file (default: user's Desktop).

    Args:
        input_path:   Path to the media file.
        model_name:   Whisper model size (tiny/base/small/medium/large-v3).
        timestamps:   Whether to prefix each segment with [HH:MM:SS].
        on_segment:   Optional callback(segment_count, segment_text_preview).
                      Called from whichever thread runs this function.
        output_dir:   Folder for the .txt (default: default_transcript_output_dir()).

    Returns:
        Path to the written .txt file.
    """
    input_path = Path(input_path)
    _validate_media_path(input_path)

    size = MODEL_SIZES.get(model_name, "?")
    logger.info("Loading model '%s' (~%s — downloads on first use)…", model_name, size)
    model = _load_whisper(model_name, "auto", "auto")
    logger.info("Transcribing: %s", input_path.name)

    segments, info = _run_transcribe_attempt(model, input_path, on_segment)
    if segments is None:
        logger.warning("GPU path failed — retrying on CPU.")
        model = _load_whisper(model_name, "cpu", "int8")
        segments, info = _run_transcribe_attempt(model, input_path, on_segment)
    if segments is None:
        raise RuntimeError("Transcription failed on both GPU and CPU.")

    return _write_transcript_text(
        input_path, segments, info, timestamps, output_dir=output_dir,
    )


def transcribe_batch(
    paths: List[Path],
    model_name: str = DEFAULT_MODEL,
    timestamps: bool = True,
    on_segment: Optional[Callable[[int, str], None]] = None,
    on_file: Optional[Callable[[int, int, Path], None]] = None,
    output_dir: Optional[Path] = None,
    combined_path: Optional[Path] = None,
    write_individual_txts: bool = True,
) -> List[Tuple[Path, Optional[Exception]]]:
    """
    Transcribe many files using one model load when possible (CPU fallback
    applies to the rest of the queue once triggered).

    Args:
        paths:        Media files (callers should use collect_paths).
        on_file:      Optional callback (1-based index, total, path) before each file.
        combined_path: If set, append each successful transcript to this file
                       (UTF-8) with a header per source file.
        write_individual_txts: If False, only ``combined_path`` is written
                               (must be set).

    Returns:
        List of (output .txt path or input path on total failure, error or None).
    """
    _whisper_model_class()
    if not paths:
        return []

    if not write_individual_txts and combined_path is None:
        raise ValueError("write_individual_txts=False requires combined_path.")

    combo_fp = None
    if combined_path is not None:
        cp = Path(combined_path)
        cp.parent.mkdir(parents=True, exist_ok=True)
        combo_fp = cp.open("w", encoding="utf-8")
        combo_fp.write(
            "Combined transcripts (offline faster-whisper)\n"
            f"Sources: {len(paths)} file(s)\n\n"
        )

    size = MODEL_SIZES.get(model_name, "?")
    logger.info(
        "Batch: %d file(s) — loading model '%s' (~%s)…",
        len(paths), model_name, size,
    )

    model = _load_whisper(model_name, "auto", "auto")
    using_cpu = False
    results: List[Tuple[Path, Optional[Exception]]] = []

    for i, input_path in enumerate(paths, start=1):
        input_path = Path(input_path)
        if on_file:
            on_file(i, len(paths), input_path)

        try:
            _validate_media_path(input_path)
        except (ValueError, FileNotFoundError, EnvironmentError) as exc:
            logger.error("[%d/%d] %s — %s", i, len(paths), input_path.name, exc)
            results.append((input_path, exc))
            continue

        logger.info("Transcribing [%d/%d]: %s", i, len(paths), input_path.name)

        segments, info = _run_transcribe_attempt(model, input_path, on_segment)
        if segments is None and not using_cpu:
            logger.warning("GPU path failed — switching to CPU for remaining files.")
            model = _load_whisper(model_name, "cpu", "int8")
            using_cpu = True
            segments, info = _run_transcribe_attempt(model, input_path, on_segment)

        if segments is None:
            err = RuntimeError("Transcription failed on both GPU and CPU.")
            logger.error("[%d/%d] %s — %s", i, len(paths), input_path.name, err)
            results.append((input_path, err))
            continue

        try:
            lines = _lines_from_segments(segments, timestamps)
            out: Optional[Path] = None
            if write_individual_txts:
                out = _write_transcript_text(
                    input_path,
                    segments,
                    info,
                    timestamps,
                    output_dir=output_dir,
                    lines=lines,
                )
            else:
                duration = str(timedelta(seconds=int(info.duration)))
                logger.info(
                    "Done — %d segments | %s | lang: %s",
                    len(lines), duration, info.language,
                )

            if combo_fp is not None:
                combo_fp.write(f"{'=' * 80}\n")
                combo_fp.write(f"File: {input_path.name}\n")
                combo_fp.write(f"Path: {input_path.resolve()}\n")
                combo_fp.write(f"[{i}/{len(paths)}]\n")
                combo_fp.write(f"{'=' * 80}\n\n")
                combo_fp.write("\n".join(lines))
                combo_fp.write("\n\n")

            results.append((out if out is not None else input_path, None))
        except Exception as exc:
            logger.exception("[%d/%d] %s", i, len(paths), input_path.name)
            results.append((input_path, exc))

    if combo_fp is not None:
        combo_fp.close()
        logger.info("Combined transcript saved: %s", combined_path)

    ok = sum(1 for _, e in results if e is None)
    logger.info("Batch finished: %d/%d succeeded.", ok, len(results))
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Transcribe video/audio to text (offline, free).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python transcribe_video.py devlog.mp4\n"
            "  python transcribe_video.py a.mp4 b.wav c.mp3\n"
            "  python transcribe_video.py --dir ./recordings\n"
            "  python transcribe_video.py --dir ./vids --recursive\n"
            "  python transcribe_video.py devlog.mp4 --model base\n"
            "  python transcribe_video.py devlog.wav --no-timestamps\n"
            "  python transcribe_video.py --dir ~/Desktop/videos --combined-only\n"
            "  python transcribe_video.py --dir ./rec --combined --combined-out D:/all.txt\n"
        ),
    )
    p.add_argument(
        "input_files",
        type=Path,
        nargs="*",
        help="One or more media files (or use --dir).",
    )
    p.add_argument(
        "--dir", "-d",
        type=Path,
        metavar="FOLDER",
        help="Transcribe every supported file in this folder (combine with file args).",
    )
    p.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="With --dir, include subfolders.",
    )
    p.add_argument(
        "--model", default=DEFAULT_MODEL,
        choices=list(MODEL_SIZES.keys()),
        help=f"Model size (default: {DEFAULT_MODEL}). Larger = more accurate, slower.",
    )
    p.add_argument("--no-timestamps", action="store_true",
                   help="Output plain prose without [HH:MM:SS] markers.")
    p.add_argument(
        "--out-dir", "-o",
        type=Path,
        metavar="FOLDER",
        help="Write .txt transcripts here (default: your Desktop).",
    )
    p.add_argument(
        "--combined",
        action="store_true",
        help="Merge successful transcripts into one UTF-8 file (--combined-out).",
    )
    p.add_argument(
        "--combined-out",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path for merged transcript (default: Desktop/merged_transcripts.txt).",
    )
    p.add_argument(
        "--combined-only",
        action="store_true",
        help="Only write the merged file (no per-source .txt on Desktop).",
    )
    return p


def main() -> None:
    # Crash logger — only when running as CLI
    try:
        sys.path.insert(0, str(Path.home() / ".claude" / "scripts"))
        from crash_logger import install
        install(project_root=Path(__file__).parent)
    except Exception:
        pass

    args = _build_parser().parse_args()
    try:
        paths = collect_paths(
            list(args.input_files),
            directory=args.dir,
            recursive=args.recursive,
        )
    except (NotADirectoryError, OSError) as exc:
        logger.error("%s", exc)
        sys.exit(1)

    if not paths:
        logger.error("No input files. Pass one or more files and/or use --dir FOLDER.")
        sys.exit(1)

    out_dir = (
        args.out_dir.resolve() if args.out_dir else default_transcript_output_dir()
    )
    logger.info("Transcript output folder: %s", out_dir)

    want_combined = args.combined or args.combined_only
    combined_path: Optional[Path] = None
    write_individual = not args.combined_only
    if want_combined:
        combined_path = (
            args.combined_out.resolve()
            if args.combined_out
            else default_transcript_output_dir() / "merged_transcripts.txt"
        )
        logger.info("Merged output file: %s", combined_path)

    try:
        if len(paths) == 1 and not want_combined:
            transcribe(
                input_path=paths[0].resolve(),
                model_name=args.model,
                timestamps=not args.no_timestamps,
                output_dir=out_dir,
            )
        else:
            res = transcribe_batch(
                paths=[p.resolve() for p in paths],
                model_name=args.model,
                timestamps=not args.no_timestamps,
                on_file=lambda i, t, p: logger.info("— starting %d/%d: %s —", i, t, p.name),
                output_dir=out_dir,
                combined_path=combined_path,
                write_individual_txts=write_individual,
            )
            failed = [r for r in res if r[1] is not None]
            if failed:
                for target, err in failed:
                    logger.error("Failed: %s — %s", target, err)
                sys.exit(1)
    except (ValueError, FileNotFoundError, EnvironmentError, ImportError) as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
