@echo off
REM ---------------------------------------------------------------------
REM build_exe.bat
REM Packages DocumentTranslator into a standalone Windows app with PyInstaller.
REM
REM IMPORTANT: this must be run ON WINDOWS, inside the activated venv, with
REM all of requirements.txt already installed. PyInstaller cross-compiles
REM nothing -- it bundles whatever Python/OS it runs on.
REM
REM Model weights: if you want end users to need ZERO Hugging Face setup
REM (recommended for handing this exe to other people), run this first:
REM     python download_models.py
REM That downloads the two IndicTrans2 checkpoints into a local models\
REM folder ONCE (using your own already-logged-in HF account), and this
REM script below bundles that folder into the exe automatically if it
REM exists. Recipients then load models straight off disk -- no account, no
REM token, no internet needed even on first run. This does add roughly
REM 700MB-1GB to the dist\ folder.
REM
REM If you skip download_models.py, the exe instead downloads the models
REM into %USERPROFILE%\.cache\huggingface the first time EACH person runs
REM it, which means each of them needs their own Hugging Face account/token
REM (see README for `huggingface-cli login`) -- fine for just yourself, not
REM realistic for distributing to many people.
REM
REM OCR (easyocr) is NOT bundled by this script, since it's an optional
REM feature most users won't need (see requirements-ocr.txt / the README's
REM OCR section). If you installed requirements-ocr.txt and want OCR to work
REM in the packaged exe too, add these three lines to the pyinstaller
REM command below:
REM     --collect-all easyocr ^
REM     --collect-all torchvision ^
REM     --collect-all cv2 ^
REM ---------------------------------------------------------------------

call venv\Scripts\activate

set MODELS_ARG=
if exist "models\" (
    echo Found local models\ folder -- bundling it so end users need no Hugging Face account.
    set MODELS_ARG=--add-data "models;models"
) else (
    echo No local models\ folder found -- exe will download models from Hugging Face on first
    echo run for whoever uses it ^(run download_models.py first if you want to avoid that^).
)

pyinstaller ^
    --name DocumentTranslator ^
    --onedir ^
    --windowed ^
    --add-data "fonts;fonts" ^
    %MODELS_ARG% ^
    --collect-all torch ^
    --collect-all transformers ^
    --collect-all indicnlp ^
    --collect-all sacremoses ^
    --collect-all sentencepiece ^
    --collect-all accelerate ^
    app.py

echo.
echo Build finished. Find the app at dist\DocumentTranslator\DocumentTranslator.exe
echo Copy the whole dist\DocumentTranslator folder when distributing -- it is
echo not a single portable file, but it starts much faster than --onefile
echo for a project this size.
pause
