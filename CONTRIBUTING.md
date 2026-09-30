# Contributing to VideoTranscriber

Thanks for considering a contribution. VideoTranscriber is a small, free, open-source offline transcription tool — issues and PRs of any size are welcome.

## Dev setup

Requires Python 3.11.

```bash
git clone https://github.com/awesomo913/VideoTranscriber.git
cd VideoTranscriber
uv venv --python 3.11
uv pip install -r requirements.txt
# GUI
python transcribe_gui.py
# CLI
python transcribe_video.py devlog.mp4
```

For running the full check suite and building the exe, also install the dev dependencies:

```bash
uv pip install -r requirements-dev.txt
```

No `ffmpeg`/`ffprobe` install is needed — audio/video decoding goes through [PyAV](https://github.com/PyAV-Org/PyAV) (`av` in `requirements.txt`), which bundles its own FFmpeg libraries.

## Running tests and lint

```bash
pytest
ruff check .
```

Please run both before opening a PR. Tests never open the GUI window, download a Whisper model, or touch the network — the Whisper model is mocked in `tests/conftest.py`.

## Architecture

- `transcribe_video.py` — core transcription logic (importable) + CLI entry point. Validates input, loads the Whisper model, handles GPU→CPU fallback, formats and writes output.
- `transcribe_gui.py` — CustomTkinter desktop GUI. Imports everything from `transcribe_video.py`; runs transcription in a background thread and posts UI updates back via `self.after(0, ...)`.
- `tests/` — pytest suite; `conftest.py` provides a `FakeWhisperModel` so no test depends on a real model.

### Key implementation details worth knowing before you change things

- `WhisperModel.transcribe()` runs language detection *before* yielding segments, so the CUDA-failure `try`/`except` in `_run_transcribe_attempt()` must wrap the **entire** `transcribe()` call, not just the segment loop — a narrower `try` will miss the common failure mode on Windows machines without CUDA 12 libraries installed.
- `has_audio_stream()` opens the file with PyAV (`av.open`) and checks `container.streams.audio` — this is a pre-flight check so a video-only or corrupt file gets a clear error message instead of an obscure exception from inside faster-whisper.
- Default transcript output folder is the user's Desktop (`default_transcript_output_dir()`); `--out-dir` / `-o` on the CLI and the "Save to" field in the GUI override it. If `{stem}.txt` already exists in the output folder, a short hash suffix is appended instead of overwriting.
- `collect_paths()` powers both CLI folder scanning (`--dir` / `--recursive`) and the GUI's "Folder…" button, so a fix there fixes both interfaces at once.

## Code style

- Small, focused functions over large ones; prefer early returns over deep nesting.
- No silent `except:` blocks — catch specific exceptions, log or surface them, never swallow.
- Anything that touches the GUI (tkinter) must run on the main thread; background threads hand results back via `self.after(0, ...)`, not by touching widgets directly.
- Use `logging` (module-level `logger = logging.getLogger(__name__)`), not `print()`, in library code.

## Good first issues

Looking for a place to start? These roadmap items are scoped well for a first PR:

- Drag-and-drop file input for the GUI (`tkinterdnd2`)
- Progress bar tied to real segment timestamps rather than elapsed time alone
- SRT/VTT subtitle export alongside plain `.txt`
- macOS/Linux real-device testing and platform-specific packaging

Check open issues first in case someone's already working on one — comment to claim it.

## Pull request checklist

- [ ] `pytest` passes
- [ ] `ruff check .` passes with no new warnings
- [ ] No new silent exception handling
- [ ] GUI changes only touch tkinter from the main thread
- [ ] Updated `CHANGELOG.md` under `[Unreleased]` if the change is user-facing
- [ ] Description explains *why*, not just *what*
