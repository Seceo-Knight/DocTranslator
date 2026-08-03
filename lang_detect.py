"""
lang_detect.py
--------------
Best-effort auto-detection restricted to the three languages this tool
supports: English, Hindi, Marathi.

langdetect (a Python port of Google's language-detection library) returns ISO
codes ('en', 'hi', 'mr', ...). Hindi and Marathi share the Devanagari script,
so langdetect's n-gram model can occasionally confuse short/ambiguous samples.
Because of that, this is offered as a convenience default in the GUI, with the
user always able to override it manually -- do not rely on it for correctness.
"""

from __future__ import annotations

from typing import List, Optional

_CODE_TO_NAME = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
}


def detect_language(text: str) -> Optional[str]:
    """
    Returns "English", "Hindi", or "Marathi", or None if detection failed or
    the text isn't confidently one of the three.
    """
    text = (text or "").strip()
    if not text:
        return None

    try:
        from langdetect import detect_langs
    except ImportError:
        return None

    try:
        candidates = detect_langs(text)
    except Exception:
        return None

    for candidate in candidates:
        name = _CODE_TO_NAME.get(candidate.lang)
        if name:
            return name
    return None


def detect_language_for_document(sample_texts: List[str], max_samples: int = 20) -> Optional[str]:
    """
    Detects language from a handful of representative text segments (e.g. the
    first N non-empty paragraphs) rather than a single line, which is more
    robust for short paragraphs/table cells.
    """
    votes: dict[str, int] = {}
    for text in sample_texts[:max_samples]:
        result = detect_language(text)
        if result:
            votes[result] = votes.get(result, 0) + 1

    if not votes:
        return None
    return max(votes, key=votes.get)
