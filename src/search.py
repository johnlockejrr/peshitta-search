#!/usr/bin/env python3
"""Search the Peshitta index built by scripts/build_index.py."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from books import BOOK_CODES, BOOK_ORDER
from syriac_norm import consonants_only

MODES = ("exact", "lemma", "prefix", "substr")


def _book_codes(book: str | None) -> set[str] | None:
    if not book:
        return None
    return {part.strip().upper() for part in book.split(",") if part.strip()}


def consonantal(s: str) -> str:
    """Reduce Syriac to consonants (keep spaces for phrases).

    Strips vowels/points and seyame so vocalized paste matches the index.
    Maps ܖ → ܪ for SEDRA-compatible orthography.
    """
    parts = []
    for word in re.split(r"(\s+)", s):
        if not word or word.isspace():
            if word and word.isspace():
                parts.append(" ")
            continue
        n = consonants_only(word)
        if n:
            parts.append(n)
    # collapse whitespace between words
    return " ".join(p for p in "".join(parts).split() if p)


@dataclass
class Hit:
    verse_id: str
    book_name: str
    chapter: int
    verse: int
    text: str
    matches: list[str]


class Index:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(
            f"file:{path}?mode=ro", uri=True, check_same_thread=False
        )
        self.db.row_factory = sqlite3.Row

    def stats(self) -> dict:
        return {r["key"]: r["value"] for r in self.db.execute("SELECT * FROM meta")}

    def lemma_of(self, word: str) -> list[dict]:
        n = consonantal(word)
        rows = self.db.execute(
            """SELECT DISTINCT w.strongs, l.display, l.n_forms, l.n_occur
                 FROM words w JOIN lemmas l ON l.strongs = w.strongs
                WHERE w.norm = ? ORDER BY l.n_occur DESC""",
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]

    def forms_of(self, word: str) -> list[str]:
        return [row["form"] for row in self.form_rows_of(word)]

    def form_rows_of(self, word: str) -> list[dict]:
        related = self._expand_strongs(self._strongs_for_norm(consonantal(word)))
        if not related:
            return []
        qs = ",".join("?" * len(related))
        return self._form_rows(f"strongs IN ({qs})", tuple(related))

    def forms_for(self, strongs: str) -> list[str]:
        return [row["form"] for row in self.form_rows_for(strongs)]

    def form_rows_for(self, strongs: str) -> list[dict]:
        related = self._expand_strongs([strongs])
        qs = ",".join("?" * len(related))
        return self._form_rows(f"strongs IN ({qs})", tuple(related))

    def _strongs_for_norm(self, nq: str) -> list[str]:
        return [
            r["strongs"]
            for r in self.db.execute(
                "SELECT DISTINCT strongs FROM words WHERE norm = ? AND strongs IS NOT NULL",
                (nq,),
            )
        ]

    def _expand_strongs(self, keys: list[str]) -> list[str]:
        if not keys:
            return []
        out: list[str] = []
        seen: set[str] = set()
        has_table = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='strongs_expand'"
        ).fetchone()
        for key in keys:
            related: list[str] = []
            if has_table:
                related = [
                    r["related"]
                    for r in self.db.execute(
                        "SELECT related FROM strongs_expand WHERE strongs = ?", (key,)
                    )
                ]
            if not related:
                related = [key]
            for item in related:
                if item not in seen:
                    seen.add(item)
                    out.append(item)
        return out

    def _form_rows(self, where: str, params: tuple) -> list[dict]:
        rows = self.db.execute(
            f"""SELECT surface AS form, n FROM (
                    SELECT surface, norm, count(*) AS n,
                           row_number() OVER (
                             PARTITION BY norm
                             ORDER BY count(*) DESC, length(surface), surface
                           ) AS rn
                      FROM words WHERE {where}
                      GROUP BY surface, norm
                ) WHERE rn = 1
                ORDER BY n DESC, length(norm), norm""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def search(
        self,
        q: str,
        mode: str = "lemma",
        order: str = "canonical",
        page: int = 1,
        size: int = 20,
        book: str | None = None,
        strongs: str | None = None,
    ) -> tuple[list[Hit], int]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        nq = consonantal(q)
        if not nq:
            return [], 0
        if " " in nq:
            return self._phrase(nq, order, page, size, book)
        where, params = self._word_predicate(nq, mode, strongs)
        if where is None:
            return [], 0
        sql = f"""
            SELECT w.verse_id, group_concat(DISTINCT w.surface) AS matches
              FROM words w WHERE {where}
          GROUP BY w.verse_id"""
        rows = self.db.execute(sql, params).fetchall()
        by_verse = {r["verse_id"]: r["matches"].split(",") for r in rows}
        return self._materialise(by_verse, order, page, size, book, nq)

    def _word_predicate(self, nq: str, mode: str, strongs: str | None = None):
        if mode == "exact":
            return "w.norm = ?", (nq,)
        if mode == "prefix":
            return "w.norm LIKE ? ESCAPE '\\'", (self._like(nq) + "%",)
        if mode == "substr":
            return "w.norm LIKE ? ESCAPE '\\'", ("%" + self._like(nq) + "%",)
        if strongs:
            related = self._expand_strongs([strongs])
        else:
            related = self._expand_strongs(self._strongs_for_norm(nq))
        if related:
            qs = ",".join("?" * len(related))
            return f"w.strongs IN ({qs})", tuple(related)
        return "w.norm = ?", (nq,)

    @staticmethod
    def _like(s: str) -> str:
        return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _phrase(self, nq, order, page, size, book):
        rows = self.db.execute(
            "SELECT verse_id FROM verses WHERE norm MATCH ?",
            ('"' + nq.replace('"', " ") + '"',),
        ).fetchall()
        by_verse = {r["verse_id"]: nq.split() for r in rows}
        return self._materialise(by_verse, order, page, size, book, nq)

    def _materialise(self, by_verse: dict[str, list[str]], order, page, size, book, nq):
        if not by_verse:
            return [], 0
        ids = list(by_verse)
        qs = ",".join("?" * len(ids))
        sql = f"""SELECT verse_id, book, book_name, chapter, verse, text
                    FROM verses WHERE verse_id IN ({qs})"""
        rows = [dict(r) for r in self.db.execute(sql, list(ids))]
        codes = _book_codes(book)
        if codes:
            rows = [r for r in rows if r["verse_id"].split(".")[0] in codes]
        if order == "relevance":
            rows.sort(
                key=lambda r: (-len(by_verse[r["verse_id"]]), self._canon(r["verse_id"]))
            )
        else:
            rows.sort(key=lambda r: self._canon(r["verse_id"]))
        total = len(rows)
        start = (page - 1) * size
        page_rows = rows[start : start + size]
        hits = [
            Hit(
                r["verse_id"],
                r["book_name"],
                int(r["chapter"]),
                int(r["verse"]),
                r["text"],
                sorted(set(by_verse[r["verse_id"]])),
            )
            for r in page_rows
        ]
        return hits, total

    @staticmethod
    def _canon(vid: str):
        b, c, v = vid.split(".")
        return (BOOK_ORDER.get(b, 999), int(c), int(v))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query")
    ap.add_argument("--db", default="data/peshitta.db")
    ap.add_argument("--mode", default="lemma", choices=MODES)
    ap.add_argument("--order", default="canonical", choices=("canonical", "relevance"))
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--size", type=int, default=10)
    ap.add_argument("--book", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--forms", action="store_true")
    a = ap.parse_args()

    ix = Index(a.db)
    if a.forms:
        for lem in ix.lemma_of(a.query):
            print(
                f"{lem['strongs']:>10}  {lem['display']:20} "
                f"{lem['n_forms']:3} forms, {lem['n_occur']:4} occ"
            )
        print(" ".join(ix.forms_of(a.query)))
        return

    hits, total = ix.search(a.query, a.mode, a.order, a.page, a.size, a.book)
    if a.json:
        print(
            json.dumps(
                {"total": total, "hits": [asdict(h) for h in hits]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    print(f"{total} verses  ({a.mode})\n")
    for h in hits:
        print(f"{h.book_name} {h.chapter}:{h.verse}  [{' '.join(h.matches)}]")
        print(f"  {h.text}\n")


if __name__ == "__main__":
    main()
