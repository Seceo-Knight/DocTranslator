"""
download_models.py
-------------------
ONE-TIME step for whoever is BUILDING/DISTRIBUTING DocumentTranslator.exe --
NOT something end users ever need to run.

Problem this solves:
    IndicTrans2's model repos are "gated" on Hugging Face -- downloading them
    normally requires an account, accepting the model license, and running
    `huggingface-cli login`. That's fine for you as the developer, but it does
    not scale to "hand the .exe to a bunch of people": you can't ask every
    single recipient to make a Hugging Face account and log in.

Fix:
    The gating is just Hugging Face's access control on downloading FROM
    THEIR SERVERS -- it is not DRM baked into the model files, and IndicTrans2
    is MIT-licensed, which permits redistributing the files themselves. So you
    download the files ONCE (having already logged in and accepted the
    license), we bundle those actual files into the .exe via build_exe.bat,
    and every end user then loads the model straight off local disk. No
    account, no token, no internet connection needed by them, ever.

Usage (run this on the machine that BUILDS the .exe, inside the venv, after
`huggingface-cli login` has already succeeded once):

    python download_models.py

This creates:
    models/indictrans2-en-indic-dist-200M/
    models/indictrans2-indic-en-dist-200M/

translator_engine.py automatically prefers these local folders over the
network the moment they exist -- nothing else needs to change. Then just run
build_exe.bat as usual; it bundles this models/ folder into the package.

Note on size: this adds roughly 700MB-1GB to the distributed dist/ folder
(two ~200M-parameter models plus tokenizers). That's the tradeoff for making
the app truly zero-setup for every recipient -- if you'd rather keep the exe
small and have each end user log in to Hugging Face themselves, just skip
this script and distribute as before; translator_engine.py falls back to the
normal download-on-first-run behavior automatically when models/ is absent.
"""
from __future__ import annotations

from huggingface_hub import snapshot_download

MODELS = [
    "ai4bharat/indictrans2-en-indic-dist-200M",
    "ai4bharat/indictrans2-indic-en-dist-200M",
]


def main() -> None:
    for model_id in MODELS:
        local_dir = f"models/{model_id.split('/')[-1]}"
        print(f"Downloading {model_id} -> {local_dir} ...")
        snapshot_download(repo_id=model_id, local_dir=local_dir)
        print("  done.")

    print()
    print("All models downloaded into ./models/")
    print("Now run build_exe.bat to package them into the .exe.")


if __name__ == "__main__":
    main()
