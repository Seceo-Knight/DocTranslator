"""
ocr_engine.py
-------------
OCR support for scanned / image-only PDF pages (pages with no extractable
text layer at all -- typically a photographed or scanned document that was
saved straight to PDF with no OCR step ever having been run on it).

Why EasyOCR and not Tesseract: Tesseract is the more common choice, but it
requires installing a separate non-Python executable on the machine (a
standalone Windows installer, not something pip can provide) -- exactly the
class of friction this project has deliberately avoided elsewhere (see the
IndicTransToolkit note in indic_processor.py). EasyOCR is a pure `pip
install`, built on PyTorch, which this project already depends on for
translation -- no extra installer, no compiler. It also natively supports
Hindi and Marathi (Devanagari) alongside English, which is exactly the
language set this tool needs.

Like the IndicTrans2 models, EasyOCR downloads its (much smaller, tens of
MB) detection/recognition models on first use per language, then runs fully
offline afterward.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import List, Tuple

LANG_TO_EASYOCR_CODE = {
    "English": "en",
    "Hindi": "hi",
    "Marathi": "mr",
}

MIN_CONFIDENCE = 0.4
DEFAULT_OCR_DPI = 300
# A page with fewer than this many extractable characters (and at least one
# embedded image) is treated as "scanned" -- image-only PDFs sometimes still
# have a stray digitally-added character or two (e.g. a page number stamp),
# so a strict "zero characters" check would miss the common case.
SCANNED_TEXT_THRESHOLD = 20


def _bundled_assets_root() -> Path:
    """
    Same convention as translator_engine._bundled_assets_root(): resolves
    the folder PyInstaller actually places --add-data content into. In a
    frozen --onedir build that's the _internal/ folder (via sys._MEIPASS),
    NOT the folder the .exe itself sits in -- those differ since PyInstaller
    6's onedir layout split bundled contents into _internal/. Using
    sys.executable's parent here would silently never find the bundled
    easyocr_models/ folder, quietly falling back to a network download
    instead.
    """
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _bundled_ocr_models_dir() -> Path | None:
    """
    Mirrors translator_engine._resolve_model_path(): if download_ocr_models.py
    was run once by whoever builds the exe, the OCR detection/recognition
    files live in a local easyocr_models/ folder that gets bundled into the
    package. If present, use it (and refuse to fall back to the network) so
    the OCR feature is just as zero-setup for end users as translation is.
    """
    local_dir = _bundled_assets_root() / "easyocr_models"
    return local_dir if local_dir.is_dir() else None


class OCREngine:
    """
    Lazily loads an EasyOCR reader per language pair and caches it, the same
    pattern translator_engine.TranslationEngine uses for translation models
    -- so OCR models are downloaded/loaded once per app session, not once per
    file.
    """

    def __init__(self):
        self._readers: dict = {}
        self._lock = threading.Lock()
        self.on_status = None  # optional callback(str), same as TranslationEngine

    def _log(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def _get_reader(self, src_lang: str):
        code = LANG_TO_EASYOCR_CODE.get(src_lang, "en")
        # English is included alongside the source language in every reader:
        # scanned documents routinely mix in Latin-script content (numbers,
        # units, English loanwords, letterheads) even when the main body is
        # Hindi/Marathi, and EasyOCR's Devanagari+English combination is a
        # supported pairing.
        langs = tuple(sorted({code, "en"}))

        if langs in self._readers:
            return self._readers[langs]
        with self._lock:
            if langs in self._readers:
                return self._readers[langs]
            try:
                import easyocr  # local import: keeps this module importable without easyocr installed
            except ImportError as exc:
                raise ImportError(
                    "OCR support requires easyocr. Install it with:\n    pip install easyocr"
                ) from exc

            bundled_dir = _bundled_ocr_models_dir()
            if bundled_dir is not None:
                self._log(f"Loading OCR models for {list(langs)} (bundled locally, no download needed)...")
                reader = easyocr.Reader(
                    list(langs), gpu=False,
                    model_storage_directory=str(bundled_dir),
                    download_enabled=False,
                )
            else:
                self._log(f"Loading OCR models for {list(langs)} (first run downloads them)...")
                reader = easyocr.Reader(list(langs), gpu=False)

            self._readers[langs] = reader
            self._log("OCR models ready.")
            return reader

    def is_scanned_page(self, page) -> bool:
        """
        Heuristic: a page with (almost) no extractable text but at least one
        embedded image is treated as scanned and routed through OCR instead
        of the normal text-block/table extraction (which would find nothing
        on a page like this anyway).
        """
        text_len = len(page.get_text().strip())
        has_image = len(page.get_images()) > 0
        return text_len < SCANNED_TEXT_THRESHOLD and has_image

    def detect_regions(self, page, src_lang: str, dpi: int = DEFAULT_OCR_DPI) -> List[Tuple]:
        """
        Renders the page to an image, runs OCR, and returns a list of
        (fitz.Rect, text) tuples in PDF point coordinates (not pixels), ready
        to be dropped straight into the same redact-then-insert pipeline
        document_handler.py already uses for ordinary text blocks and table
        cells.
        """
        import fitz
        import numpy as np

        reader = self._get_reader(src_lang)

        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:  # drop alpha channel -- EasyOCR expects RGB/grayscale
            img = img[:, :, :3]

        results = reader.readtext(img)

        # EasyOCR works in the pixel space of the rendered image; convert
        # back to PDF points (72 points per inch) so the returned rects line
        # up with the actual page coordinate system.
        scale = 72.0 / dpi

        # OCR bounding boxes can clip tight to the glyph outlines and miss a
        # sliver of an ascender/descender (e.g. the top of "l", the tail of
        # "g"). Since the next step blanks out exactly this rect on the
        # underlying scanned image, a too-tight box leaves a faint ghost of
        # the original text behind the translation. A small fixed margin
        # costs nothing (there's rarely other content immediately adjacent
        # to a line of scanned text) and guards against that reliably.
        margin = 2.0  # points

        regions = []
        for bbox, text, confidence in results:
            text = text.strip()
            if not text or confidence < MIN_CONFIDENCE:
                continue
            xs = [point[0] for point in bbox]
            ys = [point[1] for point in bbox]
            rect = fitz.Rect(
                min(xs) * scale - margin,
                min(ys) * scale - margin,
                max(xs) * scale + margin,
                max(ys) * scale + margin,
            )
            regions.append((rect, text))
        return regions
