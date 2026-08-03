"""
translator_engine.py
---------------------
Thin wrapper around AI4Bharat's IndicTrans2 models for English <-> Hindi / Marathi
translation.

Why IndicTrans2 (not IndicTrans3)?
IndicTrans3 (beta) is built on Gemma-3 and expects vLLM + GPU serving, which does not
package into a lightweight offline Windows .exe. IndicTrans2's distilled 200M models
run comfortably on CPU and are the practical choice for an offline desktop tool.

Model layout (IndicTrans2 is direction-specific, not one bidirectional model):
    en -> hi/mr   : ai4bharat/indictrans2-en-indic-dist-200M
    hi/mr -> en   : ai4bharat/indictrans2-indic-en-dist-200M

Both models are "gated" on Hugging Face: you must log in once with a token that has
accepted the model license before the first download will succeed:

    huggingface-cli login

Language tags used by IndicTrans2 (FLORES-200 style):
    English -> eng_Latn
    Hindi   -> hin_Deva
    Marathi -> mar_Deva
"""

from __future__ import annotations

import threading
from typing import List

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

# Note: we use our own pure-Python port of IndicTransToolkit's IndicProcessor
# (see indic_processor.py) rather than the IndicTransToolkit package itself.
# IndicTransToolkit ships its processor as a compiled Cython extension with no
# Windows wheels, requiring the Microsoft C++ Build Tools to install on
# Windows. Our port has identical logic but only depends on pure-Python /
# prebuilt-wheel libraries (indic-nlp-library, sacremoses, regex), so it
# installs on Windows with nothing extra.
from indic_processor import IndicProcessor


# ---------------------------------------------------------------------------
# Language configuration
# ---------------------------------------------------------------------------

LANG_TAGS = {
    "English": "eng_Latn",
    "Hindi": "hin_Deva",
    "Marathi": "mar_Deva",
}

EN_INDIC_MODEL = "ai4bharat/indictrans2-en-indic-dist-200M"
INDIC_EN_MODEL = "ai4bharat/indictrans2-indic-en-dist-200M"

# Batch size for a single generate() call. Larger = faster but more RAM/VRAM.
DEFAULT_BATCH_SIZE = 8


class TranslationEngine:
    """
    Lazily loads whichever IndicTrans2 checkpoint a translation direction needs,
    and caches it for reuse. Thread-safe enough for a single background worker
    thread driven by the GUI (see gui.py).
    """

    def __init__(self, device: str | None = None, batch_size: int = DEFAULT_BATCH_SIZE):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size
        self._lock = threading.Lock()

        self._models: dict[str, AutoModelForSeq2SeqLM] = {}
        self._tokenizers: dict[str, AutoTokenizer] = {}
        self._processor = IndicProcessor(inference=True)

        self.on_status = None  # optional callback(str) for GUI progress messages

    # -- internal helpers ----------------------------------------------------

    def _log(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def _model_name_for(self, src_lang: str, tgt_lang: str) -> str:
        if src_lang == "English":
            return EN_INDIC_MODEL
        if tgt_lang == "English":
            return INDIC_EN_MODEL
        raise ValueError(
            "Direct Hindi <-> Marathi translation is not supported by these "
            "IndicTrans2 checkpoints. Route through English, or use the "
            "indic-indic model variant instead."
        )

    def _ensure_loaded(self, model_name: str) -> None:
        if model_name in self._models:
            return
        with self._lock:
            if model_name in self._models:  # re-check after acquiring the lock
                return
            self._log(f"Loading model {model_name} (first run downloads it)...")
            tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                trust_remote_code=True,
                dtype=dtype,
            ).to(self.device)
            model.eval()
            self._tokenizers[model_name] = tokenizer
            self._models[model_name] = model
            self._log(f"Model {model_name} ready.")

    # -- public API ------------------------------------------------------------

    def translate_batch(
        self, texts: List[str], src_lang: str, tgt_lang: str
    ) -> List[str]:
        """
        Translate a list of strings from src_lang to tgt_lang (both keys of
        LANG_TAGS, e.g. "English", "Hindi", "Marathi"). Empty/whitespace-only
        entries are passed through untranslated.
        """
        if src_lang == tgt_lang:
            return list(texts)

        if src_lang not in LANG_TAGS or tgt_lang not in LANG_TAGS:
            raise ValueError(f"Unsupported language pair: {src_lang} -> {tgt_lang}")

        # Keep track of which entries actually need translation.
        indices_to_translate = [i for i, t in enumerate(texts) if t and t.strip()]
        if not indices_to_translate:
            return list(texts)

        model_name = self._model_name_for(src_lang, tgt_lang)
        self._ensure_loaded(model_name)
        tokenizer = self._tokenizers[model_name]
        model = self._models[model_name]

        src_tag = LANG_TAGS[src_lang]
        tgt_tag = LANG_TAGS[tgt_lang]

        results = list(texts)  # copy; untouched entries stay as-is

        subset = [texts[i] for i in indices_to_translate]
        translated_subset: List[str] = []

        for start in range(0, len(subset), self.batch_size):
            chunk = subset[start : start + self.batch_size]
            self._log(f"Translating {start + len(chunk)}/{len(subset)} segments...")

            batch = self._processor.preprocess_batch(chunk, src_lang=src_tag, tgt_lang=tgt_tag)
            inputs = tokenizer(
                batch,
                truncation=True,
                padding="longest",
                return_tensors="pt",
                return_attention_mask=True,
            ).to(self.device)

            with torch.no_grad():
                generated_tokens = model.generate(
                    **inputs,
                    # NOTE: IndicTrans2's custom modeling code (modeling_indictrans.py)
                    # assumes past_key_values is either None or a legacy tuple-of-tuples.
                    # Recent `transformers` versions instead pass a Cache object once
                    # use_cache=True, which breaks a `past_key_values[0][0].shape` check
                    # inside the model's own forward() with:
                    #   AttributeError: 'NoneType' object has no attribute 'shape'
                    # Disabling the cache avoids that incompatible code path entirely.
                    # Generation is somewhat slower as a result (no KV-cache reuse
                    # across beam-search steps), but it is correct on current
                    # transformers versions.
                    use_cache=False,
                    min_length=0,
                    max_length=256,
                    num_beams=5,
                    num_return_sequences=1,
                )

            decoded = tokenizer.batch_decode(
                generated_tokens,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )
            translated_subset.extend(self._processor.postprocess_batch(decoded, lang=tgt_tag))

        for i, translated in zip(indices_to_translate, translated_subset):
            results[i] = translated

        return results

    def translate_one(self, text: str, src_lang: str, tgt_lang: str) -> str:
        return self.translate_batch([text], src_lang, tgt_lang)[0]
