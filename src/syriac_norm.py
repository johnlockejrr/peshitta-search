"""Syriac normalization for search / SEDRA lookup.

Policy (checked against SEDRA 3):
- Strip vowels and most punctuation for *lookup*.
- Keep seyame (U+0308 COMBINING DIAERESIS / Syriac seyame) as a plural signal:
  SEDRA 3 stores this as keySeyame on ~3.9k word forms, and our Peshitta CSV
  marks plurals with ̈ on ~53k tokens.
- Display text can keep vowels; lookup keys are consonantal (+ optional seyame).
"""

from __future__ import annotations

import re
import unicodedata

# Syriac letters (consonants) U+0710–U+072C
_LETTER = re.compile(r"[\u0710-\u072C]")

# Combining diaeresis used as seyame in modern Unicode Peshitta texts
SEYAME = "\u0308"

# Some Peshitta editions use DOTLESS DALATH RISH (U+0716) for /r/; SEDRA uses RISH (U+072A).
RISH_VARIANTS = {
    "\u0716": "\u072A",  # ܖ → ܪ
}

# Common inseparable prefixes (longest first) for stem fallback
PREFIXES = (
    "ܘܕ",
    "ܘܒ",
    "ܘܠ",
    "ܘܡ",
    "ܘܐ",
    "ܕܒ",
    "ܕܠ",
    "ܕܡ",
    "ܒ",
    "ܕ",
    "ܘ",
    "ܠ",
    "ܡ",
)


def canonicalize_letters(text: str) -> str:
    """Map orthographic letter variants to SEDRA-friendly forms."""
    return "".join(RISH_VARIANTS.get(ch, ch) for ch in text)

# Characters to drop for lookup (vowels, dots, punctuation, spaces already split)
_STRIP_CATEGORIES = {
    # vowels / points in Syriac block U+0730–U+074A and related
}


def is_syriac_letter(ch: str) -> bool:
    return "\u0710" <= ch <= "\u072C"


def is_seyame(ch: str) -> bool:
    if ch == SEYAME:
        return True
    name = unicodedata.name(ch, "")
    return "SEYAME" in name


def is_vowel_or_point(ch: str) -> bool:
    o = ord(ch)
    # Syriac vocalization & points
    if 0x0730 <= o <= 0x074A:
        return True
    # qushshaya / rukkakha often U+0741 / U+0742
    if o in (0x0741, 0x0742):
        return True
    name = unicodedata.name(ch, "")
    if any(
        k in name
        for k in (
            "VOWEL",
            "PTHAHA",
            "ZQAPHA",
            "RBASA",
            "HBASA",
            "ESASA",
            "RWHA",
            "QUSHSHAYA",
            "RUKKAKHA",
        )
    ):
        return True
    # combining dot below used as spirantization in some editions
    if ch in ("\u0323", "\u0324", "\u0307", "\u032D"):
        return True
    return False


def is_punct(ch: str) -> bool:
    if ch.isspace():
        return True
    cat = unicodedata.category(ch)
    if cat.startswith("P") or cat == "Po":
        return True
    name = unicodedata.name(ch, "")
    if name.startswith("SYRIAC") and any(
        k in name for k in ("COLON", "STOP", "PARAGRAPH", "OBLIQUE", "MARK")
    ):
        return True
    return ch in ".:;!?,\"'“”‘’()[]{}<>«»–—…|"


def consonants_with_seyame(text: str) -> str:
    """Lookup key: Syriac letters + seyame only (vowels/punct stripped)."""
    text = unicodedata.normalize("NFC", canonicalize_letters(text))
    out: list[str] = []
    for ch in text:
        if is_syriac_letter(ch) or is_seyame(ch):
            out.append(ch)
    return "".join(out)


def consonants_only(text: str) -> str:
    """Strict consonants — no seyame — for fallback matching against SEDRA forms."""
    text = unicodedata.normalize("NFC", canonicalize_letters(text))
    return "".join(ch for ch in text if is_syriac_letter(ch))


def strip_prefixes(plain: str) -> list[str]:
    """Return plain plus candidates with common prefixes removed (longest first)."""
    out = [plain]
    seen = {plain}
    for pref in PREFIXES:
        if plain.startswith(pref) and len(plain) > len(pref) + 1:
            cand = plain[len(pref) :]
            if cand not in seen:
                seen.add(cand)
                out.append(cand)
    return out


def display_clean(text: str) -> str:
    """Verse display: strip punctuation but keep letters, vowels, seyame."""
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    for ch in text:
        if is_punct(ch) and not ch.isspace():
            continue
        out.append(ch)
    # collapse spaces
    return re.sub(r"\s+", " ", "".join(out)).strip()


def tokenize_verse(text: str) -> list[str]:
    """Split a verse into word tokens (punctuation as separators)."""
    text = unicodedata.normalize("NFC", text)
    buf: list[str] = []
    tokens: list[str] = []
    for ch in text:
        if is_punct(ch) or ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens
