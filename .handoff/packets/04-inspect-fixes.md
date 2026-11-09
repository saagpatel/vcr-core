# Packet 04: fix two inspector correctness defects (from the Codex Sol review of PR #9)

Read `.handoff/partial-stream-contract.md` (binding). Touch only `vcr_core/partial/inspect.py`
and `tests/test_partial_inspect.py` (plus `__main__.py` only if a signature must change). Do not
change any fixture, core module, or frozen file. Do not push.

## Defect 1: malformed-byte text view (inspect.py `_chunk_views`, `_display_tokens`, `_piece_tokens`)
Today the fallback tokenizer leans on `codecs` replace-decoder heuristics. It renders
`b"\xc3\xe2\x82\xac"` as four hex bytes instead of hex `c3` then text `€`, and for a chunk
`b"\xc3\xe2\x82"` it shows `c3` twice.

Replace that machinery with a deterministic byte scanner (stdlib only):
- `_scan(data: bytes) -> tuple[list[_Text | _Hex], bytes]`: walk left to right. At position i,
  read the lead byte's expected length n (1 for <0x80, 2 for C2–DF, 3 for E0–EF, 4 for F0–F4,
  otherwise invalid). If `data[i:i+n]` has length n and `.decode("utf-8")` succeeds (this
  rejects overlongs, surrogates and >U+10FFFF), emit it as text (merge adjacent text) and
  advance by n. If fewer than n bytes remain **and** every remaining byte is a valid
  continuation for that lead (use the strict rule: check that some full completion could be
  valid, e.g. by trying `decode` on remaining+continuation padding of b"\x80"…, or explicit
  per-lead second-byte ranges E0:A0–BF, ED:80–9F, F0:90–BF, F4:80–8F, otherwise 80–BF),
  stop and return those bytes as the incomplete `tail`. Otherwise emit `_Hex(data[i:i+1])` and
  advance by 1.
- `_chunk_views`: keep `carry` bytes. For each chunk, `tokens, carry_out = _scan(carry + data)`.
  The chunk row shows `tokens`; `carries = len(carry_out)` when the chunk is non-empty and
  `carry_out` is non-empty; `completes_split = bool(carry) and the first token is _Text whose
  UTF-8 encoding starts with carry`. Empty chunks pass the carry through unchanged and show
  "(empty chunk)". After the last chunk, any remaining carry is the undecodable tail rendered
  as hex. Every byte of the stream appears in exactly one row's text view or the tail: never
  dropped, never duplicated.
- Keep all existing HTML structure, badges, attributes and escaping.

Regression tests (new, in tests/test_partial_inspect.py), checking `_scan` directly and through
rendered pages:
- `b"\xc3\xe2\x82\xac"` -> [Hex c3, Text "€"], tail b"".
- `b"\xc3\xe2\x82"` (single chunk, clean_close) -> Hex c3 exactly once, then the tail e2 82
  rendered once as hex in the termination/tail area, never as row text.
- Chunks [b"a\xe2", b"\x82", b"\xacb"] -> rows "a" (carries 1), "" (carries 2), "€b"
  (completes split).
- `b"\xed\xa0\x80"` (surrogate) -> three hex bytes, no text. `b"\xf4\x90\x80\x80"` -> four hex.
  `b"\xc0\xaf"` (overlong) -> two hex.
- A property test over all 30 bundled fixtures plus 200 seeded random byte streams
  (`random.Random(1234)`, 0–40 bytes, random chunking incl. empty chunks): concatenating, in
  order, every row's bytes (text tokens re-encoded + hex tokens) and the final tail equals the
  body exactly. Expose a small internal helper to make that possible if needed.

## Defect 2: page path collisions (`_href_for`, `_within`, `write_site`)
IDs `foo` and `foo.html/bar` collide as file vs directory; ID `index.html/child` creates an
`index.html` directory. Switch to **flat, unique filenames** in the output root: `pages/`
subdirectory is fine as long as nothing can collide, e.g.
`pages/NNN-<slug>.html` where NNN is the zero-padded position in the sorted input and slug is
the ID with every run of characters outside `[A-Za-z0-9._-]` (including `/`) replaced by `-`,
stripped of leading/trailing `.`/`-`, truncated to 80 chars, `cassette` if empty.
`index.html` stays at the root and can never be shadowed. Keep the out-dir containment check.
Index links and any back-links must keep working.

Tests: IDs `foo` + `foo.html/bar` in both input orders; a single `index.html/child`; IDs that
differ only by characters that slugify the same (`a/b` and `a-b`) get distinct files; site
builds, every page exists, the index links to each exactly once.

## Acceptance
```
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest -q
.venv/bin/python -m vcr_core.partial inspect --bundled --out "$TMPDIR/pss-site"
```
