"""Rozpoznawanie języków programowania w tytułach/treściach ofert.

Celowo konserwatywna lista: tylko jasne, jednoznaczne sygnatury (np. 'Go'
rozpoznawane wyłącznie przez 'golang', żeby nie łapać słówka 'go' z tekstu).
"""
from __future__ import annotations

import re

_LANG_PATTERNS = (
    ("Python", re.compile(r"\bpython\b", re.I)),
    ("JavaScript", re.compile(r"\bjavascript\b|\bjs\b(?![\w])", re.I)),
    ("TypeScript", re.compile(r"\btypescript\b|\bts\b(?![\w])", re.I)),
    ("Java", re.compile(r"\bjava\b(?!\s*script)", re.I)),
    ("Kotlin", re.compile(r"\bkotlin\b", re.I)),
    ("Swift", re.compile(r"\bswift\b", re.I)),
    ("PHP", re.compile(r"\bphp\b", re.I)),
    ("Ruby", re.compile(r"\bruby\b|\brails\b", re.I)),
    ("Rust", re.compile(r"\brust\b", re.I)),
    ("Go", re.compile(r"\bgolang\b", re.I)),
    ("C++", re.compile(r"\bc\+\+(?!\w)", re.I)),
    ("C#", re.compile(r"\bc\s*#(?!\w)", re.I)),
    ("Scala", re.compile(r"\bscala\b", re.I)),
    # 'C' na końcu — żeby nie podchwycić C++/C#/wielu słów
    ("C", re.compile(r"\bc\b(?!\+\+|#)", re.I)),
)


def detect_languages(*texts: str | None) -> list[str]:
    """Zwraca listę języków znalezionych w połączonych tekstach (bez duplikatów)."""
    haystack = " ".join(text for text in texts if text)
    if not haystack:
        return []
    found = [name for name, pattern in _LANG_PATTERNS if pattern.search(haystack)]
    return found


def detect_languages_text(*texts: str | None) -> str:
    """Wariant zapisu do kolumny (CSV po przecinku)."""
    return ", ".join(detect_languages(*texts))