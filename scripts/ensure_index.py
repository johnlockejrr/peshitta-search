#!/usr/bin/env python3
"""Build data/peshitta.db from sedra4sqlite if missing."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sedra_root() -> Path:
    env = os.environ.get("SEDRA4SQLITE")
    if env:
        return Path(env)
    return Path.home() / "sedra4sqlite"


def main() -> None:
    force = "--force" in sys.argv
    db = ROOT / "data" / "peshitta.db"
    if db.is_file() and not force:
        print(f"index present: {db}")
        return

    sedra_root = _sedra_root()
    corpus = sedra_root / "data" / "corpus.db"
    sedra = sedra_root / "data" / "sedra.db"
    english = sedra_root / "data" / "SEDRA" / "tblEnglish.txt"
    if not corpus.is_file():
        raise SystemExit(
            f"missing {corpus}\n"
            f"Set SEDRA4SQLITE to your sedra4sqlite checkout, or finish the morphology pipeline."
        )
    if not sedra.is_file():
        raise SystemExit(f"missing {sedra}")

    sys.path.insert(0, str(ROOT / "scripts"))
    import build_index

    sys.argv = [
        "build_index.py",
        "--corpus",
        str(corpus),
        "--sedra",
        str(sedra),
        "--english",
        str(english),
        "--out",
        str(db),
    ]
    build_index.main()


if __name__ == "__main__":
    main()
