#!/usr/bin/env python3
"""
transcribe_video.py — Offline video/audio transcription using faster-whisper.

Can be used as a CLI script OR imported as a module by transcribe_gui.py.

Supported: .mp4 .mp3 .wav .m4a .webm .ogg .flac .aac .mpeg
Output: <same-dir>/<same-stem>.txt with optional [HH:MM:SS] segment markers.

Setup:
    winget install ffmpeg          (Windows) / brew install ffmpeg (Mac)
    uv pip install faster-whisper

Usage:
    python transcribe_video.py devlog.mp4
    python transcribe_video.py devlog.mp4 --model base --no-timestamps
"""

import argparse
import logging
import shutil
import sys
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional

SUPPORTED_EXTENSIONS = {".mp4", ".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac", ".aac", ".mpeg"}
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

def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]"


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


# ---------------------------------------------------------------------------
# Core transcription (importable)
# ---------------------------------------------------------------------------

def transcribe(
    input_path: Path,
    model_name: str = DEFAULT_MODEL,
    timestamps: bool = True,
    on_segment: Optional[Callable[[int, str], None]] = None,
) -> Path:
    """
    Transcribe *input_path* and write a .txt file in the same directory.

    Args:
        input_path:   Path to the media file.
        model_name:   Whisper model size (tiny/base/small/medium/large-v3).
        timestamps:   Whether to prefix each segment with [HH:MM:SS].
        on_segment:   Optional callback(segment_count, segment_text_preview).
                      Called from whichever thread runs this function.

    Returns:
        Path to the written .txt file.
    """
    input_path = Path(input_path)

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

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError("Run: uv pip install faster-whisper")

    size = MODEL_SIZES.get(model_name, "?")
    logger.info("Loading model '%s' (~%s — downloads on first use)…", model_name, size)

    def _load(device: str, compute: str) -> "WhisperModel":
        return WhisperModel(model_name, device=device, compute_type=compute)

    model = _load("auto", "auto")
    logger.info("Transcribing: %s", input_path.name)

    def _run(m: "WhisperModel"):
        segs, inf = m.transcribe(str(input_path), beam_size=5)
        collected = []
        try:
            for seg in segs:
                collected.append(seg)
                if on_segment:
                    on_segment(len(collected), seg.text.strip()[:60])
        except RuntimeError as exc:
            keywords = ("cublas", "cuda", "cufft", "dll", "library")
            if any(k in str(exc).lower() for k in keywords):
                return None, None  # signal CPU fallback needed
            raise
        return collected, inf

    segments, info = _run(model)
    if segments is None:
        logger.warning("GPU init failed — retrying on CPU.")
        model = _load("cpu", "int8")
        segments, info = _run(model)

    lines = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        prefix = f"{format_timestamp(seg.start)} " if timestamps else ""
        lines.append(f"{prefix}{text}")

    output_path = input_path.with_suffix(".txt")
    output_path.write_text("\n".join(lines), encoding="utf-8")

    duration = str(timedelta(seconds=int(info.duration)))
    logger.info("Done — %d segments | %s | lang: %s", len(lines), duration, info.language)
    logger.info("Saved: %s", output_path)
    return output_path


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
            "  python transcribe_video.py devlog.mp4 --model base\n"
            "  python transcribe_video.py devlog.wav --no-timestamps\n"
        ),
    )
    p.add_argument("input_file", type=Path)
    p.add_argument(
        "--model", default=DEFAULT_MODEL,
        choices=list(MODEL_SIZES.keys()),
        help=f"Model size (default: {DEFAULT_MODEL}). Larger = more accurate, slower.",
    )
    p.add_argument("--no-timestamps", action="store_true",
                   help="Output plain prose without [HH:MM:SS] markers.")
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
        transcribe(
            input_path=args.input_file.resolve(),
            model_name=args.model,
            timestamps=not args.no_timestamps,
        )
    except (ValueError, FileNotFoundError, EnvironmentError, ImportError) as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
