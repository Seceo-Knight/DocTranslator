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
├── requirements.txt
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

---

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
- **PDF**: best-effort only. PDFs have no flow-document structure -- text is
  absolute-positioned glyphs. This tool extracts text blocks, translates them,
  and redraws them into the same bounding box (auto-shrinking the font to
  fit), but since translated text is rarely the same length as the original,
  line wrapping can shift. Scanned (image-only) PDFs are not supported yet --
  see Roadmap.

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

The script runs:

```
pyinstaller ^
    --name DocumentTranslator ^
    --onedir ^
    --windowed ^
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

Model weights are intentionally *not* bundled into the exe (they're
multi-GB and gated by license). The packaged app downloads them into
`%USERPROFILE%\.cache\huggingface` on first run, exactly like running from
source, then works offline after that. Run `huggingface-cli login` once on
whichever machine will run the exe before its first launch, or set an
`HF_TOKEN` environment variable for users who'll run it unattended.

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
- [ ] OCR for scanned/image-only PDFs
- [ ] Drag-and-drop file input
- [ ] Persistent translation history
- [ ] True layout-preserving PDF translation (would need a PDF layout engine,
      not just block redraw)

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
  respectively -- swap the model names in `translator_engine.py`.

## License

This project's own code has no license restrictions stated here -- add one
if you plan to distribute it. It depends on IndicTrans2 (MIT, AI4Bharat) and
reuses pre/post-processing logic originally from IndicTransToolkit (MIT,
Varun Gumma et al.).
