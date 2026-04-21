@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  build_exe.bat — Build VideoTranscriber.exe for Windows
REM
REM  Requirements (run once before building):
REM    uv pip install pyinstaller faster-whisper customtkinter
REM
REM  Output: dist\VideoTranscriber.exe
REM  NOTE: The .exe does NOT bundle model weights. On first run, the app
REM        downloads them (~480 MB for 'small'). Internet required once.
REM ─────────────────────────────────────────────────────────────────────────

echo Installing PyInstaller (if not present)...
uv pip install pyinstaller --quiet

echo Building VideoTranscriber.exe...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "VideoTranscriber" ^
  --collect-data customtkinter ^
  --collect-all faster_whisper ^
  --hidden-import ctypes ^
  --hidden-import ctypes.util ^
  transcribe_gui.py

if %ERRORLEVEL% == 0 (
    echo.
    echo SUCCESS — dist\VideoTranscriber.exe is ready.
    echo Copy it anywhere and run it. ffmpeg must still be on PATH.
) else (
    echo.
    echo BUILD FAILED — check output above for errors.
)
pause
