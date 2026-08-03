"""
download_ocr_models.py
-----------------------
ONE-TIME step for whoever is BUILDING/DISTRIBUTING DocumentTranslator.exe --
same idea as download_models.py, but for the OCR feature (the "OCR scanned
PDFs" checkbox / --ocr flag) instead of the main translation models.

Only relevant if you've installed requirements-ocr.txt and want the OCR
checkbox to work with zero internet access for whoever receives the exe.
If you don't care about OCR working offline out of the box for other people
(e.g. you're the only one who'll ever tick that checkbox), you can skip this
script entirely -- ocr_engine.py falls back to EasyOCR's normal
download-on-first-use behavior automatically when easyocr_models/ is absent.

Why this is needed at all: EasyOCR downloads its own detection/recognition
model files (small, tens of MB, no account or license needed -- unlike the
IndicTrans2 models) the first time each language combination is used. That's
a one-time, no-friction step for yourself, but it still means every end user
needs internet on their first scanned-PDF OCR run unless these files are
bundled in ahead of time, same underlying issue as the Hugging Face models.

Usage (run this on the machine that BUILDS the .exe, inside the venv, with
requirements-ocr.txt installed):

    python download_ocr_models.py

This creates a local easyocr_models/ folder containing the detector and
recognizer files for every language combination this app uses (English
alone, English+Hindi, English+Marathi). ocr_engine.py automatically prefers
this folder over the network the moment it exists. Then run build_exe.bat as
usual; it bundles this folder into the package alongside models/.
"""
from __future__ import annotations

try:
    import easyocr
except ImportError as exc:
    raise SystemExit(
        "easyocr is not installed. Install requirements-ocr.txt first:\n"
        "    pip install torchvision --index-url https://download.pytorch.org/whl/cpu\n"
        "    pip install -r requirements-ocr.txt"
    ) from exc

# Every language combination ocr_engine._get_reader() can ask for (English is
# always included alongside the source language -- see ocr_engine.py).
LANG_COMBOS = [
    ["en"],
    ["en", "hi"],
    ["en", "mr"],
]

STORAGE_DIR = "easyocr_models"


def main() -> None:
    for langs in LANG_COMBOS:
        print(f"Downloading OCR models for {langs} -> {STORAGE_DIR}/ ...")
        # Instantiating a Reader with download_enabled=True (the default) and
        # a custom model_storage_directory downloads straight into that
        # folder instead of the default ~/.EasyOCR/model cache.
        easyocr.Reader(langs, gpu=False, model_storage_directory=STORAGE_DIR)
        print("  done.")

    print()
    print(f"All OCR models downloaded into ./{STORAGE_DIR}/")
    print("Now run build_exe.bat to package them into the .exe.")


if __name__ == "__main__":
    main()
