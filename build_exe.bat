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
REM OCR (easyocr) support: this script auto-detects whether easyocr is
REM installed and includes it in the build if so (nothing to configure).
REM If you also want the OCR feature to work with zero internet access for
REM recipients (same reasoning as the models\ folder above), run this first:
REM     python download_ocr_models.py
REM which downloads EasyOCR's detector/recognizer files into a local
REM easyocr_models\ folder that this script bundles in automatically if
REM present. If you skip it, OCR still works in the built exe, but each
REM person downloads EasyOCR's models the first time they use the OCR
REM checkbox (no account needed for that part, unlike the main models).
REM
REM Branding: assets\icon.ico becomes the exe's file/taskbar icon
REM (--icon below); assets\logo.png is bundled in via --add-data so gui.py
REM can show it in the app's own header at runtime.
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

set OCR_ARG=
python -c "import easyocr" >nul 2>&1
if %errorlevel%==0 (
    echo Found easyocr installed -- including OCR support in the build.
    set OCR_ARG=--collect-all easyocr --collect-all torchvision --collect-all cv2
) else (
    echo easyocr not installed -- OCR support will not be included ^(see requirements-ocr.txt^).
)

set OCR_MODELS_ARG=
if exist "easyocr_models\" (
    echo Found local easyocr_models\ folder -- bundling it so OCR needs no internet access either.
    set OCR_MODELS_ARG=--add-data "easyocr_models;easyocr_models"
)

pyinstaller ^
    --name DocumentTranslator ^
    --onedir ^
    --windowed ^
    --icon "assets\icon.ico" ^
    --add-data "fonts;fonts" ^
    --add-data "assets;assets" ^
    %MODELS_ARG% ^
    %OCR_ARG% ^
    %OCR_MODELS_ARG% ^
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
