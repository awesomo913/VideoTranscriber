# VideoTranscriber

Offline, free, local video and audio transcription using [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No cloud APIs. No API keys. Works without internet after the first model download.

Transcribes `.mp4`, `.mp3`, `.wav`, `.m4a`, `.webm`, `.ogg`, `.flac`, `.aac` into a `.txt` file saved next to the input. Designed for 15–30 minute development logs.

---

## Quick start

```bash
# 1. Install ffmpeg
#    Windows:  winget install ffmpeg
#    Mac:      brew install ffmpeg
#    Linux:    sudo apt install ffmpeg

# 2. Install Python deps
uv pip install faster-whisper customtkinter

# 3a. GUI
python transcribe_gui.py

# 3b. CLI
python transcribe_video.py devlog.mp4
python transcribe_video.py devlog.mp4 --model base --no-timestamps
```

See [TUTORIAL.md](TUTORIAL.md) for full platform-specific setup (Windows / macOS / Linux / Raspberry Pi / Android).

---

## Features

| Feature | Detail |
|---------|--------|
| **Fully offline** | Runs on your machine — nothing leaves your device |
| **Video + audio** | `.mp4` handled directly — no manual audio extraction |
| **Timestamps** | `[00:01:42] segment text` format, toggleable |
| **Auto CPU fallback** | Detects GPU; silently falls back to CPU if CUDA libs missing |
| **Model choice** | tiny / base / **small** (default) / medium / large-v3 |
| **GUI + CLI** | Desktop window or command line |
| **Windows .exe** | Single-file executable via `build_exe.bat` |

---

## Models

| Model | Size | Speed (30 min on CPU) | Best for |
|-------|------|----------------------|----------|
| tiny | 75 MB | ~1 min | Quick drafts |
| base | 145 MB | ~2 min | General use |
| **small** | **480 MB** | **~3–4 min** | **Dev logs (default)** |
| medium | 1.5 GB | ~8 min | High accuracy |
| large-v3 | 3 GB | ~15 min | Best quality |

---

## Building the .exe (Windows)

```bat
build_exe.bat
```

Output: `dist\VideoTranscriber.exe` — copy anywhere and run. ffmpeg must still be on PATH. Model weights download on first run (~480 MB for small).

---

## License

MIT

## TL;DR

---

## Publisher

Published by **Revolutionary Designs**.  
GitHub: https://github.com/awesomo913  
Contact: solidgoldbarsinmycloset@gmail.com  <!-- pii-ok: official brand contact -->

