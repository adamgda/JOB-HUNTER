"""Rozpoznawanie języka TEKSTU oferty (polski/angielski/…).

Priorytet:
  1. Twardy heurystyczny sygnał Polski: diakrytyki + typowe słowa ogłoszeń.
  2. langdetect (deterministyczny, seed=0) na dłuższych tekstach.
  3. 'unknown', gdy tekstu jest za mało / nic nie pasuje.
"""
from __future__ import annotations

import re

_PL_DIACRITICS_RE = re.compile(r"[ąćęłńóśźż]")
_PL_WORDS_RE = re.compile(
    r"\b(prac(y|a)|praca zdaln\w+|wynagrodzen\w+|dołącz\w*|obowiązki|wymagani\w+|"
    r"zatrudni\w+|rekrutacj\w+|oferujemy|poszukujemy|full[- ]?etat|"
    r"warszaw\w+|kraków\w+|wrocław\w+|gdańsk\w*|poznań\w+|łodzi\w*)",
    re.I,
)
_EN_WORDS_RE = re.compile(
    r"\b(we are|you will|we're|experience|apply|applicants?|resume|position|"
    r"full[- ]?time|remote|hire|hiring|join our team|team)\b",
    re.I,
)
_MIN_LANGDETECT_LEN = 30
_MIN_LANGDETECT_PROB = 0.6
# rozpoznajemy w praktyce tylko te języki (polski rynek) — reszta to na krótkich
# tekstach szum (af/id/ro…); niestandardowe wymagają wyższej pewności
_ACCEPTED_LANGS = {"pl", "en", "de", "fr", "es", "it", "nl", "uk", "ru", "cs", "pt"}
_THRESHOLDS = {"pl": 0.5, "en": 0.55}


def detect_text_lang(*texts: str | None) -> str:
    """Zwraca kod języka ('pl', 'en', 'de', …) lub 'unknown'.

    Kolejność celowo od najpewniejszego sygnału:
      1. diakrytyki PL (praktycznie nie mylą się z innymi językami),
      2. langdetect (deterministyczny; próg pewności) dla dłuższych tekstów,
      3. heurystyki słowne PL/EN dla krótkich tekstów,
      4. 'unknown', gdy nic nie pasuje.
    """
    haystack = " ".join(text.strip() for text in texts if text and text.strip())
    if not haystack:
        return "unknown"
    # 1) twardy sygnał PL
    if _PL_DIACRITICS_RE.search(haystack):
        return "pl"
    # 2) langdetect
    if len(haystack) >= _MIN_LANGDETECT_LEN:
        try:
            from langdetect import DetectorFactory, detect_langs

            DetectorFactory.seed = 0  # deterministyczne wyniki
            top = detect_langs(haystack[:2000])
            if top and top[0].lang in _ACCEPTED_LANGS:
                threshold = _THRESHOLDS.get(top[0].lang, 0.9)
                if top[0].prob >= threshold:
                    return top[0].lang
        except Exception:  # noqa: BLE001 — degradacja do heurystyk
            pass
    # 3) słowa kluczowe
    if _PL_WORDS_RE.search(haystack):
        return "pl"
    if _EN_WORDS_RE.search(haystack):
        return "en"
    return "unknown"