# Peshitta Search — desktop (Tauri / Rust)

Windows/Linux desktop shell for the same UI as the web app. Search runs in
**Rust** against the SQLite index — no Python runtime in the packaged app.

## Layout

```
rust-app/
  src/                    React UI (same design as the web app)
  search-engine/          Pure Rust port of search.py + API assembly
  src-tauri/
    src/lib.rs            Tauri commands: search, books, health
    resources/            Bundled peshitta.db
```

## Prerequisites

- [Rust](https://rustup.rs/) (stable)
- Node.js 20+
- Windows: WebView2 + [Tauri Windows prerequisites](https://tauri.app/start/prerequisites/)
- Linux: webkit2gtk (Tauri Linux prerequisites). On WSL you can still verify:

```bash
cargo test -p search-engine
```

## Setup

```bash
cd rust-app
npm install
# After rebuilding the parent index, refresh the bundled copy:
#   cp ../data/peshitta.db src-tauri/resources/peshitta.db
```

## Develop / build

```bash
npm run tauri:dev
npm run tauri:build
```

Override index: `SEARCH_DB=/path/to/peshitta.db npm run tauri:dev`

Index *building* stays in the parent Python scripts; this app only reads the finished DB.
