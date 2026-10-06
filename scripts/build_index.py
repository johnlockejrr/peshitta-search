#!/usr/bin/env python3
"""Build the Peshitta search index (SQLite + FTS5) from sedra4sqlite DBs.

    python scripts/build_index.py \
        --corpus /path/to/sedra4sqlite/data/corpus.db \
        --sedra  /path/to/sedra4sqlite/data/sedra.db \
        --english /path/to/sedra4sqlite/data/SEDRA/tblEnglish.txt \
        --out data/peshitta.db

Schema matches Samaritanus (verses FTS5, words, lemmas, strongs_expand, meta)
so the search API can stay nearly identical. Lemma keys:

  L{keyLexeme}   SEDRA 3 lexeme
  S4{lexeme_id}  SEDRA 4 API lexeme

Root mode expands SEDRA 3 lexemes that share a keyRoot, and SEDRA 4
lexemes that share the same stem.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from books import BOOKS, verse_id  # noqa: E402
from syriac_norm import consonants_only  # noqa: E402

SCHEMA = """
PRAGMA journal_mode=DELETE;
DROP TABLE IF EXISTS verses;
DROP TABLE IF EXISTS words;
DROP TABLE IF EXISTS lemmas;
DROP TABLE IF EXISTS strongs_expand;
DROP TABLE IF EXISTS meta;

CREATE VIRTUAL TABLE verses USING fts5(
  verse_id UNINDEXED, book UNINDEXED, book_name UNINDEXED,
  chapter UNINDEXED, verse UNINDEXED,
  text,
  norm,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE words (
  verse_id TEXT NOT NULL,
  pos      INTEGER NOT NULL,
  surface  TEXT NOT NULL,
  norm     TEXT NOT NULL,
  strongs  TEXT,
  source   TEXT NOT NULL
);
CREATE INDEX words_strongs ON words(strongs);
CREATE INDEX words_norm    ON words(norm);
CREATE INDEX words_verse   ON words(verse_id);

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
CREATE INDEX strongs_expand_related ON strongs_expand(related);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def load_english(path: Path) -> dict[int, str]:
    """keyLexeme -> first English gloss."""
    out: dict[int, str] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                lex = int(row["keyLexeme"])
            except (KeyError, ValueError, TypeError):
                continue
            if lex in out:
                continue
            meaning = (row.get("strMeaning") or "").strip()
            if meaning:
                out[lex] = meaning
    return out


def load_sedra3(sedra_path: Path, english: dict[int, str]):
    """Return (lexeme_meta, root_to_lexemes).

    lexeme_meta[keyLexeme] = {root, display, gloss}
    """
    conn = sqlite3.connect(f"file:{sedra_path}?mode=ro&immutable=1", uri=True)
    roots = {
        r: syr
        for r, syr in conn.execute("SELECT keyRoot, syriac FROM roots")
    }
    lexeme_meta: dict[int, dict] = {}
    root_to_lexemes: dict[int, list[int]] = collections.defaultdict(list)
    for key_lex, key_root, syr in conn.execute(
        "SELECT keyLexeme, keyRoot, syriac FROM lexemes"
    ):
        display = syr or roots.get(key_root, "")
        gloss = english.get(key_lex, "")
        lexeme_meta[key_lex] = {
            "root": key_root,
            "display": display,
            "gloss": gloss,
        }
        root_to_lexemes[key_root].append(key_lex)
    conn.close()
    return lexeme_meta, root_to_lexemes


def sedra4_gloss(payload: str | None) -> str:
    if not payload:
        return ""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, list) or not data:
        return ""
    glosses = data[0].get("glosses") or {}
    eng = glosses.get("eng") or []
    if isinstance(eng, list) and eng:
        return str(eng[0]).rstrip(".")
    syr = glosses.get("syr") or []
    if isinstance(syr, list) and syr:
        return str(syr[0])
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--sedra", type=Path, required=True)
    ap.add_argument("--english", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("data/peshitta.db"))
    a = ap.parse_args()

    if not a.corpus.is_file():
        raise SystemExit(f"missing corpus DB: {a.corpus}")
    if not a.sedra.is_file():
        raise SystemExit(f"missing SEDRA DB: {a.sedra}")

    english_path = a.english
    if english_path is None:
        english_path = a.sedra.parent / "SEDRA" / "tblEnglish.txt"

    print("loading SEDRA 3 lexicon + English glosses ...")
    english = load_english(english_path)
    lexeme_meta, root_to_lexemes = load_sedra3(a.sedra, english)
    print(f"  {len(lexeme_meta)} lexemes, {len(english)} English glosses")

    corpus = sqlite3.connect(f"file:{a.corpus}?mode=ro&immutable=1", uri=True)
    corpus.row_factory = sqlite3.Row

    # SEDRA 4: lexeme_id -> stem / gloss / display
    s4_meta: dict[int, dict] = {}
    for row in corpus.execute(
        "SELECT lexeme_id, stem, syriac, payload FROM sedra4_forms WHERE ok = 1 AND lexeme_id IS NOT NULL"
    ):
        lid = int(row["lexeme_id"])
        if lid in s4_meta:
            continue
        stem = row["stem"] or row["syriac"] or ""
        s4_meta[lid] = {
            "stem": stem,
            "display": row["syriac"] or stem,
            "gloss": sedra4_gloss(row["payload"]),
        }
    stem_to_s4: dict[str, list[int]] = collections.defaultdict(list)
    for lid, meta in s4_meta.items():
        stem = meta["stem"] or meta["display"]
        if stem:
            stem_to_s4[stem].append(lid)

    print("reading corpus tokens ...")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.out.is_file():
        a.out.unlink()
    db = sqlite3.connect(a.out)
    db.executescript(SCHEMA)

    stats = collections.Counter()
    word_rows: list[tuple] = []
    verse_rows: list[tuple] = []
    lemma_forms: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    lemma_display: dict[str, str] = {}

    verses = list(
        corpus.execute(
            "SELECT verse_id, book, book_number, chapter, verse, text_display "
            "FROM verses ORDER BY book_number, chapter, verse"
        )
    )
    # Preload tokens+morph by corpus verse_id
    morph_by_token: dict[int, sqlite3.Row] = {
        r["token_id"]: r
        for r in corpus.execute("SELECT * FROM token_morph")
    }

    for v in verses:
        bn = int(v["book_number"])
        if bn not in BOOKS:
            continue
        code, book_name = BOOKS[bn]
        vid = verse_id(bn, int(v["chapter"]), int(v["verse"]))
        text = v["text_display"] or ""
        toks = list(
            corpus.execute(
                "SELECT id, position, surface, lookup_plain FROM tokens "
                "WHERE verse_id = ? ORDER BY position",
                (v["verse_id"],),
            )
        )
        norms: list[str] = []
        for t in toks:
            surface = t["surface"] or ""
            n = consonants_only(surface) or consonants_only(t["lookup_plain"] or "")
            if not n:
                continue
            norms.append(n)
            morph = morph_by_token.get(t["id"])
            strongs = None
            src = "unmatched"
            if morph is None:
                src = "unmatched"
            elif morph["source"] == "sedra3" and morph["keyLexeme"] is not None:
                key_lex = int(morph["keyLexeme"])
                strongs = f"L{key_lex}"
                src = "sedra3"
                meta = lexeme_meta.get(key_lex, {})
                disp = meta.get("display") or n
                gloss = meta.get("gloss") or ""
                lemma_display[strongs] = f"{disp} · {gloss}" if gloss else disp
            elif morph["source"] == "sedra4" and morph["sedra4_lexeme_id"] is not None:
                lid = int(morph["sedra4_lexeme_id"])
                strongs = f"S4{lid}"
                src = "sedra4"
                meta = s4_meta.get(lid, {})
                disp = meta.get("display") or morph["stem"] or n
                gloss = meta.get("gloss") or ""
                lemma_display[strongs] = f"{disp} · {gloss}" if gloss else disp
            else:
                src = "unmatched"

            stats[src] += 1
            word_rows.append((vid, int(t["position"]), surface, n, strongs, src))
            if strongs:
                lemma_forms[strongs][n] += 1
                if strongs not in lemma_display:
                    lemma_display[strongs] = n

        verse_rows.append(
            (vid, code, book_name, int(v["chapter"]), int(v["verse"]), text, " ".join(norms))
        )

    print("building Root expand edges ...")
    expand_rows: list[tuple[str, str]] = []
    seen_pair: set[tuple[str, str]] = set()

    # SEDRA 3: all lexemes under the same root
    for _root, lex_ids in root_to_lexemes.items():
        keys = [f"L{i}" for i in lex_ids if f"L{i}" in lemma_forms]
        if not keys:
            continue
        for a_key in keys:
            for b_key in keys:
                pair = (a_key, b_key)
                if pair not in seen_pair:
                    seen_pair.add(pair)
                    expand_rows.append(pair)

    # SEDRA 4: group by stem
    for _stem, lids in stem_to_s4.items():
        keys = [f"S4{i}" for i in lids if f"S4{i}" in lemma_forms]
        if not keys:
            continue
        for a_key in keys:
            for b_key in keys:
                pair = (a_key, b_key)
                if pair not in seen_pair:
                    seen_pair.add(pair)
                    expand_rows.append(pair)

    # Self-edges for any lemma missing expand (safety)
    for key in lemma_forms:
        pair = (key, key)
        if pair not in seen_pair:
            seen_pair.add(pair)
            expand_rows.append(pair)

    db.executemany("INSERT INTO verses VALUES (?,?,?,?,?,?,?)", verse_rows)
    db.executemany("INSERT INTO words VALUES (?,?,?,?,?,?)", word_rows)
    db.executemany(
        "INSERT INTO lemmas VALUES (?,?,?,?)",
        [
            (
                s,
                lemma_display.get(s) or min(c, key=len),
                len(c),
                sum(c.values()),
            )
            for s, c in lemma_forms.items()
        ],
    )
    db.executemany("INSERT INTO strongs_expand VALUES (?,?)", expand_rows)
    tot = sum(stats.values())
    db.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [
            ("verses", str(len(verse_rows))),
            ("tokens", str(len(word_rows))),
            ("lemmas", str(len(lemma_forms))),
            ("strongs_expand", str(len(expand_rows))),
            ("coverage_sedra3", str(stats["sedra3"])),
            ("coverage_sedra4", str(stats["sedra4"])),
            ("coverage_none", str(stats["unmatched"])),
        ],
    )
    db.commit()
    db.execute("ANALYZE")
    db.commit()
    db.close()
    corpus.close()

    print(f"\nindexed {len(verse_rows)} verses, {tot} tokens, {len(lemma_forms)} lemmas")
    if tot:
        print(f"  SEDRA 3 : {stats['sedra3']:6d} ({stats['sedra3']/tot*100:5.1f}%)")
        print(f"  SEDRA 4 : {stats['sedra4']:6d} ({stats['sedra4']/tot*100:5.1f}%)")
        print(f"  unmatched: {stats['unmatched']:6d} ({stats['unmatched']/tot*100:5.1f}%)")
    print(f"\nwrote {a.out} ({a.out.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
