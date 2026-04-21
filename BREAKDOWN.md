# VideoTranscriber — Breakdown
**Created:** 2026-04-21
**Location:** `C:\Users\computer\Desktop\AI\VideoTranscriber\`
**Language/Stack:** Python 3.11 + faster-whisper + CustomTkinter + ffmpeg

---

## 1. What It Does
Standalone desktop/CLI tool that transcribes local video (.mp4) and audio (.wav, .mp3, etc.) files to timestamped `.txt` files using Whisper running entirely offline. Designed for 15–30 minute development log recordings. Output is clean text suitable for pasting into an LLM. No cloud API, no API key, no data leaves the machine.

## 2. How To Run It
- **Install:** `uv pip install faster-whisper customtkinter` + ffmpeg on PATH
- **GUI:** `python transcribe_gui.py`
- **CLI:** `python transcribe_video.py devlog.mp4 [--model small] [--no-timestamps]`
- **Exe (Windows):** Run `build_exe.bat` → `dist\VideoTranscriber.exe`
- **Requirements:** Python 3.10+, ffmpeg, faster-whisper≥1.0, customtkinter≥5.2

## 3. Architecture & File Structure
```
VideoTranscriber/
├── transcribe_video.py   # Core transcription logic + CLI entry point
├── transcribe_gui.py     # CustomTkinter GUI — imports from transcribe_video.py
├── requirements.txt      # faster-whisper, customtkinter
├── build_exe.bat         # Windows: PyInstaller one-file exe
├── README.md             # GitHub front page
├── TUTORIAL.md           # End-user install guide (all 5 platforms)
├── BREAKDOWN.md          # This file
└── HANDOFF.md            # AI-to-AI / co-worker handoff
```

**Data flow:**
`input_path (.mp4/.wav/...)` → `transcribe_video.transcribe()` → `faster_whisper.WhisperModel.transcribe()` → lazy segment generator → optional `on_segment(count, text)` callback → format timestamp + text per segment → write `.txt` to same folder

**GUI data flow:**
`App._browse()` → set file path → `App._start_transcribe()` → background thread → `transcribe(..., on_segment=lambda: self.after(0, update_status))` → `App._on_done()` on main thread → update preview + enable buttons

## 4. Key Decisions & Why
- **`faster-whisper` over `openai-whisper`**: CTranslate2 backend is 4× faster, uses half the RAM, no PyTorch/CUDA required. Same model files, same model names. Already established in this workspace.
- **No moviepy for .mp4**: `faster-whisper` calls ffmpeg internally for audio decoding — passing an .mp4 path directly works without a manual extraction step.
- **Default model `small`**: Dev logs contain technical vocabulary (function names, library names, CLI flags). The `base` model mishears these often. `small` is the sweet spot — ~3–4 min for 30 min audio on CPU.
- **GPU auto-detect with CPU fallback**: `device="auto"` is tried first; on Windows without CUDA 12 libs installed (common), a `RuntimeError` fires during the first encode. The `_run()` helper detects this by keyword-matching the error string and retries with `device="cpu", compute_type="int8"`. No user config needed.
- **Importable core**: `transcribe_video.py` is designed to be `import`-ed by the GUI. The crash logger `install()` is only called in the CLI `main()` path, not at module import time.
- **`on_segment` callback**: Allows the GUI to receive live progress updates during transcription without the core knowing anything about the GUI (clean separation). The GUI posts updates via `self.after(0, ...)` for thread safety.
- **`threading.Thread(daemon=True)`**: Transcription runs in a background daemon thread so the GUI stays responsive. All UI updates come back through `self.after(0, ...)`.
- **PyInstaller `--onefile --windowed`**: Single-exe output suppresses the console window on launch. `--collect-data customtkinter` bundles CTk's theme JSON assets which PyInstaller misses by default.

## 5. Development Log

### 2026-04-21 — Initial creation
- Built `transcribe_video.py`: core + CLI, CUDA fallback, `on_segment` callback
- Built `transcribe_gui.py`: CustomTkinter dark GUI, threading, live status, preview pane
- Platforms tested: Windows (CPU fallback verified), CLI on .wav synthetic test files
- Known: GUI status color update uses winfo_children scan — could be simplified to direct widget reference in future
- Deferred: macOS/Linux/Pi/Android platform testing
