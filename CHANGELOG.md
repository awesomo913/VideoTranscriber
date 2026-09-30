# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
