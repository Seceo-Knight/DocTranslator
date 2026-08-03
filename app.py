"""
app.py
------
Entry point for DocumentTranslator.

    python app.py                     -> launches the GUI (default)
    python app.py --gui               -> same, explicit
    python app.py --cli INPUT ...     -> headless CLI mode, useful for
                                          scripting/testing or servers without
                                          a display

CLI examples:
    python app.py --cli report.docx --from English --to Hindi
    python app.py --cli ./docs_folder --from Auto --to Marathi --out ./translated_docs
    python app.py --cli scanned_report.pdf --from English --to Hindi --ocr

This is also the script PyInstaller packages into DocumentTranslator.exe
(see build_exe.bat) -- by default double-clicking the exe opens the GUI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from document_handler import SUPPORTED_EXTENSIONS, extract_sample_texts, translate_file
from lang_detect import detect_language_for_document
from ocr_engine import OCREngine
from translator_engine import LANG_TAGS, TranslationEngine

LANGUAGES = list(LANG_TAGS.keys())


def _collect_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [f for f in sorted(input_path.rglob("*")) if f.suffix.lower() in SUPPORTED_EXTENSIONS]


def run_cli(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: path not found: {input_path}", file=sys.stderr)
        return 1

    files = _collect_files(input_path)
    if not files:
        print("No supported files (.docx, .txt, .pdf) found.")
        return 1

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = TranslationEngine()
    engine.on_status = print

    ocr_engine = None
    if args.ocr:
        ocr_engine = OCREngine()
        ocr_engine.on_status = print

    for file_path in files:
        print(f"Translating {file_path.name}...")

        src_lang = args.src
        if src_lang == "Auto-detect":
            samples = extract_sample_texts(str(file_path))
            detected = detect_language_for_document(samples)
            src_lang = detected or "English"
            print(f"  Auto-detected source language: {src_lang}")

        if src_lang == args.tgt:
            print(f"  Skipping (source and target both {src_lang}).")
            continue

        out_path = output_dir / f"{file_path.stem}_{args.tgt}{file_path.suffix}"
        translate_file(
            str(file_path), str(out_path), engine.translate_batch, src_lang, args.tgt,
            progress_cb=print, ocr_engine=ocr_engine,
        )
        print(f"  Saved: {out_path}")

    print("Done.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline document translator (English/Hindi/Marathi)")
    parser.add_argument("--gui", action="store_true", help="Launch the desktop GUI (default if no other flags given)")
    parser.add_argument("--cli", dest="input", help="Run headless: path to a file or folder to translate")
    parser.add_argument("--from", dest="src", default="Auto-detect", choices=["Auto-detect"] + LANGUAGES)
    parser.add_argument("--to", dest="tgt", default="Hindi", choices=LANGUAGES)
    parser.add_argument("--out", dest="out", default="translated_docs")
    parser.add_argument(
        "--ocr", action="store_true",
        help="Enable OCR for scanned/image-only PDF pages (requires easyocr; downloads OCR models on first use)",
    )

    args = parser.parse_args()

    if args.input:
        raise SystemExit(run_cli(args))

    import gui

    gui.main()


if __name__ == "__main__":
    main()
