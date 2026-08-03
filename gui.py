"""
gui.py
------
Tkinter desktop GUI for DocumentTranslator. Tkinter ships with Python (no
extra dependency) and packages cleanly with PyInstaller, which is why it was
chosen over PyQt/Kivy for this tool.

Layout:
    - Choose a single file or a whole folder (batch mode)
    - Pick source language (or Auto-detect) and target language
    - Pick an output folder (defaults to ./translated_docs)
    - Start; translation runs on a background thread so the UI never freezes
    - A log pane + progress bar show per-file / per-segment progress

The Tk main loop is not thread-safe, so the worker thread only ever pushes
strings onto a queue.Queue; the GUI thread drains that queue on a timer.
"""

from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    HORIZONTAL,
    LEFT,
    RIGHT,
    BooleanVar,
    StringVar,
    Tk,
    X,
    Y,
    filedialog,
    messagebox,
)
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from document_handler import SUPPORTED_EXTENSIONS, extract_sample_texts, translate_file
from lang_detect import detect_language_for_document
from ocr_engine import OCREngine
from translator_engine import LANG_TAGS, TranslationEngine

LANGUAGES = list(LANG_TAGS.keys())  # ["English", "Hindi", "Marathi"]


class DocumentTranslatorApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Document Translator (IndicTrans2 - Offline)")
        self.root.geometry("720x560")

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.engine: TranslationEngine | None = None
        self.ocr_engine: OCREngine | None = None
        self.worker_thread: threading.Thread | None = None

        self.input_path = StringVar()
        self.output_dir = StringVar(value=str(Path.cwd() / "translated_docs"))
        self.mode = StringVar(value="file")  # "file" or "folder"
        self.src_lang = StringVar(value="Auto-detect")
        self.tgt_lang = StringVar(value="Hindi")
        # Off by default: OCR pulls in a heavier dependency (easyocr, plus
        # its own model downloads) than the rest of this tool needs, so it's
        # opt-in rather than something that silently triggers a new install
        # the first time someone happens to feed it a scanned PDF.
        self.enable_ocr = BooleanVar(value=False)

        self._build_widgets()
        self.root.after(100, self._drain_log_queue)

    # -- UI construction ------------------------------------------------------

    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}

        mode_frame = ttk.LabelFrame(self.root, text="1. Choose input")
        mode_frame.pack(fill=X, **pad)

        ttk.Radiobutton(
            mode_frame, text="Single file", variable=self.mode, value="file",
            command=self._refresh_browse_label,
        ).pack(side=LEFT, padx=6, pady=6)
        ttk.Radiobutton(
            mode_frame, text="Whole folder (batch)", variable=self.mode, value="folder",
            command=self._refresh_browse_label,
        ).pack(side=LEFT, padx=6, pady=6)

        path_frame = ttk.Frame(self.root)
        path_frame.pack(fill=X, **pad)
        ttk.Entry(path_frame, textvariable=self.input_path).pack(
            side=LEFT, fill=X, expand=True, padx=(0, 6)
        )
        self.browse_button = ttk.Button(path_frame, text="Browse file...", command=self._browse_input)
        self.browse_button.pack(side=RIGHT)

        lang_frame = ttk.LabelFrame(self.root, text="2. Languages")
        lang_frame.pack(fill=X, **pad)

        ttk.Label(lang_frame, text="From:").pack(side=LEFT, padx=(10, 2))
        ttk.Combobox(
            lang_frame, textvariable=self.src_lang, state="readonly",
            values=["Auto-detect"] + LANGUAGES, width=14,
        ).pack(side=LEFT, padx=(0, 16))

        ttk.Label(lang_frame, text="To:").pack(side=LEFT, padx=(0, 2))
        ttk.Combobox(
            lang_frame, textvariable=self.tgt_lang, state="readonly",
            values=LANGUAGES, width=14,
        ).pack(side=LEFT)

        ttk.Checkbutton(
            lang_frame, text="OCR scanned PDFs (needs easyocr; downloads OCR models on first use)",
            variable=self.enable_ocr,
        ).pack(side=LEFT, padx=(16, 0))

        out_frame = ttk.LabelFrame(self.root, text="3. Output folder")
        out_frame.pack(fill=X, **pad)
        ttk.Entry(out_frame, textvariable=self.output_dir).pack(
            side=LEFT, fill=X, expand=True, padx=(10, 6), pady=6
        )
        ttk.Button(out_frame, text="Browse...", command=self._browse_output).pack(
            side=RIGHT, padx=(0, 10)
        )

        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=X, **pad)
        self.start_button = ttk.Button(action_frame, text="Start translation", command=self._start)
        self.start_button.pack(side=LEFT)

        self.progress = ttk.Progressbar(action_frame, orient=HORIZONTAL, mode="determinate")
        self.progress.pack(side=LEFT, fill=X, expand=True, padx=10)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill=BOTH, expand=True, **pad)
        self.log_widget = ScrolledText(log_frame, height=14, state="disabled", wrap="word")
        self.log_widget.pack(fill=BOTH, expand=True, padx=6, pady=6)

    def _refresh_browse_label(self) -> None:
        self.browse_button.config(
            text="Browse file..." if self.mode.get() == "file" else "Browse folder..."
        )

    # -- browse dialogs ---------------------------------------------------------

    def _browse_input(self) -> None:
        if self.mode.get() == "file":
            exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
            path = filedialog.askopenfilename(filetypes=[("Supported documents", exts)])
        else:
            path = filedialog.askdirectory()
        if path:
            self.input_path.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    # -- logging ------------------------------------------------------------

    def _log(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_widget.configure(state="normal")
                self.log_widget.insert(END, message + "\n")
                self.log_widget.see(END)
                self.log_widget.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log_queue)

    # -- translation lifecycle ------------------------------------------------

    def _start(self) -> None:
        input_path = self.input_path.get().strip()
        output_dir = self.output_dir.get().strip()
        tgt_lang = self.tgt_lang.get()
        src_choice = self.src_lang.get()

        if not input_path:
            messagebox.showerror("Missing input", "Choose a file or folder first.")
            return
        if not Path(input_path).exists():
            messagebox.showerror("Not found", f"Path does not exist:\n{input_path}")
            return

        self.start_button.config(state="disabled")
        self.progress["value"] = 0

        self.worker_thread = threading.Thread(
            target=self._run_worker,
            args=(input_path, output_dir, src_choice, tgt_lang),
            daemon=True,
        )
        self.worker_thread.start()

    def _collect_files(self, input_path: str) -> list[Path]:
        p = Path(input_path)
        if p.is_file():
            return [p]
        return [f for f in sorted(p.rglob("*")) if f.suffix.lower() in SUPPORTED_EXTENSIONS]

    def _resolve_src_lang(self, path: Path, src_choice: str) -> str:
        if src_choice != "Auto-detect":
            return src_choice
        samples = extract_sample_texts(str(path))
        detected = detect_language_for_document(samples)
        if detected is None:
            self._log(f"  Could not auto-detect language for {path.name}; defaulting to English.")
            return "English"
        self._log(f"  Auto-detected source language: {detected}")
        return detected

    def _run_worker(self, input_path: str, output_dir: str, src_choice: str, tgt_lang: str) -> None:
        try:
            files = self._collect_files(input_path)
            if not files:
                self._log("No supported files (.docx, .txt, .pdf) found.")
                return

            self._log(f"Found {len(files)} file(s) to translate.")

            if self.engine is None:
                self.engine = TranslationEngine()
                self.engine.on_status = self._log

            if self.enable_ocr.get() and self.ocr_engine is None:
                self.ocr_engine = OCREngine()
                self.ocr_engine.on_status = self._log
            ocr_engine = self.ocr_engine if self.enable_ocr.get() else None

            output_root = Path(output_dir)
            output_root.mkdir(parents=True, exist_ok=True)

            for index, file_path in enumerate(files, start=1):
                self._log(f"[{index}/{len(files)}] Translating {file_path.name}...")
                src_lang = self._resolve_src_lang(file_path, src_choice)

                if src_lang == tgt_lang:
                    self._log(f"  Skipping: source and target language are both {src_lang}.")
                    continue

                suffix = f"_{tgt_lang}"
                out_name = f"{file_path.stem}{suffix}{file_path.suffix}"
                out_path = output_root / out_name

                translate_file(
                    str(file_path),
                    str(out_path),
                    self.engine.translate_batch,
                    src_lang,
                    tgt_lang,
                    progress_cb=self._log,
                    ocr_engine=ocr_engine,
                )
                self._log(f"  Saved: {out_path}")
                self.progress["value"] = (index / len(files)) * 100

            self._log("Done.")
        except Exception as exc:  # surfaced to the user rather than a silent crash
            # Log the full traceback (not just the exception message) to the
            # log pane -- the message alone is rarely enough to diagnose
            # library/version issues; the file/line trail is what matters.
            self._log("ERROR:\n" + traceback.format_exc())
            messagebox.showerror("Translation failed", str(exc) + "\n\n(See the log pane for the full details.)")
        finally:
            self.start_button.config(state="normal")


def main() -> None:
    root = Tk()
    DocumentTranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
