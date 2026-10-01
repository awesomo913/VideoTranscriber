# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-09-30

### Fixed

- `--combined`/`--combined-only` now write the merged transcript under `--out-dir` by default, instead of always defaulting to the Desktop — so the merged file lands next to the other transcripts when you've chosen a different output folder.
- Re-transcribing the same file twice into a folder that already has both the plain `.txt` and the hash-suffixed backup no longer silently overwrites the second one — the app now keeps counting up (`_2`, `_3`, …) until it finds a free filename, so nothing you already saved gets clobbered.
- GPU detection is sturdier: if loading the Whisper model itself fails because CUDA libraries are missing (not just a failure partway through transcribing), it now falls back to CPU the same way, logs the real underlying error for troubleshooting, and shows a calm "No compatible GPU found — using CPU" note instead of a scary-looking warning. On machines with no CUDA device at all, it skips the doomed GPU attempt entirely and goes straight to CPU.

### Docs

- Corrected a false claim that macOS gets GPU acceleration via Apple's MPS/Metal backend — the underlying engine (CTranslate2) only supports CPU or NVIDIA CUDA, so Macs always transcribe on CPU.
- Reworded "silently falls back to CPU" to "automatically falls back to CPU (noted in the log)" so it's clear the fallback is visible in the app's log, not hidden.
- Noted honestly that automated testing (CI) only runs on Windows; macOS and Linux support is community-tested, not CI-covered.

## [1.0.0] - 2026-09-30

### Added

- Offline, local transcription of video and audio files to timestamped `.txt` using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (no cloud API, no account, no API key).
- Supported formats: `.mp4 .mp3 .wav .m4a .webm .ogg .flac .aac .mpeg .mov .mkv .avi`.
- Desktop GUI (`transcribe_gui.py`) built with CustomTkinter: file/folder pickers, model selector, output folder, live segment progress, ETA, output preview, copy-to-clipboard, open-folder.
- CLI (`transcribe_video.py`): single file, multiple files, `--dir` / `--recursive` folder scanning, `--model`, `--no-timestamps`, `--out-dir`, `--combined` / `--combined-only` / `--combined-out` merged-transcript output.
- Selectable Whisper model: tiny, base, small (default), medium, large-v3.
- Automatic GPU detection with silent CPU fallback if CUDA libraries are missing.
- Batch mode shares one model load across a queue of files.
- Portable single-file `VideoTranscriber.exe` distributed via GitHub Releases, built by GitHub Actions on tag with an attached `SHA256SUMS.txt`.

### Fixed

- Removed the hard requirement to have a system `ffmpeg`/`ffprobe` install on `PATH`. faster-whisper already decodes media through [PyAV](https://github.com/PyAV-Org/PyAV), which ships its own bundled FFmpeg libraries — the app now checks for an audio stream using PyAV directly instead of shelling out to `ffprobe`, so a normal user no longer needs to install anything beyond the Python packages in `requirements.txt`.
