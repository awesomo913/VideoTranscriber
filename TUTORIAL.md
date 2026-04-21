# VideoTranscriber — Tutorial
**Last updated:** 2026-04-21 (v1.0.0)

---

## 1. Quickstart

**What you'll accomplish:** Transcribe a video or audio file to a `.txt` file in under 5 minutes.

Jump to your platform:
- [Windows](#windows)
- [macOS](#macos)
- [Linux (x64/ARM64)](#linux)
- [Raspberry Pi](#raspberry-pi)
- [Android (Termux)](#android-termux)

---

## Platform Setup

### Windows

**Requirements:** Windows 10/11, Python 3.10+

**Step 1 — Install ffmpeg**
```powershell
winget install ffmpeg
```
Or download manually from https://ffmpeg.org/download.html and add the `bin/` folder to your PATH.

Verify: open a new terminal and run `ffmpeg -version`

**Step 2 — Install Python dependencies**
```powershell
uv pip install faster-whisper customtkinter
```
If you don't have `uv`: `pip install uv` first, then run the above.

**Step 3a — Run the GUI**
```powershell
python transcribe_gui.py
```
A dark-themed window opens. Click **Browse…**, select your file, choose a model, click **Transcribe**.

**Step 3b — Run the CLI**
```powershell
python transcribe_video.py devlog.mp4
```

**Step 4 (optional) — Build a standalone .exe**
```powershell
uv pip install pyinstaller
build_exe.bat
```
Output: `dist\VideoTranscriber.exe` — copy anywhere. ffmpeg must remain on PATH.

---

### macOS

**Requirements:** macOS 12+, Python 3.10+, [Homebrew](https://brew.sh)

**Step 1 — Install ffmpeg**
```bash
brew install ffmpeg
```

**Step 2 — Install Python dependencies**
```bash
pip install faster-whisper customtkinter
```

**Step 3a — Run the GUI**
```bash
python transcribe_gui.py
```

**Step 3b — Run the CLI**
```bash
python transcribe_video.py devlog.mp4
```

**Note on Apple Silicon (M1/M2/M3):** `faster-whisper` automatically uses the MPS GPU backend on macOS 13+ — transcription is fast without CUDA.

---

### Linux

**Requirements:** Ubuntu 20.04+ / Debian 11+ (or any distro with Python 3.10+)

**Step 1 — Install ffmpeg**
```bash
sudo apt update && sudo apt install ffmpeg python3-pip -y
```

**Step 2 — Install Python dependencies**
```bash
pip install faster-whisper customtkinter
```

**Step 3a — Run the GUI**

Requires a desktop environment (X11 or Wayland + Tk).
```bash
python transcribe_gui.py
```

**Step 3b — Run the CLI (headless / servers)**
```bash
python transcribe_video.py devlog.mp4
```

**NVIDIA GPU (optional):** Install CUDA 12 + cuDNN 9 for faster inference. `faster-whisper` detects the GPU automatically.

---

### Raspberry Pi

**Requirements:** Raspberry Pi 4 or 5, Raspberry Pi OS (64-bit), Python 3.10+

Raspberry Pi uses ARM CPU — no GPU acceleration. Use `tiny` or `base` model for reasonable speed.

**Step 1 — Install ffmpeg**
```bash
sudo apt update && sudo apt install ffmpeg -y
```

**Step 2 — Install Python dependencies**
```bash
pip install faster-whisper
# GUI optional — skip customtkinter on headless Pi
pip install customtkinter  # only if you have a desktop
```

**Step 3 — Transcribe (recommended: CLI)**
```bash
# Use 'tiny' model — 'small' can take 10+ min on Pi 4 CPU
python transcribe_video.py devlog.mp4 --model tiny
```

**Performance guide (Pi 4 — 4 GB RAM, 30 min audio):**
| Model | Time |
|-------|------|
| tiny | ~4 min |
| base | ~8 min |
| small | ~18 min |

**Tip:** Use `tmux` or `screen` so the job keeps running if you disconnect:
```bash
tmux new -s transcribe
python transcribe_video.py devlog.mp4 --model base
```

---

### Android (Termux)

**Requirements:** Android 9+, [Termux](https://f-droid.org/en/packages/com.termux/) (install from F-Droid, not the Play Store version)

**GUI is not supported on Android.** CLI only.

**Step 1 — Set up Termux**
```bash
pkg update && pkg upgrade -y
pkg install python ffmpeg -y
```

**Step 2 — Install faster-whisper**
```bash
pip install faster-whisper
```

**Step 3 — Copy your video file to Termux storage**
```bash
termux-setup-storage
# Then copy files to ~/storage/downloads/
```

**Step 4 — Transcribe**
```bash
# 'tiny' or 'base' only — 'small' may crash on low-RAM devices
python transcribe_video.py ~/storage/downloads/devlog.mp4 --model tiny
```

**Output** lands next to the input file in `~/storage/downloads/`.

---

## 2. Feature Walkthrough

### GUI — Browse & Transcribe
- **What it does:** Graphical window for picking files, choosing settings, and viewing output.
- **How:** Click **Browse…** → select a `.mp4` / `.wav` / `.mp3` → choose model → click **Transcribe**.
- **Progress:** The status bar shows each segment as it's processed (`Segment 14: function naming...`).
- **Output:** The text preview fills in when done. Click **Open folder** to jump to the `.txt` file, or **Copy all** to paste into an LLM.
- **Gotcha:** On first run for a new model, the app appears frozen for ~30 seconds while the model downloads. It's working — don't close it.

### CLI — Command Line
- **What it does:** Runs transcription from the terminal, prints progress, exits.
- **When to use:** Servers, automation, Raspberry Pi headless, batch scripts.
- **Example:**
  ```bash
  python transcribe_video.py 2026-04-21_devlog.mp4
  # Output: 2026-04-21_devlog.txt in the same folder
  ```

### Timestamps
- **What it does:** Prefixes each Whisper segment with `[HH:MM:SS]`.
- **When to use:** When you want to navigate long recordings — paste the text into Claude and ask "what was discussed around 00:12:00?".
- **Toggle:** GUI checkbox or CLI `--no-timestamps` flag.
- **Example output:**
  ```
  [00:00:00] Okay so today I'm going to work on the encounter table parser.
  [00:01:34] The issue is the bracket depth counter is off by one when structs nest.
  [00:03:12] Fixed it by using a stack instead of a simple integer counter.
  ```

### Model Selection
- **What it does:** Picks the Whisper model. Larger = more accurate, slower, more RAM.
- **Recommendation for dev logs:** `small` — handles technical vocabulary well at reasonable speed.
- **CLI flag:** `--model base` (or tiny / small / medium / large-v3)

---

## 3. Common Workflows

### Workflow: Transcribe a dev log for LLM input
1. Record your session to `.mp4` (OBS, Loom, etc.)
2. Run: `python transcribe_video.py 2026-04-21_session.mp4`
3. Open the `.txt` next to the video
4. Paste into Claude: *"Summarize this dev log and extract all TODOs"*

### Workflow: Batch transcribe a folder (CLI)
```bash
for f in *.mp4; do
    python transcribe_video.py "$f" --model small
done
```
Each `.mp4` gets a `.txt` next to it.

### Workflow: Plain text for search / storage
```bash
python transcribe_video.py session.mp4 --no-timestamps
```
Output is clean prose — easier to grep or copy-paste.

---

## 4. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ffmpeg not found` | ffmpeg not on PATH | Reinstall or add `bin/` to PATH. Open a **new** terminal after install. |
| App freezes after clicking Transcribe | Downloading model (first run) | Wait 30–60 seconds. Check network. |
| `cublas64_12.dll not found` | CUDA libs not installed | App auto-falls back to CPU — this is normal. You'll see a warning in logs. |
| `ImportError: No module named faster_whisper` | Package not installed | Run `uv pip install faster-whisper` |
| Output is empty / 0 segments | Audio has no speech (or too quiet) | Check the file plays sound. Try `--model small` for better detection. |
| Pi: very slow transcription | ARM CPU with large model | Use `--model tiny` or `--model base` on Raspberry Pi. |
| Android: `pip install` fails | Arch mismatch or missing wheel | Run `pkg install python-pip && pip install faster-whisper --no-binary :all:` |
| GUI doesn't open on Linux | Tkinter not installed | `sudo apt install python3-tk` |

---

## 5. FAQ

**Q: Does this send my audio to the internet?**
A: No. After the model downloads once (~480 MB), everything runs locally on your machine.

**Q: Can I use a GPU?**
A: Yes — CUDA (NVIDIA) on Windows/Linux, MPS on Apple Silicon Mac. The app auto-detects. If CUDA libs are missing, it silently falls back to CPU.

**Q: What languages does it support?**
A: All languages Whisper supports (~99). Language is auto-detected per file.

**Q: The .exe — does it bundle everything?**
A: The `.exe` bundles Python + all libraries. Model weights (~480 MB for `small`) are still downloaded at runtime on first use. ffmpeg must be on PATH.

**Q: Can I import this in my own Python script?**
A: Yes:
```python
from transcribe_video import transcribe
from pathlib import Path
out = transcribe(Path("devlog.mp4"), model_name="small", timestamps=True)
print(f"Written to {out}")
```

---

## 6. Changelog

### 2026-04-21 — v1.0.0
- Initial release
- GUI: file picker, model selector, timestamps toggle, segment progress, output preview
- CLI: `--model`, `--no-timestamps` flags
- Platforms: Windows (exe), macOS, Linux, Raspberry Pi (CLI), Android Termux (CLI)
- Auto CPU fallback when CUDA libs missing
