"""Tiny Syriac fixture index for API tests (no network, no full corpus)."""
import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("DOCS_ENABLED", "false")
os.environ.pop("API_KEY", None)
os.environ.pop("STATIC_DIR", None)

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search import consonantal  # noqa: E402

FIX_DIR = Path(__file__).resolve().parent / ".tmp"
FIX_DIR.mkdir(exist_ok=True)
FIX_DB = FIX_DIR / "fixture.db"
if FIX_DB.exists():
    FIX_DB.unlink()

_SCHEMA = """
CREATE VIRTUAL TABLE verses USING fts5(
  verse_id UNINDEXED, book UNINDEXED, book_name UNINDEXED,
  chapter UNINDEXED, verse UNINDEXED, text, norm,
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE words (
  verse_id TEXT NOT NULL,
  pos INTEGER NOT NULL,
  surface TEXT NOT NULL,
  norm TEXT NOT NULL,
  strongs TEXT,
  source TEXT NOT NULL
);
CREATE TABLE lemmas (
  strongs TEXT PRIMARY KEY,
  display TEXT NOT NULL,
  n_forms INTEGER NOT NULL,
  n_occur INTEGER NOT NULL
);
CREATE TABLE strongs_expand (
  strongs TEXT NOT NULL,
  related TEXT NOT NULL,
  PRIMARY KEY (strongs, related)
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

# Syriac strings as escapes
BRESHIT = "\u0712\u072a\u071d\u072b\u071d\u072c"  # ܒܪܝܫܝܬ
BRA = "\u0712\u072a\u0710"  # ܒܪܐ
ALAHA = "\u0710\u0720\u0717\u0710"  # ܐܠܗܐ
WEMAR = "\u0718\u0710\u0721\u072a"  # ܘܐܡܪ
RISH = "\u072a\u071d\u072b"  # ܪܝܫ
NAHRA = "\u0722\u0717\u072a\u0710"  # ܢܗܪܐ
KTABA = "\u071f\u072c\u0712\u0710"  # ܟܬܒܐ
DYALID = "\u0715\u071d\u0720\u071d\u0715\u0718\u072c\u0717"  # ܕܝܠܝܕܘܬܗ
WABADU = "\u0718\u0725\u0712\u0715\u0718"  # waw ayin beth dalath waw
KLILA = "\u071f\u0720\u071d\u0720\u0710"  # ܟܠܝܠܐ
RISH_A = "\u072a\u071d\u072b\u0710"  # ܪܝܫܐ
RESHITA = "\u072a\u071d\u072b\u071d\u072c\u0710"  # rish yodh shin yodh taw aleph

_RAW_VERSES = [
    ("GEN.1.1", "GEN", "Genesis", 1, 1, f"{BRESHIT} {BRA} {ALAHA}"),
    ("GEN.1.3", "GEN", "Genesis", 1, 3, f"{WEMAR} {ALAHA}"),
    ("GEN.2.10", "GEN", "Genesis", 2, 10, f"{RISH} {NAHRA}"),
    ("MAT.1.1", "MAT", "Matthew", 1, 1, f"{KTABA} {DYALID}"),
    ("EXO.39.30", "EXO", "Exodus", 39, 30, f"{WABADU} {KLILA}"),
]
_VERSES = [(*row, consonantal(row[-1])) for row in _RAW_VERSES]

_RAW_WORDS = [
    ("GEN.1.1", 0, BRESHIT, "L3019", "sedra3"),
    ("GEN.1.1", 1, BRA, "L328", "sedra3"),
    ("GEN.1.1", 2, ALAHA, "L130", "sedra3"),
    ("GEN.1.3", 1, ALAHA, "L130", "sedra3"),
    ("GEN.2.10", 0, RISH, "L3017", "sedra3"),
    ("MAT.1.1", 0, KTABA, "L2000", "sedra3"),
    ("EXO.39.30", 1, KLILA, "L1500", "sedra3"),
]
_WORDS = [
    (vid, pos, surface, consonantal(surface), strongs, source)
    for vid, pos, surface, strongs, source in _RAW_WORDS
]
_LEMMAS = [
    ("L130", f"{ALAHA} · God", 1, 2),
    ("L328", f"{BRA} · create", 1, 1),
    ("L3017", f"{RISH_A} · head", 1, 1),
    ("L3019", f"{RESHITA} · beginning", 1, 1),
    ("L2000", f"{KTABA} · book", 1, 1),
    ("L1500", f"{KLILA} · crown", 1, 1),
]
_EXPAND = [
    ("L130", "L130"),
    ("L328", "L328"),
    ("L3017", "L3017"),
    ("L3017", "L3019"),
    ("L3019", "L3019"),
    ("L3019", "L3017"),
    ("L2000", "L2000"),
    ("L1500", "L1500"),
]

_db = sqlite3.connect(FIX_DB)
_db.executescript(_SCHEMA)
_db.executemany("INSERT INTO verses VALUES (?,?,?,?,?,?,?)", _VERSES)
_db.executemany("INSERT INTO words VALUES (?,?,?,?,?,?)", _WORDS)
_db.executemany("INSERT INTO lemmas VALUES (?,?,?,?)", _LEMMAS)
_db.executemany("INSERT INTO strongs_expand VALUES (?,?)", _EXPAND)
_db.executemany(
    "INSERT INTO meta VALUES (?,?)",
    [
        ("verses", "5"),
        ("tokens", "7"),
        ("lemmas", "6"),
        ("strongs_expand", str(len(_EXPAND))),
    ],
)
_db.commit()
_db.close()

os.environ["SEARCH_DB"] = str(FIX_DB)
