@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  build_exe.bat — Build VideoTranscriber.exe for Windows
REM
REM  Requirements (run once before building):
REM    uv pip install -r requirements-dev.txt
REM
REM  Output: dist\VideoTranscriber.exe
REM  NOTE: The .exe does NOT bundle model weights. On first run, the app
REM        downloads them (~480 MB for 'small'). Internet required once.
REM ─────────────────────────────────────────────────────────────────────────

python build.py
