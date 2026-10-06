# Peshitta Search

**v0.1.0** — Dicta-style Syriac Peshitta search (web + desktop). Morphology from
SEDRA 3 + SEDRA 4 fill-in; text from an Apache-2.0 Peshitta edition prepared in
[`sedra4sqlite`](../sedra4sqlite) (or rebuild locally).

## Quick start (web)

```bash
cd ~/peshitta_search
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./dev.sh
```

UI http://127.0.0.1:5173 · API http://127.0.0.1:8000

`./dev.sh` uses `data/peshitta.db` (prebuilt in the repo). Rebuild from morphology:

```bash
export SEDRA4SQLITE=~/sedra4sqlite
python3 scripts/ensure_index.py --force
```

## Search modes

| Mode | Behavior |
|------|----------|
| Root | SEDRA root family (SEDRA 3) / stem family (SEDRA 4) |
| Exact / Prefix / Contains | Consonantal form match |

## Desktop (Tauri)

```bash
cd rust-app
npm install
cargo test -p search-engine
npm run tauri:dev    # or tauri:build
```

See [rust-app/README.md](rust-app/README.md).

## Release package (web zip)

```bash
./scripts/make_release.sh
# → release/peshitta-search-0.1.0.zip
```

GitHub Releases (private repo): push a `v*` tag (e.g. `v0.1.0`) matching
`package.json` / `rust-app` / `tauri.conf.json` versions.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```
