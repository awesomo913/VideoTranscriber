#!/usr/bin/env python3
"""
transcribe_gui.py — Desktop GUI for VideoTranscriber.

Requires: customtkinter, faster-whisper, ffmpeg on PATH.
"""

import os
import subprocess
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

# Allow running from the project folder or as a PyInstaller bundle
sys.path.insert(0, str(Path(__file__).parent))
from transcribe_video import (
    SUPPORTED_EXTENSIONS, MODEL_SIZES, DEFAULT_MODEL,
    check_ffmpeg, transcribe,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT = "#4fc3f7"
SUCCESS = "#4ecca3"
ERROR = "#e94560"
WARNING = "#f0a500"
BG_CARD = "#1e2a3a"
FONT_BODY = ("Segoe UI", 13)
FONT_MONO = ("Consolas", 12)

FILTER_EXTS = [("Media files", " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))),
               ("All files", "*.*")]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VideoTranscriber")
        self.geometry("680x580")
        self.minsize(560, 480)
        self.resizable(True, True)

        self._output_path: Path | None = None
        self._running = False

        self._build_ui()
        self._check_deps_on_start()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # ── Title bar ──────────────────────────────────────────────────
        title = ctk.CTkLabel(self, text="VideoTranscriber",
                             font=("Segoe UI", 22, "bold"), text_color=ACCENT)
        title.grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        sub = ctk.CTkLabel(self, text="Local offline transcription — no cloud, no API key",
                           font=("Segoe UI", 11), text_color="#8899aa")
        sub.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        # ── File + options card ────────────────────────────────────────
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        card.grid(row=2, column=0, padx=16, pady=4, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # File row
        ctk.CTkLabel(card, text="File:", font=FONT_BODY).grid(
            row=0, column=0, padx=(14, 8), pady=(14, 6), sticky="w")
        self._file_var = ctk.StringVar(value="No file selected")
        self._file_label = ctk.CTkLabel(card, textvariable=self._file_var,
                                        font=FONT_MONO, anchor="w",
                                        text_color="#aabbcc")
        self._file_label.grid(row=0, column=1, padx=4, pady=(14, 6), sticky="ew")
        ctk.CTkButton(card, text="Browse…", width=90, font=FONT_BODY,
                      command=self._browse).grid(row=0, column=2, padx=(4, 14), pady=(14, 6))

        # Model row
        ctk.CTkLabel(card, text="Model:", font=FONT_BODY).grid(
            row=1, column=0, padx=(14, 8), pady=6, sticky="w")
        model_frame = ctk.CTkFrame(card, fg_color="transparent")
        model_frame.grid(row=1, column=1, columnspan=2, padx=4, pady=6, sticky="w")
        self._model_var = ctk.StringVar(value=DEFAULT_MODEL)
        ctk.CTkComboBox(model_frame, values=list(MODEL_SIZES.keys()),
                        variable=self._model_var, width=130, font=FONT_BODY,
                        state="readonly").pack(side="left")
        self._model_hint = ctk.CTkLabel(model_frame, text="", font=("Segoe UI", 11),
                                        text_color="#8899aa")
        self._model_hint.pack(side="left", padx=(10, 0))
        self._model_var.trace_add("write", self._update_model_hint)
        self._update_model_hint()

        # Timestamps row
        ctk.CTkLabel(card, text="Output:", font=FONT_BODY).grid(
            row=2, column=0, padx=(14, 8), pady=(6, 14), sticky="w")
        self._ts_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Include [HH:MM:SS] timestamps",
                        variable=self._ts_var, font=FONT_BODY).grid(
            row=2, column=1, padx=4, pady=(6, 14), sticky="w")

        # ── Transcribe button ──────────────────────────────────────────
        self._btn = ctk.CTkButton(self, text="Transcribe", height=42,
                                  font=("Segoe UI", 15, "bold"),
                                  command=self._start_transcribe)
        self._btn.grid(row=3, column=0, padx=16, pady=10, sticky="ew")

        # ── Status + progress ──────────────────────────────────────────
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.grid(row=4, column=0, padx=16, pady=(0, 4), sticky="ew")
        status_row.grid_columnconfigure(0, weight=1)
        self._status_var = ctk.StringVar(value="Ready.")
        ctk.CTkLabel(status_row, textvariable=self._status_var,
                     font=("Segoe UI", 12), anchor="w").grid(
            row=0, column=0, sticky="ew")
        self._progress = ctk.CTkProgressBar(self, mode="indeterminate")
        self._progress.grid(row=5, column=0, padx=16, pady=(0, 8), sticky="ew")
        self._progress.set(0)

        # ── Output preview ─────────────────────────────────────────────
        out_label = ctk.CTkFrame(self, fg_color="transparent")
        out_label.grid(row=6, column=0, padx=16, pady=(4, 0), sticky="ew")
        out_label.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(out_label, text="Output preview:", font=("Segoe UI", 11),
                     text_color="#8899aa", anchor="w").grid(row=0, column=0, sticky="w")
        self._copy_btn = ctk.CTkButton(out_label, text="Copy all", width=80,
                                       font=("Segoe UI", 11), height=26,
                                       command=self._copy_output, state="disabled")
        self._copy_btn.grid(row=0, column=1, sticky="e")
        self._open_btn = ctk.CTkButton(out_label, text="Open folder", width=100,
                                       font=("Segoe UI", 11), height=26,
                                       command=self._open_folder, state="disabled")
        self._open_btn.grid(row=0, column=2, padx=(4, 0), sticky="e")

        self._preview = ctk.CTkTextbox(self, font=FONT_MONO, height=140,
                                       state="disabled", wrap="word",
                                       text_color="#ccddee")
        self._preview.grid(row=7, column=0, padx=16, pady=(4, 16), sticky="nsew")
        self.grid_rowconfigure(7, weight=1)

    # ------------------------------------------------------------------
    # Startup checks
    # ------------------------------------------------------------------

    def _check_deps_on_start(self):
        if not check_ffmpeg():
            self._set_status("⚠ ffmpeg not found — see TUTORIAL.md for install instructions.",
                             color=WARNING)
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            self._set_status("⚠ faster-whisper not installed. Run: uv pip install faster-whisper",
                             color=WARNING)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select video or audio file",
            filetypes=FILTER_EXTS,
        )
        if path:
            self._file_var.set(path)
            self._set_status("Ready.")

    def _update_model_hint(self, *_):
        model = self._model_var.get()
        size = MODEL_SIZES.get(model, "")
        notes = {
            "tiny":   "fastest, lower accuracy",
            "base":   "fast, decent accuracy",
            "small":  "recommended for dev logs",
            "medium": "high accuracy, slower",
            "large-v3": "best quality, slow",
        }
        self._model_hint.configure(text=f"~{size} — {notes.get(model, '')}")

    def _start_transcribe(self):
        if self._running:
            return
        path_str = self._file_var.get()
        if not path_str or path_str == "No file selected":
            messagebox.showwarning("No file", "Please browse to a video or audio file first.")
            return
        self._running = True
        self._output_path = None
        self._btn.configure(state="disabled", text="Transcribing…")
        self._copy_btn.configure(state="disabled")
        self._open_btn.configure(state="disabled")
        self._set_preview("")
        self._progress.start()
        self._set_status("Starting…")
        threading.Thread(target=self._run_transcribe,
                         args=(Path(path_str),), daemon=True).start()

    def _run_transcribe(self, input_path: Path):
        def on_seg(count: int, text: str):
            self.after(0, self._set_status, f"Segment {count}: {text[:50]}…")

        try:
            out = transcribe(
                input_path=input_path,
                model_name=self._model_var.get(),
                timestamps=self._ts_var.get(),
                on_segment=on_seg,
            )
            self.after(0, self._on_done, out)
        except Exception as exc:
            self.after(0, self._on_error, str(exc))

    def _on_done(self, output_path: Path):
        self._running = False
        self._output_path = output_path
        self._progress.stop()
        self._progress.set(1)
        self._btn.configure(state="normal", text="Transcribe")
        self._copy_btn.configure(state="normal")
        self._open_btn.configure(state="normal")
        self._set_status(f"Done — saved to {output_path.name}", color=SUCCESS)
        try:
            text = output_path.read_text(encoding="utf-8")
            self._set_preview(text)
        except Exception:
            pass

    def _on_error(self, msg: str):
        self._running = False
        self._progress.stop()
        self._progress.set(0)
        self._btn.configure(state="normal", text="Transcribe")
        self._set_status(f"Error: {msg}", color=ERROR)

    def _copy_output(self):
        if self._output_path and self._output_path.exists():
            text = self._output_path.read_text(encoding="utf-8")
            self.clipboard_clear()
            self.clipboard_append(text)
            self._set_status("Copied to clipboard.", color=SUCCESS)

    def _open_folder(self):
        if self._output_path:
            folder = self._output_path.parent
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str = "#aabbcc"):
        self._status_var.set(text)
        # Find the status label widget and update its color
        for child in self.winfo_children():
            if isinstance(child, ctk.CTkFrame):
                for w in child.winfo_children():
                    if isinstance(w, ctk.CTkLabel) and w.cget("textvariable") == str(self._status_var):
                        w.configure(text_color=color)
                        return

    def _set_preview(self, text: str):
        self._preview.configure(state="normal")
        self._preview.delete("1.0", "end")
        if text:
            self._preview.insert("1.0", text)
        self._preview.configure(state="disabled")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
