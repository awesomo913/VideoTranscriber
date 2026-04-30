#!/usr/bin/env python3
"""
transcribe_gui.py — Desktop GUI for VideoTranscriber.

Requires: customtkinter, faster-whisper, ffmpeg on PATH.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

sys.path.insert(0, str(Path(__file__).parent))
from transcribe_video import (
    SUPPORTED_EXTENSIONS, MODEL_SIZES, DEFAULT_MODEL,
    check_ffmpeg, collect_paths, default_transcript_output_dir,
    transcribe, transcribe_batch,
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

_MODEL_NOTES = {
    "tiny":     "real-time speed, lower accuracy",
    "base":     "very fast, decent accuracy",
    "small":    "fast, good accuracy (recommended)",
    "medium":   "high accuracy, ~2× real-time",
    "large-v3": "best quality, slower",
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VideoTranscriber")
        self.geometry("700x680")
        self.minsize(560, 560)
        self.resizable(True, True)

        self._output_path: Path | None = None
        self._paths: list[Path] = []
        self._running = False
        self._start_time = 0.0
        self._batch_file_idx = 0
        self._batch_total = 0

        self._build_ui()
        self._check_deps_on_start()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # ── Title bar ──────────────────────────────────────────────────
        title = ctk.CTkLabel(self, text="VideoTranscriber",
                             font=("Segoe UI", 22, "bold"), text_color=ACCENT)
        title.grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        sub = ctk.CTkLabel(
            self,
            text="Local offline transcription — powered by faster-whisper",
            font=("Segoe UI", 11), text_color="#8899aa",
        )
        sub.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        # ── File + options card ────────────────────────────────────────
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        card.grid(row=2, column=0, padx=16, pady=4, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # File queue row
        ctk.CTkLabel(card, text="Queue:", font=FONT_BODY).grid(
            row=0, column=0, padx=(14, 8), pady=(14, 6), sticky="nw")
        self._file_var = ctk.StringVar(value="No files — use buttons below")
        self._file_label = ctk.CTkLabel(
            card, textvariable=self._file_var,
            font=FONT_MONO, anchor="w", justify="left",
            text_color="#aabbcc", wraplength=380,
        )
        self._file_label.grid(row=0, column=1, padx=4, pady=(14, 6), sticky="ew")
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=(4, 14), pady=(14, 6), sticky="ne")
        ctk.CTkButton(btn_frame, text="File(s)…", width=80, font=FONT_BODY,
                      command=self._browse_files).pack(pady=2)
        ctk.CTkButton(btn_frame, text="Folder…", width=80, font=FONT_BODY,
                      command=self._browse_folder).pack(pady=2)
        ctk.CTkButton(btn_frame, text="Clear", width=80, font=FONT_BODY,
                      command=self._clear_queue, fg_color="#444", hover_color="#555").pack(pady=2)

        self._recursive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            card, text="Include subfolders (when using Folder…)",
            variable=self._recursive_var, font=("Segoe UI", 11),
        ).grid(row=1, column=1, columnspan=2, padx=4, pady=(0, 4), sticky="w")

        # Model row
        ctk.CTkLabel(card, text="Model:", font=FONT_BODY).grid(
            row=2, column=0, padx=(14, 8), pady=6, sticky="w")
        model_frame = ctk.CTkFrame(card, fg_color="transparent")
        model_frame.grid(row=2, column=1, columnspan=2, padx=4, pady=6, sticky="w")
        self._model_var = ctk.StringVar(value=DEFAULT_MODEL)
        ctk.CTkComboBox(model_frame, values=list(MODEL_SIZES.keys()),
                        variable=self._model_var, width=130, font=FONT_BODY,
                        state="readonly").pack(side="left")
        self._model_hint = ctk.CTkLabel(model_frame, text="", font=("Segoe UI", 11),
                                        text_color="#8899aa")
        self._model_hint.pack(side="left", padx=(10, 0))
        self._model_var.trace_add("write", self._update_model_hint)
        self._update_model_hint()

        # Output dir row
        ctk.CTkLabel(card, text="Save to:", font=FONT_BODY).grid(
            row=3, column=0, padx=(14, 8), pady=6, sticky="w")
        out_row = ctk.CTkFrame(card, fg_color="transparent")
        out_row.grid(row=3, column=1, columnspan=2, padx=4, pady=6, sticky="ew")
        out_row.grid_columnconfigure(0, weight=1)
        self._out_dir_var = ctk.StringVar(value=str(default_transcript_output_dir()))
        ctk.CTkLabel(out_row, textvariable=self._out_dir_var,
                     font=("Segoe UI", 11), anchor="w", text_color="#aabbcc",
                     wraplength=320).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(out_row, text="Change…", width=80, font=("Segoe UI", 11),
                      height=28, command=self._browse_out_dir).grid(
            row=0, column=1, padx=(8, 14))

        # Timestamps row
        ctk.CTkLabel(card, text="Output:", font=FONT_BODY).grid(
            row=4, column=0, padx=(14, 8), pady=(6, 14), sticky="w")
        self._ts_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Include [HH:MM:SS] timestamps",
                        variable=self._ts_var, font=FONT_BODY).grid(
            row=4, column=1, padx=4, pady=(6, 14), sticky="w")

        # ── Transcribe button ──────────────────────────────────────────
        self._btn = ctk.CTkButton(self, text="Transcribe", height=42,
                                  font=("Segoe UI", 15, "bold"),
                                  command=self._start_transcribe)
        self._btn.grid(row=3, column=0, padx=16, pady=10, sticky="ew")

        # ── Status + progress ──────────────────────────────────────────
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.grid(row=4, column=0, padx=16, pady=(0, 2), sticky="ew")
        status_row.grid_columnconfigure(0, weight=1)

        self._status_var = ctk.StringVar(value="Ready.")
        self._status_label = ctk.CTkLabel(
            status_row, textvariable=self._status_var,
            font=("Segoe UI", 12), anchor="w",
        )
        self._status_label.grid(row=0, column=0, sticky="ew")

        self._elapsed_var = ctk.StringVar(value="")
        ctk.CTkLabel(status_row, textvariable=self._elapsed_var,
                     font=("Segoe UI", 11), text_color="#8899aa").grid(
            row=0, column=1, padx=(8, 4))

        self._eta_var = ctk.StringVar(value="")
        ctk.CTkLabel(status_row, textvariable=self._eta_var,
                     font=("Segoe UI", 11), text_color=ACCENT).grid(
            row=0, column=2, padx=(0, 0))

        self._progress = ctk.CTkProgressBar(self, mode="determinate")
        self._progress.grid(row=5, column=0, padx=16, pady=(2, 8), sticky="ew")
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

        self._preview = ctk.CTkTextbox(self, font=FONT_MONO, height=160,
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
            return
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            self._set_status("⚠ faster-whisper not installed. Run: uv pip install faster-whisper",
                             color=WARNING)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _add_paths(self, new_paths: list[Path]) -> None:
        seen = {p.resolve() for p in self._paths}
        skipped_names: list[str] = []
        for p in new_paths:
            if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                skipped_names.append(p.name)
                continue
            r = p.resolve()
            if r not in seen:
                seen.add(r)
                self._paths.append(p)
        if skipped_names:
            cap = 14
            tail = "\n…" if len(skipped_names) > cap else ""
            messagebox.showwarning(
                "Unsupported file type",
                "Skipped — extension not supported:\n\n"
                + "\n".join(skipped_names[:cap]) + tail,
            )
        self._refresh_queue_label()
        self._set_status("Ready." if self._paths else "No files in queue.")

    def _refresh_queue_label(self) -> None:
        if not self._paths:
            self._file_var.set("No files — use File(s)… or Folder…")
            return
        if len(self._paths) == 1:
            self._file_var.set(str(self._paths[0]))
            return
        lines = [str(p) for p in self._paths[:2]]
        rest = len(self._paths) - 2
        if rest > 0:
            lines.append(f"… and {rest} more ({len(self._paths)} total)")
        self._file_var.set("\n".join(lines))

    def _clear_queue(self) -> None:
        self._paths = []
        self._refresh_queue_label()
        self._set_status("Queue cleared.")

    def _browse_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select one or more video/audio files",
            filetypes=FILTER_EXTS,
        )
        if paths:
            self._add_paths([Path(p) for p in paths])

    def _browse_folder(self) -> None:
        d = filedialog.askdirectory(title="Select folder with media files")
        if not d:
            return
        skipped: list[Path] = []
        try:
            found = collect_paths(
                [],
                directory=Path(d),
                recursive=self._recursive_var.get(),
                folder_skipped_media=skipped,
            )
        except OSError as exc:
            messagebox.showerror("Folder", str(exc))
            return
        if not found:
            hint = ""
            if skipped:
                exts = sorted({p.suffix.lower() for p in skipped if p.suffix})
                ext_part = ", ".join(exts[:6]) if exts else "unknown"
                hint = (f"\n\nFound {len(skipped)} other file(s) — extensions: {ext_part}"
                        f"{' …' if len(exts) > 6 else ''}.")
            messagebox.showinfo("Folder", "No supported media files in that folder." + hint)
            return
        self._add_paths(found)
        if skipped:
            cap = 12
            sample = "\n".join(p.name for p in skipped[:cap])
            extra = f"\n… and {len(skipped) - cap} more" if len(skipped) > cap else ""
            messagebox.showinfo(
                "Folder — some files not queued",
                f"Added {len(found)} file(s). These {len(skipped)} file(s) were not "
                f"(unsupported extension):\n\n{sample}{extra}",
            )

    def _browse_out_dir(self) -> None:
        d = filedialog.askdirectory(title="Select output folder for transcripts")
        if d:
            self._out_dir_var.set(d)

    def _update_model_hint(self, *_):
        model = self._model_var.get()
        size = MODEL_SIZES.get(model, "")
        self._model_hint.configure(
            text=f"~{size} — {_MODEL_NOTES.get(model, '')}"
        )

    def _start_transcribe(self):
        if self._running:
            return
        if not self._paths:
            messagebox.showwarning(
                "No files",
                "Add one or more files (File(s)…), or all files in a folder (Folder…).",
            )
            return
        self._running = True
        self._output_path = None
        self._batch_file_idx = 0
        self._batch_total = 0
        self._btn.configure(state="disabled", text="Transcribing…")
        self._copy_btn.configure(state="disabled")
        self._open_btn.configure(state="disabled")
        self._set_preview("")
        self._progress.configure(mode="determinate")
        self._progress.set(0)
        self._set_status("Loading model…")
        self._start_time = time.monotonic()
        self._tick()
        paths = [p.resolve() for p in self._paths]
        out_dir = Path(self._out_dir_var.get())
        threading.Thread(
            target=self._run_transcribe, args=(paths, out_dir), daemon=True
        ).start()

    def _tick(self) -> None:
        if not self._running:
            return
        elapsed = time.monotonic() - self._start_time
        m, s = divmod(int(elapsed), 60)
        self._elapsed_var.set(f"⏱ {m:02d}:{s:02d}")
        self.after(1000, self._tick)

    def _run_transcribe(self, paths: list[Path], out_dir: Path) -> None:
        _last_seg = [0.0]
        _last_prog = [0.0]

        def on_seg(count: int, text: str) -> None:
            now = time.monotonic()
            if now - _last_seg[0] < 0.35:
                return
            _last_seg[0] = now
            self.after(0, self._set_status, f"Segment {count}: {text[:55]}…")

        def on_file(i: int, total: int, p: Path) -> None:
            def _update():
                self._batch_file_idx = i - 1
                self._batch_total = total
                self._set_status(f"File {i}/{total}: {p.name}")
            self.after(0, _update)

        def on_progress(current_sec: float, total_sec: float) -> None:
            now = time.monotonic()
            if now - _last_prog[0] < 0.25:
                return
            _last_prog[0] = now
            self.after(0, self._on_progress_update, current_sec, total_sec)

        try:
            if len(paths) == 1:
                out = transcribe(
                    input_path=paths[0],
                    model_name=self._model_var.get(),
                    timestamps=self._ts_var.get(),
                    on_segment=on_seg,
                    output_dir=out_dir,
                    on_progress=on_progress,
                )
                self.after(0, self._on_done, out)
            else:
                res = transcribe_batch(
                    paths=paths,
                    model_name=self._model_var.get(),
                    timestamps=self._ts_var.get(),
                    on_segment=on_seg,
                    on_file=on_file,
                    output_dir=out_dir,
                    on_progress=on_progress,
                )
                self.after(0, self._on_batch_done, res)
        except Exception as exc:
            self.after(0, self._on_error, str(exc))

    def _on_progress_update(self, current_sec: float, total_sec: float) -> None:
        if not self._running or total_sec <= 0:
            return
        file_fraction = min(current_sec / total_sec, 1.0)
        if self._batch_total > 0:
            overall = (self._batch_file_idx + file_fraction) / self._batch_total
        else:
            overall = file_fraction
        self._progress.set(min(overall, 1.0))
        elapsed = time.monotonic() - self._start_time
        if overall > 0.02 and elapsed > 1.0:
            eta_secs = max(elapsed / overall - elapsed, 0)
            m, s = divmod(int(eta_secs), 60)
            self._eta_var.set(f"ETA {m:02d}:{s:02d}")

    def _on_batch_done(self, res: list[tuple[Path, Exception | None]]) -> None:
        failed = [(p, e) for p, e in res if e is not None]
        ok = [p for p, e in res if e is None]
        self._finish()
        if not ok and failed:
            self._on_error("; ".join(f"{p.name}: {e}" for p, e in failed))
            return
        if failed:
            self._set_status(
                f"Done with errors: {len(ok)} ok, {len(failed)} failed.",
                color=WARNING,
            )
            messagebox.showwarning(
                "Batch finished",
                f"{len(ok)} succeeded, {len(failed)} failed.\n"
                + "\n".join(f"• {p.name}: {e}" for p, e in failed[:8]),
            )
        else:
            self._set_status(f"All {len(ok)} file(s) transcribed.", color=SUCCESS)
        last_txt = next((p for p in reversed(ok) if p.suffix == ".txt"), None)
        if last_txt and last_txt.exists():
            self._output_path = last_txt
            self._copy_btn.configure(state="normal")
            self._open_btn.configure(state="normal")
            try:
                self._set_preview(last_txt.read_text(encoding="utf-8"))
            except OSError:
                pass
        else:
            self._copy_btn.configure(state="normal")
            self._open_btn.configure(state="normal")
            self._set_preview("\n\n".join(f"✓ {p.name}" for p in ok) if ok else "")

    def _on_done(self, output_path: Path) -> None:
        self._output_path = output_path
        self._finish()
        self._copy_btn.configure(state="normal")
        self._open_btn.configure(state="normal")
        self._set_status(f"Done — saved to {output_path}", color=SUCCESS)
        try:
            self._set_preview(output_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    def _on_error(self, msg: str) -> None:
        self._finish(success=False)
        self._set_status(f"Error: {msg}", color=ERROR)

    def _finish(self, success: bool = True) -> None:
        self._running = False
        self._elapsed_var.set("")
        self._eta_var.set("")
        self._progress.set(1.0 if success else 0.0)
        self._btn.configure(state="normal", text="Transcribe")

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
        self._status_label.configure(text_color=color)

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
