# Packet 03: inspection UI for partial-stream cassettes

Read `.handoff/partial-stream-contract.md` first (binding). The core API in `vcr_core/partial/`
exists on your base branch; use `load`, `PartialCassette`, `iter_fixtures`, `FIXTURES_DIR`.
Do not change core behavior. Do not push. Stdlib only (no JS frameworks, no CDN, no network).

## Goal
`vcr_core/partial/inspect.py` renders any partial cassette as a self-contained static HTML page
showing the stream chunk by chunk with its termination state, plus an index page listing many
cassettes. Wire CLI in `vcr_core/partial/__main__.py`:
- `python -m vcr_core.partial inspect <file-or-dir>... [--out DIR]` writes `index.html` and one
  page per cassette into DIR (default `./partial-inspect`), prints the index path.
- `python -m vcr_core.partial inspect --bundled [--out DIR]` uses all bundled fixtures.
- `python -m vcr_core.partial serve [--port 8765] [paths... | --bundled]` renders to a temp dir
  and serves it with `http.server` bound to 127.0.0.1 only.

## Page content (per cassette)
- Header: id, class, description, request method+url, status, headers table (in order).
- Termination banner, visually distinct per state, with stable text label exactly
  `clean_close`, `early_close`, or `truncated_mid_event`, plus `after_chunk`, `error`, `detail`.
- One row per chunk, in order: index, byte length, byte offset range, hex dump (grouped bytes),
  and a text view decoded **incrementally across chunks** with
  `codecs.getincrementaldecoder("utf-8")` so a codepoint split across chunks is shown in the
  chunk where it completes, and bytes carried over are marked (e.g. a "↪ carries N bytes" badge
  on the earlier chunk and "completes split codepoint" on the later one). Control chars and
  `\n` rendered visibly (`␊`). Empty chunks shown as "(empty chunk)".
- After the last chunk: a terminal row rendering the termination (e.g. "✂ connection reset:
  ConnectionResetError" / "⋯ truncated mid-event: <detail>" / "■ clean close"), and for a
  truncated stream any undecodable trailing bytes shown in hex.
- Summary: total bytes, chunk count, body sha256.
- All cassette-derived text HTML-escaped (`html.escape`). Each element the tests need carries
  stable attributes: chunk rows `data-chunk-index="N"`, termination `data-termination="<state>"`.
- Light and dark via `prefers-color-scheme`; readable at narrow widths; inline CSS only.

## Public functions
`render_cassette(c: PartialCassette) -> str`, `render_index(items: Sequence[tuple[str,
PartialCassette]]) -> str` (href, cassette), `write_site(cassettes, out_dir: Path) -> Path`.

## Tests (new file `tests/test_partial_inspect.py`)
- For every bundled fixture (use `iter_fixtures()`; if the bundled set is empty at your base,
  also build in-test cassettes covering all 3 termination states, a split 4-byte emoji, an
  empty chunk, and `<script>` in description to prove escaping): the page has exactly
  `len(chunks)` `data-chunk-index` rows numbered 0..n-1 in order, exactly one
  `data-termination="<state>"` matching, contains each chunk's hex, contains no raw `<script>`
  from cassette data.
- Split-codepoint case: the completed character appears once, in the completing chunk row.
- CLI: `inspect --bundled --out tmp` and `inspect <file> --out tmp` exit 0 and write
  index.html + pages; index links to every page.
- `serve` is not started in tests except a smoke test that starts it on port 0 in a thread /
  subprocess, GETs index.html over 127.0.0.1, then shuts down within 5 s.

## Acceptance
```
.venv/bin/python -m vcr_core.partial inspect --bundled --out /tmp/pss-inspect   # (use your TMPDIR)
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest -q
```
