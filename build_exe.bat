@echo off
REM ---------------------------------------------------------------------
REM build_exe.bat
REM Packages DocumentTranslator into a standalone Windows app with PyInstaller.
REM
REM IMPORTANT: this must be run ON WINDOWS, inside the activated venv, with
REM all of requirements.txt already installed. PyInstaller cross-compiles
REM nothing -- it bundles whatever Python/OS it runs on.
REM
REM Model weights are NOT bundled (they are multi-GB and gated on Hugging
REM Face). The exe downloads them into %USERPROFILE%\.cache\huggingface on
REM first run, then works fully offline afterwards. Run
REM     huggingface-cli login
REM once beforehand with a token that has accepted the IndicTrans2 model
REM licenses, or the first-run download will fail with a 401 error.
REM ---------------------------------------------------------------------

call venv\Scripts\activate

pyinstaller ^
    --name DocumentTranslator ^
    --onedir ^
    --windowed ^
    --add-data "fonts;fonts" ^
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
