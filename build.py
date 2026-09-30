"""Build VideoTranscriber.exe — a standalone Windows executable.

Builds with whatever interpreter runs this script. Point it at a dedicated
clean venv so the bundle doesn't drag unrelated packages from a shared
environment:

    .venv\\Scripts\\python.exe build.py

Output: dist\\VideoTranscriber.exe only (no copies elsewhere — CI picks it up
from dist\\ for releases; a local install is the user's own choice).

Note: model weights are NOT bundled into the exe. They download from Hugging
Face on first run (~480 MB for the default 'small' model).
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "VideoTranscriber"
MAIN = os.path.join(HERE, "transcribe_gui.py")

# Hidden imports that PyInstaller's static import-analysis misses.
_HIDDEN_IMPORTS = [
    "ctypes",
    "ctypes.util",
]

_COLLECT_ALL = [
    # faster-whisper's transcription backend (ctranslate2 + tokenizers + VAD
    # models) ships data files and native binaries that import-analysis misses.
    "faster_whisper",
    # PyAV bundles its own FFmpeg shared libraries — collected in full so the
    # exe can decode media without a system ffmpeg install.
    "av",
]

_COLLECT_DATA = [
    # customtkinter's theme JSON assets are not picked up by default.
    "customtkinter",
]


def build_exe() -> None:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm",
        "--onefile", "--windowed",
        f"--name={APP_NAME}",
    ]
    for mod in _HIDDEN_IMPORTS:
        args.append(f"--hidden-import={mod}")
    for pkg in _COLLECT_ALL:
        args.append(f"--collect-all={pkg}")
    for pkg in _COLLECT_DATA:
        args.append(f"--collect-data={pkg}")
    args.append(MAIN)

    print("[build] Running PyInstaller (this may take 1-2 minutes)...")
    # Timeout so a hung PyInstaller fails loudly instead of blocking forever;
    # 20 minutes comfortably covers slow machines / cold caches.
    subprocess.check_call(args, cwd=HERE, timeout=1200)
    print("[build] PyInstaller complete.")


def main() -> None:
    build_exe()

    exe_path = os.path.join(HERE, "dist", f"{APP_NAME}.exe")
    if not os.path.isfile(exe_path):
        raise SystemExit(f"[build] FAILED: expected {exe_path} but it doesn't exist")
    size_mb = round(os.path.getsize(exe_path) / (1024 * 1024), 1)
    print(f"[build] OK -> {exe_path}  ({size_mb} MB)")


if __name__ == "__main__":
    main()
