# DocTranslator

An offline Windows tool that translates DOCX / TXT / PDF documents between
English, Hindi, and Marathi without disturbing the document's structure
(headings, bullet lists, tables, styles) -- powered by AI4Bharat's open-source
IndicTrans2 models, running fully offline after the first model download.

This README is written as a complete, from-scratch walkthrough, including
every real error we hit while first setting this up and exactly how each one
was fixed -- so anyone starting from a clean Windows machine can follow it
straight through without guessing.

## Why IndicTrans2, not IndicTrans3

IndicTrans3 currently exists only as a beta model built on Gemma-3, meant to
be served with vLLM on a GPU. That doesn't package into a lightweight offline
Windows app. IndicTrans2's distilled 200M models are proven, run fine on a
CPU, and are what this project actually uses.

## Project layout

```
DocumentTranslator/
├── app.py                  # CLI entry point + launches the GUI by default
├── gui.py                  # Tkinter desktop GUI
├── translator_engine.py    # IndicTrans2 model loading + batch translation
├── indic_processor.py      # Pure-Python pre/post-processing (see note below)
├── document_handler.py     # DOCX/TXT/PDF structure-preserving read-write
├── lang_detect.py          # English/Hindi/Marathi auto-detection
├── ocr_engine.py           # Optional OCR for scanned/image-only PDFs (see below)
├── fonts/                  # Bundled Devanagari font for PDF output (see below)
│   ├── Shobhika-Regular.otf
│   └── Shobhika-Bold.otf
├── assets/                 # App branding: exe icon + in-app logo (see below)
│   ├── icon.ico
│   └── logo.png
├── glossary.txt            # Your do-not-translate list (chemical/product names)
├── requirements.txt
├── requirements-ocr.txt    # Optional extra dependency for OCR support
├── download_models.py      # One-time: bundle translation models for distribution
├── download_ocr_models.py  # One-time: bundle OCR models for distribution
├── build_exe.bat           # PyInstaller packaging script (run on Windows)
└── translated_docs/        # default output folder
```

**Note on `indic_processor.py`:** IndicTrans2 needs a pre/post-processing step
(punctuation normalization, masking numbers/URLs/emails, Indic script
tokenization) around the model. AI4Bharat's own package for this,
`IndicTransToolkit`, implements it as a compiled Cython extension and ships no
Windows wheels -- installing it on Windows means compiling from source, which
needs Microsoft's C++ Build Tools (a multi-GB download). `indic_processor.py`
is a direct, line-by-line port of that same logic back into plain Python
(credit: original algorithm by Varun Gumma, Jay Gala, Pranjal Chitale, and Raj
Dabre / AI4Bharat, MIT license), so it installs with nothing beyond
`pip install -r requirements.txt` -- no compiler, no Visual Studio. It's used
automatically; there's nothing extra to configure.

---

## Step-by-step setup (from a clean Windows machine)

### 1. Install Python

Install Python 3.11+ from python.org. **Check "Add Python to PATH"** during
install, or later commands won't be found.

### 2. Get the project onto your machine

Unzip the project. Note that if you download it as a zip that itself
contains a `DocumentTranslator/` folder, you can end up with a doubled-up
path like `Downloads\DocumentTranslator\DocumentTranslator`. If a command
below says a file "does not exist," run `dir` and `cd` into whichever folder
actually contains `requirements.txt`, `app.py`, etc.

### 3. Create and activate a virtual environment

```
cd DocumentTranslator
python -m venv venv
venv\Scripts\activate
```

Your prompt should now start with `(venv)`. Every command below assumes
you're inside this activated venv.

### 4. Install PyTorch (CPU build) first, separately

```
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Do this as its own step, before `pip install -r requirements.txt`. Plain
`pip install torch` on Windows can pull in the full CUDA-enabled build --
several GB of NVIDIA GPU libraries -- even on a machine with no GPU, which
makes the install look "stuck" for a long time during
`Installing collected packages`. The CPU-only build above is a couple hundred
MB and installs in under a minute. If you do have an NVIDIA GPU and want
faster translation, you can install the CUDA build instead (see pytorch.org),
but CPU is fine for testing.

### 5. Install the rest of the dependencies

```
pip install -r requirements.txt
```

This pulls in `transformers`, `indic-nlp-library`, `sacremoses`, `regex`,
`tqdm`, `python-docx`, `PyMuPDF`, `langdetect`, `accelerate`,
`huggingface_hub`, and `pyinstaller`. All of these install on Windows with
plain prebuilt wheels -- no compiler needed for anything in this list.

### 6. Get access to the IndicTrans2 models (required, one-time)

The models are **gated** on Hugging Face -- you must accept their license
before you're allowed to download them.

1. Create a free account at huggingface.co if you don't have one.
2. While logged in, open these two model pages and accept/agree to access on
   each:
   - https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M
   - https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
3. Create an access token: go to https://huggingface.co/settings/tokens,
   click "New token," name it anything, type "Read," click Create, and copy
   the token (starts with `hf_...`) -- you can't view it again after leaving
   the page.
4. Log in from the terminal (still inside the activated venv):
   ```
   huggingface-cli login
   ```
   Paste the token when prompted (right-click to paste in Command Prompt).
   When asked "Add token as git credential?" you can answer `n`.
5. Confirm it worked:
   ```
   huggingface-cli whoami
   ```
   This should print your Hugging Face username.

Skipping this step means the first translation attempt fails with an HTTP
401 error.

### 7. Run it

GUI (default):

```
python app.py
```

Pick a file (or a whole folder, for batch mode), choose source language (or
Auto-detect) and target language, choose an output folder, and click "Start
translation." The very first translation also downloads the relevant
~200-400MB model checkpoint, so it'll be slower than every run after that,
which is fully offline.

Headless CLI (useful for scripting, or to see full error tracebacks instead
of a popup):

```
python app.py --cli report.docx --from English --to Hindi
python app.py --cli ./docs_folder --from Auto-detect --to Marathi --out ./translated_docs
```

---

## Troubleshooting -- real errors we hit, and the fix for each

These are, in order, the actual problems encountered while first setting this
up on Windows, kept here so the fixes aren't lost.

**`ERROR: Could not open requirements file: ... No such file or directory`**
The zip's contents were one folder deeper than expected (a nested
`DocumentTranslator\DocumentTranslator`). Run `dir`, and `cd` into whichever
folder directly contains `requirements.txt`.

**`pip install -r requirements.txt` looks frozen at "Installing collected
packages"**
This is torch silently pulling in the full CUDA/GPU build (several GB) even
without a GPU. Cancel with `Ctrl+C`, run
`pip uninstall torch -y`, then install the CPU-only build explicitly first:
`pip install torch --index-url https://download.pytorch.org/whl/cpu`, then
rerun `pip install -r requirements.txt` (it'll skip torch, already installed).

**`error: Microsoft Visual C++ 14.0 or greater is required` while installing
`IndicTransToolkit`**
That package ships as a compiled Cython extension with no Windows wheels --
its own docs say it isn't built/tested for Windows. Rather than requiring a
multi-GB Visual Studio Build Tools install, this project doesn't depend on
that package at all: `indic_processor.py` is a pure-Python port of the exact
same logic, using only pure-Python/prebuilt-wheel libraries. If you're
following this README's `requirements.txt`, you should never hit this error
in the first place.

**Popup: `Translation failed: 'NoneType' object has no attribute 'shape'`**
This came from IndicTrans2's own custom model code
(`modeling_indictrans.py`), which assumes its cache argument is either `None`
or an old-style tuple. Recent versions of `transformers` instead pass a
`Cache` object once caching is enabled, which that check doesn't expect --
version drift between the model's (older) custom code and current
`transformers`, not a bug in this project. Fixed in `translator_engine.py` by
disabling the KV-cache for generation (`use_cache=False`). Translation is
somewhat slower as a result (no cache reuse across beam-search steps) but
correct. Already applied in this repo -- nothing to do.

**`'torch_dtype' is deprecated! Use 'dtype' instead!` warning**
Harmless -- newer `transformers` renamed that constructor argument. Fixed by
using `dtype=` instead of `torch_dtype=` when loading the model in
`translator_engine.py`. Already applied in this repo.

**Translated PDF shows question marks (`?`) instead of Hindi/Marathi text**
PyMuPDF's built-in fonts (Helvetica, Times, etc.) only have Latin-script
glyphs -- there's no Devanagari in them at all, so any Devanagari character
falls back to `?`. Fixed by bundling a real Devanagari font
(`fonts/Shobhika-Regular.otf`, IIT Bombay, SIL Open Font License) and
embedding it into the PDF automatically whenever the target language is
Hindi or Marathi (see `_font_for_language` in `document_handler.py`). English
output keeps using PyMuPDF's built-in Helvetica -- no font file needed there.
Already applied in this repo; `build_exe.bat` also bundles the `fonts/`
folder into the packaged exe via `--add-data`, so this works after packaging
too, not just when running from source.

---

## Protecting chemical names and technical terms from mistranslation

General-purpose translation models weren't trained heavily on chemical
nomenclature, and will happily "translate" a formula or product name into
something wrong. Two layers of protection are built in:

1. **Chemical formulas are detected automatically.** Anything shaped like a
   sequence of element symbols -- `H2SO4`, `NaOH`, `C6H12O6`, `CO2`, `Fe2O3`,
   and so on -- is recognized by a pattern in `indic_processor.py` and passed
   straight through untranslated, in its exact original form. This also
   catches plain acronyms (`CEO`, `PDF`, `USA`), which is a side effect, not
   a bug -- acronyms usually shouldn't be translated either. Nothing to
   configure; this runs on every document automatically.

2. **Named compounds and product names go in `glossary.txt`.** A formula
   pattern can't guess that "Chemsortia" (or any other specific compound or
   brand/product name) shouldn't be translated -- there's no pattern to
   detect, it just looks like an ordinary word. For these, list the term in
   `glossary.txt` (one per line; lines starting with `#` are comments/ignored).
   Any term listed there is matched case-insensitively as a whole word/phrase
   and passed through to the output exactly as written in your source
   document, in every language direction. The file ships with a commented-out
   example -- just add your own terms below it.

   Known minor limitation: if a glossary term (or a chemical formula) is
   directly glued to another word with a hyphen and no space (e.g.
   `Chemsortia-lite` with no space before the hyphen), the underlying English
   tokenizer can occasionally reinsert a stray space at that hyphen in the
   output. This doesn't affect the protected term itself -- it comes through
   correctly either way -- only the spacing immediately around an attached
   hyphen-suffix in that specific pattern.

## How structure is preserved

- **DOCX**: text is translated paragraph-by-paragraph and table-cell-by-cell
  (including nested tables and headers/footers), then written back into the
  paragraph's first run. Paragraph-level formatting -- heading styles, bullet
  and numbered lists, alignment, spacing, images, page breaks -- is never
  touched, so it survives translation exactly. The one trade-off: if a single
  paragraph mixes multiple runs with different formatting (e.g. one bold word
  mid-sentence), that fine-grained formatting collapses onto the first run's
  style. Whole-document structure is unaffected.
- **TXT**: translated line by line, preserving blank lines.
- **PDF**: tables are detected first (via PyMuPDF's table finder) and
  translated cell-by-cell, matched back to their row/column position -- the
  table's border lines are preserved by redacting only the inside of each
  cell (inset a couple points from the border), not the cell's edge itself,
  so the grid survives untouched. Any text that isn't part of a detected
  table is translated as loose paragraph blocks the same way as before, and
  the two passes don't overlap (table text is never also translated as a
  loose block). Beyond that, PDF is still best-effort: it has no flow-document
  structure -- text is absolute-positioned glyphs, redrawn into the same
  bounding box with auto-shrinking font size, but since translated text is
  rarely the same length as the original, line wrapping within a single cell
  or paragraph can still shift.
- **Scanned/image-only PDFs** (a page with no extractable text at all -- a
  photographed or scanned document with no OCR ever run on it): detected
  automatically, and -- if OCR is enabled, see below -- routed through OCR
  instead of the normal text extraction. The page is rendered to an image,
  OCR finds each line of text and its position, those lines are translated
  the same way as any other block, and the original pixels under each
  detected region are blanked out (via PDF redaction's image-blanking mode)
  before the translated text is drawn on top, so the rest of the scanned
  image (photos, signatures, letterhead, table lines that are part of the
  image rather than real PDF structure) is left completely alone.

## OCR for scanned PDFs (optional)

OCR is off by default -- it's not installed unless you ask for it, and even
once installed, it only runs on pages that are genuinely scanned/image-only
(a normal digital PDF page is untouched either way).

**Setup (one extra step beyond the main install):**

```
pip install torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-ocr.txt
```

The `torchvision` install has to go through the CPU-only index explicitly,
for the exact same reason `torch` itself does in the main setup steps above --
otherwise it silently pulls the full CUDA/GPU build.

**Using it:**

- GUI: check "OCR scanned PDFs" before clicking Start.
- CLI: add `--ocr`, e.g. `python app.py --cli scan.pdf --from English --to Hindi --ocr`

The underlying engine is [EasyOCR](https://github.com/JaidedAI/EasyOCR)
(PyTorch-based), chosen specifically because it's a plain `pip install` --
Tesseract, the more common alternative, requires installing a separate
non-Python executable on Windows, which is exactly the kind of friction this
project avoided elsewhere (see the IndicTransToolkit note earlier in this
README). EasyOCR natively supports Hindi and Marathi (Devanagari) alongside
English. Like the translation models, its OCR models download once per
language on first use (tens of MB, much smaller than the translation
models) and then work fully offline.

Known limitations specific to OCR mode: table borders that are literally
part of a scanned image (ink/print lines, not real PDF vector graphics)
aren't specially detected the way digital-PDF tables are -- each OCR'd line
of text is treated as a loose block. OCR accuracy depends on scan quality;
skewed/rotated scans aren't corrected. If `easyocr` isn't installed and OCR
is requested anyway, you'll get a clear error telling you to
`pip install easyocr` rather than an obscure crash.

**Distributing the OCR feature to other people:** unlike the IndicTrans2
models, EasyOCR's files aren't gated (no account needed), but they're still
downloaded from the internet the first time someone uses the OCR checkbox.
If you want OCR to also be zero-setup/offline for recipients of the exe, run
this once before `build_exe.bat` (needs `requirements-ocr.txt` installed):

```
python download_ocr_models.py
```

This downloads EasyOCR's detector/recognizer files into a local
`easyocr_models/` folder, which `build_exe.bat` bundles in automatically if
present -- same pattern as `download_models.py` for the main translation
models. Skip it and OCR still works fine in the built exe; each person just
downloads those (small, tens-of-MB) files the first time they tick the OCR
box.

---

## Packaging into a Windows .exe

Once you've confirmed translation works via `python app.py`, package it:

```
build_exe.bat
```

Run this **on Windows**, inside the activated venv, after
`pip install -r requirements.txt` has completed. PyInstaller bundles whatever
OS/Python it's run on -- it cannot cross-compile a Windows exe from Linux or
Mac, which is why this step has to happen on the actual Windows machine (not,
for example, in a cloud build).

**Branding:** the exe ships with its own icon (`assets/icon.ico`) and the GUI
has a branded header with the same logo (`assets/logo.png`) plus a "Developed
by Vaibhav Handekar" credit in the footer. Both files are generated assets
already committed to the repo -- nothing to set up, `build_exe.bat` picks
them up automatically (`--icon` for the exe file icon, `--add-data` to bundle
`logo.png` for the in-app header). Swap either file for your own artwork any
time; the app looks for exactly `assets/icon.ico` and `assets/logo.png`.

The script runs:

```
pyinstaller ^
    --name DocumentTranslator ^
    --onedir ^
    --windowed ^
    --icon "assets\icon.ico" ^
    --add-data "fonts;fonts" ^
    --add-data "assets;assets" ^
    --collect-all torch ^
    --collect-all transformers ^
    --collect-all indicnlp ^
    --collect-all sacremoses ^
    --collect-all sentencepiece ^
    --collect-all accelerate ^
    app.py
```

This takes a few minutes. The finished app lands at
`dist\DocumentTranslator\DocumentTranslator.exe`. **Distribute the whole
`dist\DocumentTranslator` folder**, not just the `.exe` file -- `--onedir`
keeps all the supporting files alongside it (this starts much faster than
PyInstaller's single-file `--onefile` mode for a project this size, which
would otherwise re-extract everything into a temp folder on every launch).

By default, model weights are *not* bundled into the exe -- the packaged app
downloads them into `%USERPROFILE%\.cache\huggingface` on first run, exactly
like running from source, then works offline after that. This is fine if
you're the only one who'll ever run the exe, but it means every recipient
needs their own Hugging Face account and `huggingface-cli login`. **If
you're handing this exe to other people, see the next section** --
`download_models.py` removes that requirement entirely.

---

## Distributing to other people (no Hugging Face account needed for them)

The IndicTrans2 model repos are "gated" on Hugging Face: downloading them
normally requires an account, accepting the model license, and a personal
access token. That's a reasonable one-time step for *you*, the developer, but
it doesn't scale to "give this exe to a bunch of people" -- you can't ask
every recipient to sign up for Hugging Face just to translate a document.

The gating is only Hugging Face's access control on downloads *from their
servers* -- it isn't DRM inside the model files, and IndicTrans2 is
MIT-licensed, which explicitly permits redistributing the files themselves.
So the fix is: download the model files **once**, yourself, and bundle those
actual files into the exe. Recipients then load the model straight off local
disk -- no Hugging Face account, no token, no internet connection required,
even on their very first run.

Steps (do this once, before running `build_exe.bat`):

```
huggingface-cli login          (if you haven't already)
python download_models.py
build_exe.bat
```

`download_models.py` downloads both IndicTrans2 checkpoints into a local
`models/` folder. `build_exe.bat` detects that folder automatically and
bundles it into `dist\DocumentTranslator` alongside everything else --
nothing else needs to change, and no code path needs to know which mode
you're in; `translator_engine.py` just prefers the local folder over the
network whenever it's present.

Tradeoffs to weigh:

- **Bundled (`download_models.py` + build):** `dist\DocumentTranslator` grows
  by roughly 700MB-1GB (two ~200M-parameter models plus tokenizers), but
  every recipient gets a true zero-setup, zero-account, works-offline-on-
  first-launch experience. This is the right choice for handing the tool to
  a team, a lab, or anyone outside yourself.
- **Not bundled (skip that step):** smaller download for you to distribute,
  but each recipient must create their own Hugging Face account, accept the
  IndicTrans2 license, generate a token, and run `huggingface-cli login`
  before their first translation -- real friction, and not realistic to ask
  of many people.

One option this project deliberately does *not* use: baking a single shared
Hugging Face token into the app so everyone authenticates as "you" behind the
scenes. That still requires every user to have internet on first run, and
anyone who unpacks the exe can extract the token from it, which risks it
getting abused or revoked for everyone at once. Bundling the actual files is
simpler and has none of those failure modes.

If your use case is genuinely commercial/at-scale redistribution beyond your
own team or lab, it's worth double-checking the current license terms on
each model's Hugging Face page yourself before shipping widely -- this
project isn't legal advice, and license terms can change.

Note: this section covers the main translation models. If you also plan to
hand out the optional OCR feature, see `download_ocr_models.py` in the OCR
section below -- same idea, smaller files, no account required for those.

---

## Roadmap / not yet built

- [x] Modern GUI
- [x] DOCX, TXT, and best-effort PDF support
- [x] English <-> Hindi <-> Marathi
- [x] Auto language detection
- [x] Batch translation of entire folders
- [x] Progress bar / log pane
- [x] Offline mode after first model download
- [x] Windows .exe packaging script
- [x] Chemical formula and glossary protection (avoid mistranslating
      technical/product names)
- [x] PDF table structure detection (rows/columns matched correctly, border
      lines preserved) -- note this is *structural* correctness, not full
      layout fidelity; see the still-open item below
- [x] OCR for scanned/image-only PDFs (optional -- see below)
- [x] Zero-setup distribution to other users (bundle model weights into the
      exe via `download_models.py`, so recipients need no Hugging Face
      account/token -- see "Distributing to other people" above)
- [ ] Drag-and-drop file input
- [ ] Persistent translation history
- [ ] True layout-preserving PDF translation -- preserving each text block's
      original font/size/color/bold-italic, and reflowing text across lines
      or pushing content down when a translation is longer than the
      original, instead of shrinking font size to force-fit the same box.
      Would need an actual page-layout/typesetting engine, not just
      block-level redraw -- a meaningfully bigger project than what's built
      here.

## Known limitations

- Direct Hindi <-> Marathi translation is not supported by these checkpoints
  -- IndicTrans2's `en-indic`/`indic-en` models only translate to/from
  English. Hindi -> Marathi is possible in principle by chaining
  Hindi -> English -> Marathi, but that compounds translation error and isn't
  wired up here.
- Auto-detection between Hindi and Marathi can occasionally misfire since
  they share the Devanagari script -- always let a user override it manually
  for anything that matters.
- CPU translation of a long document can take a while (more so now that the
  KV-cache is disabled -- see Troubleshooting); a GPU, or the larger `-1B`
  model variants if quality matters more than speed, will be faster/better
  respectively -- swap the model names in `translator_engine.py`. For a
  faster CPU run at some cost to fluency, check "Fast mode" in the GUI (or
  pass `--fast` on the CLI) to switch from beam search to greedy decoding.
  Documents with a lot of repeated text (headers, footers, repeated table
  values) also translate faster automatically -- exact-duplicate segments
  are only run through the model once per session and reused.

## License

This project's own code has no license restrictions stated here -- add one
if you plan to distribute it. It depends on IndicTrans2 (MIT, AI4Bharat) and
reuses pre/post-processing logic originally from IndicTransToolkit (MIT,
Varun Gumma et al.). The bundled font `fonts/Shobhika-Regular.otf` (and
`Shobhika-Bold.otf`) is Shobhika 1.05 by the Indian Institute of Technology
Bombay, licensed under the SIL Open Font License 1.1 -- free to embed and
redistribute, including in packaged/commercial applications.
