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
    check_ffmpeg, collect_paths, transcribe, transcribe_batch,
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
        self._paths: list[Path] = []
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

        # File queue row
        ctk.CTkLabel(card, text="Queue:", font=FONT_BODY).grid(
            row=0, column=0, padx=(14, 8), pady=(14, 6), sticky="nw")
        self._file_var = ctk.StringVar(value="No files — use buttons below")
        self._file_label = ctk.CTkLabel(
            card, textvariable=self._file_var,
            font=FONT_MONO, anchor="w", justify="left",
            text_color="#aabbcc", wraplength=400,
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

        # Subfolder option (for folder add)
        self._recursive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            card, text="Subfolders (when using Folder…)",
            variable=self._recursive_var, font=("Segoe UI", 11),
        ).grid(row=1, column=1, columnspan=2, padx=4, pady=(0, 6), sticky="w")

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

        # Timestamps row
        ctk.CTkLabel(card, text="Output:", font=FONT_BODY).grid(
            row=3, column=0, padx=(14, 8), pady=(6, 14), sticky="w")
        self._ts_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Include [HH:MM:SS] timestamps",
                        variable=self._ts_var, font=FONT_BODY).grid(
            row=3, column=1, padx=4, pady=(6, 14), sticky="w")

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

    def _add_paths(self, new_paths: list[Path]) -> None:
        seen = {p.resolve() for p in self._paths}
        for p in new_paths:
            if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            r = p.resolve()
            if r not in seen:
                seen.add(r)
                self._paths.append(p)
        self._refresh_queue_label()
        self._set_status("Ready." if self._paths else "No files in queue.")

    def _refresh_queue_label(self) -> None:
        if not self._paths:
            self._file_var.set("No files — use File(s)… or Folder…")
            return
        if len(self._paths) == 1:
            self._file_var.set(str(self._paths[0]))
            return
        # Multi — show first two + count
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
        try:
            found = collect_paths(
                [],
                directory=Path(d),
                recursive=self._recursive_var.get(),
            )
        except OSError as exc:
            messagebox.showerror("Folder", str(exc))
            return
        if not found:
            messagebox.showinfo(
                "Folder",
                "No supported media files in that folder.",
            )
            return
        self._add_paths(found)

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
        if not self._paths:
            messagebox.showwarning(
                "No files",
                "Add one or more files (File(s)…), or all files in a folder (Folder…).",
            )
            return
        self._running = True
        self._output_path = None
        self._btn.configure(state="disabled", text="Transcribing…")
        self._copy_btn.configure(state="disabled")
        self._open_btn.configure(state="disabled")
        self._set_preview("")
        self._progress.start()
        self._set_status("Starting…")
        paths = [p.resolve() for p in self._paths]
        threading.Thread(
            target=self._run_transcribe, args=(paths,), daemon=True
        ).start()

    def _run_transcribe(self, paths: list[Path]) -> None:
        def on_seg(count: int, text: str) -> None:
            self.after(0, self._set_status, f"Segment {count}: {text[:50]}…")

        def on_file(i: int, total: int, p: Path) -> None:
            self.after(
                0, self._set_status,
                f"File {i}/{total}: {p.name}",
            )

        try:
            if len(paths) == 1:
                out = transcribe(
                    input_path=paths[0],
                    model_name=self._model_var.get(),
                    timestamps=self._ts_var.get(),
                    on_segment=on_seg,
                )
                self.after(0, self._on_done, out, None)
            else:
                res = transcribe_batch(
                    paths=paths,
                    model_name=self._model_var.get(),
                    timestamps=self._ts_var.get(),
                    on_segment=on_seg,
                    on_file=on_file,
                )
                self.after(0, self._on_batch_done, res)
        except Exception as exc:
            self.after(0, self._on_error, str(exc))

    def _on_batch_done(
        self, res: list[tuple[Path, Exception | None]]
    ) -> None:
        failed = [(p, e) for p, e in res if e is not None]
        ok = [p for p, e in res if e is None]
        self._running = False
        self._progress.stop()
        self._progress.set(1)
        self._btn.configure(state="normal", text="Transcribe")
        if not ok and failed:
            self._on_error("; ".join(f"{p.name}: {e}" for p, e in failed))
            return
        if failed:
            self._set_status(
                f"Done with errors: {len(ok)} ok, {len(failed)} failed. "
                f"Check messages.",
                color=WARNING,
            )
            messagebox.showwarning(
                "Batch finished",
                f"{len(ok)} succeeded, {len(failed)} failed.\n"
                + "\n".join(f"• {p.name}: {e}" for p, e in failed[:8]),
            )
        else:
            self._set_status(
                f"All {len(ok)} file(s) transcribed.",
                color=SUCCESS,
            )
        # Preview last successful .txt
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
            self._set_preview(
                "\n\n".join(f"✓ {p.name}" for p in ok) if ok else ""
            )

    def _on_done(
        self, output_path: Path, _unused: None = None
    ) -> None:
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
        except OSError:
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
