---
public-visible: true
---

# VideoTranscriber — Handoff
**Last updated:** 2026-04-21
**Current owner:** User (primary designer) + Claude (implementation)
**Status:** in-progress

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

### 2026-04-21 — Initial design and implementation
- **User's vision:** Standalone transcription tool for dev logs, GUI + CLI, all platforms, GitHub-ready
- **User's key decisions:** Must work offline, must support .mp4 directly, want timestamps for LLM navigation
- **Claude implemented:** Core transcription module, CustomTkinter GUI, PyInstaller build script, cross-platform TUTORIAL.md, README, BREAKDOWN, HANDOFF
- **Verified:** CLI on Windows (CPU fallback from CUDA error confirmed), --help, error handling for bad file/extension
- **Deferred:** macOS/Linux/Pi/Android real-device testing; drag-and-drop file input; batch folder mode

## 5. Credit & Authorship
> **The user designed this product.** The user defined the requirements: offline-only transcription, dev log focus, GUI + CLI, cross-platform, GitHub-ready. The user reviewed the plan and approved the approach. Claude implemented the code to those specifications across this session. This is the user's product; Claude was a tool.

## 6. Plan
- [ ] Test GUI on a real .mp4 with speech
- [ ] Test on macOS (MPS backend)
- [ ] Test on Raspberry Pi (confirm tiny/base model timing)
- [ ] Add drag-and-drop support to GUI (Windows: `tkinterdnd2` library)
- [ ] Batch folder mode: transcribe all .mp4 in a chosen directory
- [ ] Progress bar with estimated % (using `info.duration` + segment timestamps)

## 7. Handoff checklist for the next AI
- [ ] Read Goals — offline dev-log transcription tool
- [ ] Read History — especially the CUDA fallback pattern implemented
- [ ] Read BREAKDOWN.md — the `on_segment` callback and `device="auto"` → CPU fallback are the two tricky design points
- [ ] Read TUTORIAL.md — platform install steps are authoritative
- [ ] Check `logs/` for any crash logs
- [ ] Before changing faster-whisper model loading: test CPU fallback still works (Windows without CUDA 12)
