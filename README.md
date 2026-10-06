# Peshitta Search

Dicta-style Syriac Peshitta search (web). Morphology from SEDRA 3 + SEDRA 4 fill-in; text from an Apache-2.0 Peshitta CSV prepared in [`sedra4sqlite`](../sedra4sqlite).

## Quick start

```bash
cd ~/peshitta_search
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./dev.sh
```

Opens the UI at http://127.0.0.1:5173 (API on :8000).

`./dev.sh` builds `data/peshitta.db` from `$SEDRA4SQLITE` (default `~/sedra4sqlite`) if needed.

Rebuild the index:

```bash
python3 scripts/ensure_index.py --force
```

## Search modes

| Mode | Behavior |
|------|----------|
| Root | SEDRA root family (SEDRA 3) / stem family (SEDRA 4) |
| Exact / Prefix / Contains | Consonantal form match |

Vocalized queries are stripped to Syriac consonants before search.

## Layout

- `scripts/build_index.py` — FTS5 + lemma index from `corpus.db` + `sedra.db`
- `src/backend.py` / `src/search.py` — FastAPI + SQLite search
- `src/App.jsx` — Dicta-style UI (English chrome, RTL Syriac results)

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Filters (Books, Meanings, Word Forms) start collapsed. Only verse text is RTL;
chrome stays LTR English.
