"""Thai text normalization and a Thai-aware tokenizer for TF-IDF search."""
from __future__ import annotations

import re
import unicodedata
from typing import List

from pythainlp.corpus import thai_stopwords
from pythainlp.tokenize import word_tokenize
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Shifted/lowered glyph variants that Thai fonts such as TH Sarabun PSK place in the
# Private Use Area; PDFs made from Word often expose them as text.
_PUA_TO_THAI = str.maketrans({
    "\uf700": "\u0e10", "\uf701": "\u0e34", "\uf702": "\u0e35", "\uf703": "\u0e36",
    "\uf704": "\u0e37", "\uf705": "\u0e48", "\uf706": "\u0e49", "\uf707": "\u0e4a",
    "\uf708": "\u0e4b", "\uf709": "\u0e4c", "\uf70a": "\u0e48", "\uf70b": "\u0e49",
    "\uf70c": "\u0e4a", "\uf70d": "\u0e4b", "\uf70e": "\u0e4c", "\uf70f": "\u0e0d",
    "\uf710": "\u0e31", "\uf711": "\u0e4d", "\uf712": "\u0e47", "\uf713": "\u0e48",
    "\uf714": "\u0e49", "\uf715": "\u0e4a", "\uf716": "\u0e4b", "\uf717": "\u0e4c",
    "\uf718": "\u0e38", "\uf719": "\u0e39", "\uf71a": "\u0e3a",
})
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"))
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

_REPEATED_MARK = re.compile(r"([\u0e31\u0e34-\u0e3a\u0e47-\u0e4e])\1+")
# tone mark / thanthakhat typed before an upper vowel: เกี่ยว must be ก + ี + ่, not ก + ่ + ี
_TONE_BEFORE_VOWEL = re.compile(r"([\u0e48-\u0e4c])([\u0e31\u0e34-\u0e37\u0e47])")
# sara am split into nikhahit + sara aa (what Tesseract outputs), optionally with a tone mark between
_SPLIT_SARA_AM = re.compile(r"\u0e4d([\u0e48-\u0e4b]?)\u0e32")

# A run of Thai characters (letters, vowels, marks), allowing single spaces inside it,
# which OCR often inserts in the middle of words.
_THAI_RUN = re.compile(r"[\u0e01-\u0e4e]+(?: [\u0e01-\u0e4e]+)*")
_WORD = re.compile(r"(?u)\b\w\w+\b")  # scikit-learn's default token_pattern

STOP_WORDS = frozenset(ENGLISH_STOP_WORDS) | frozenset(thai_stopwords())


def normalize_thai(text: str) -> str:
    """Canonical form for stored text. Uses NFC, never NFKC: NFKC would split ำ again."""
    text = unicodedata.normalize("NFC", text.translate(_PUA_TO_THAI).translate(_ZERO_WIDTH))
    text = _REPEATED_MARK.sub(r"\1", text)
    text = _TONE_BEFORE_VOWEL.sub(r"\2\1", text)
    text = _SPLIT_SARA_AM.sub("\\1\u0e33", text)
    return text.replace("\u0e40\u0e40", "\u0e41")  # เเ typed for แ


def tokenize(text: str) -> List[str]:
    """
    Search tokens: Thai runs are split into words with PyThaiNLP (newmm), everything
    else uses scikit-learn's default pattern. Stop words (English + Thai) are dropped.
    Module-level so the pickled TfidfVectorizer can find it again.
    """
    text = normalize_thai(text).translate(_THAI_DIGITS)
    tokens: List[str] = []
    pos = 0
    for m in _THAI_RUN.finditer(text):
        tokens += _WORD.findall(text[pos:m.start()])
        run = m.group().replace(" ", "")
        tokens += [t for t in word_tokenize(run, engine="newmm", keep_whitespace=False) if t.strip()]
        pos = m.end()
    tokens += _WORD.findall(text[pos:])
    return [t for t in tokens if t not in STOP_WORDS]
