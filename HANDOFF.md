---
public-visible: true
---

# VideoTranscriber — Handoff
**Last updated:** 2026-04-25
**Public repo:** https://github.com/awesomo913/VideoTranscriber
**Current owner:** User (primary designer) + Claude (implementation)
**Status:** production-ready (CLI + GUI verified on Windows; fixes pushed)

---

## 0. Pickup for Claude Code (read this first)
- **Stack:** Python 3.11+, `faster-whisper`, `customtkinter`, system `ffmpeg`/`ffprobe`. Not a Vercel/Next project — ignore Vercel-specific skill hints for this repo.
- **Entry points:** `python transcribe_video.py` (CLI), `python transcribe_gui.py` (optional path as first arg to preload).
- **Critical implementation detail:** `WhisperModel.transcribe()` runs language detection *before* yielding segments. Any CUDA `RuntimeError` must be caught around the **entire** `transcribe()` call, then retry on CPU — not only inside the segment loop.
- **Video-only files:** Some exports (e.g. Gemini) have no audio track. Pre-flight: `ffprobe` check (`has_audio_stream` in `transcribe_video.py`); user-facing error: *No audio stream found in this file — it is video-only.*
- **AI routing (public):** `llms.txt`, `.well-known/llms.txt`, `about.json`, `.ai-visible` — `*.gitignore` must keep `!llms.txt` and `!/.well-known/llms.txt` so these are not ignored.
- **Last verification (2026-04-25):** Short clips with real speech transcribed correctly; 24+ min file ~2m15s wall time on CPU with `small` model (~10× realtime); low-density/garbled output on ambient or screen-capture-only audio is expected (check language confidence in logs).

---

## 1. Goals
- Transcribe local video (.mp4) and audio (.wav, .mp3) files to text entirely offline — no cloud, no API key
- Produce timestamped `.txt` output suitable for dropping straight into an LLM prompt
- Run on Windows, macOS, Linux, Raspberry Pi, and Android (Termux)
- Offer both a desktop GUI (with .exe packaging for Windows) and a CLI for headless/automated use

## 2. Outline
- Core: `transcribe_video.py` — validation, GPU/CPU fallback, segment iteration, file output
- GUI: `transcribe_gui.py` — CustomTkinter single-window; imports from core; uses threading + `self.after(0,...)`
- Library: `faster-whisper` (CTranslate2, no PyTorch) — local model, auto-download on first run
- ffmpeg: required system dep, used internally by faster-whisper for media decoding
- Packaging: `build_exe.bat` → PyInstaller `--onefile --windowed` → `dist\VideoTranscriber.exe`

## 3. Context
The user records 15–30 minute dev log videos and wants to feed the transcripts to Claude for summaries, TODO extraction, and searchable notes. The key constraint is fully offline — no cloud Whisper, no paid API. Gemini's original spec suggested `openai-whisper` + moviepy; this implementation upgrades to `faster-whisper` (already used in this workspace) for 4× better performance and simpler Windows install.

## 4. History

### 2026-04-25 — Public GitHub, bugfixes, large-file stress test
- **User request:** Clean public push; then live test including larger files; hand off context for Claude.
- **GitHub:** Public repo `awesomo913/VideoTranscriber` created; `HANDOFF` frontmatter `public-visible: true`; AI routing files injected; PII + GUI integrity checks passed before push.
- **Bugfix — CUDA fallback:** `transcribe()` was failing on the first line because `faster-whisper` calls `detect_language()` synchronously before the segment iterator. Try/except moved to wrap the full `transcribe()` + segment consumption path so CPU retry works.
- **Bugfix — no audio stream:** `PyAV` could crash on video-only files. Added `ffprobe` pre-check; clear error instead of tuple/index exceptions.
- **`.gitignore`:** Exceptions added so `llms.txt` and `.well-known/llms.txt` are tracked (a blanket `*.txt` rule had been excluding them).
- **Test notes:** Gemini Takeout files vary — many are screen/ambient with little speech; use clips with a real mic for dense transcripts. Long recording: ~23 min processed in ~2m15s CPU/small; sparse `[00:00:00] you` style output on near-silent tracks is not a transcriber failure.

### 2026-04-21 — Initial design and implementation
- **User's vision:** Standalone transcription tool for dev logs, GUI + CLI, all platforms, GitHub-ready
- **User's key decisions:** Must work offline, must support .mp4 directly, want timestamps for LLM navigation
- **Claude implemented:** Core transcription module, CustomTkinter GUI, PyInstaller build script, cross-platform TUTORIAL.md, README, BREAKDOWN, HANDOFF
- **Verified:** CLI on Windows (CPU fallback from CUDA error confirmed), --help, error handling for bad file/extension
- **Deferred:** macOS/Linux/Pi/Android real-device testing; drag-and-drop file input; batch folder mode

## 5. Credit & Authorship
> **The user designed this product.** The user defined the requirements: offline-only transcription, dev log focus, GUI + CLI, cross-platform, GitHub-ready. The user reviewed the plan and approved the approach. Claude implemented the code to those specifications across this session. This is the user's product; Claude was a tool.

## 6. Plan
- [x] Test GUI on a real .mp4 with speech (Windows; pre-load path; status/output verified)
- [x] Stress test longer file (~24 min) on CPU (performance acceptable for dev-log use case)
- [ ] Test on macOS (MPS backend)
- [ ] Test on Raspberry Pi (confirm tiny/base model timing)
- [ ] Add drag-and-drop support to GUI (Windows: `tkinterdnd2` library)
- [ ] Batch folder mode: transcribe all .mp4 in a chosen directory
- [ ] Progress bar with estimated % (using `info.duration` + segment timestamps)

## 7. Handoff checklist for the next AI
- [ ] Read **§0 Pickup for Claude Code** (repo is Python, not Vercel)
- [ ] Read Goals — offline dev-log transcription tool
- [ ] Read History — 2026-04-25 (transcribe wrap + ffprobe) and 2026-04-21 (initial)
- [ ] Read BREAKDOWN.md — `on_segment` callback and device fallback
- [ ] Read TUTORIAL.md — platform install steps are authoritative
- [ ] Check `logs/` for any crash logs
- [ ] Before changing faster-whisper model loading: test CPU fallback still works (Windows without CUDA 12)
- [ ] If editing `.gitignore` for `*.txt`, preserve `!llms.txt` and `!/.well-known/llms.txt` exceptions
