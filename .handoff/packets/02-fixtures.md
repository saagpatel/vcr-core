# Packet 02: thirty original partial-stream fixtures + class tests + guard

Read `.handoff/partial-stream-contract.md` first (binding). The core API in `vcr_core/partial/`
already exists on your base branch; use it, don't change its behavior (bug fixes allowed only
with a test, and say so in your report).

## Goal
Exactly 30 fixtures, 10 per class, generated deterministically by
`scripts/build_partial_fixtures.py` (stdlib only, uses `vcr_core.partial.record` /
`record_iter`, writes with `dump`). Running it twice yields byte-identical files; add
`--check` mode that exits nonzero if any on-disk fixture differs from what it would write.

Files: `vcr_core/partial/fixtures/<class-dir>/NN-slug.pcas.json`, NN = 01..10.
`id` = `<class-dir>/NN-slug`. All content synthetic (example.test URLs, made-up text).

### split-codepoints (class split_codepoint), 10 fixtures
Multibyte UTF-8 split across chunk boundaries, termination `clean_close`. Cover: 2-byte
(é, ß), 3-byte (€, CJK 中, ✓), 4-byte (emoji 🙂, 𝄞), splits 1+1, 1+2, 2+1, 1+1+1+1, a char
split across three chunks with an empty chunk between, combining sequences (e + U+0301),
ZWJ emoji sequence split mid-sequence, split inside an SSE `data:` line, split inside an
NDJSON string. `expect`: `{"decoded_text": <full str>, "split_points": [byte offsets that
fall inside a codepoint]}`.

### partial-events (class partial_event), 10 fixtures
SSE events or JSON objects cut mid-way, termination `truncated_mid_event` with `detail`.
Cover: SSE `data:` JSON cut mid-string, cut mid-key, cut after `data:` before payload, cut
between `\n` and the second `\n`, multi-line `data:` event cut on line 2, NDJSON object cut
mid-number, cut mid-escape (`\u00`), cut mid-multibyte inside a JSON string, chat-completion
style token stream cut after 3 full events, OpenAI-style `[DONE]` sentinel cut (`data: [DO`).
`expect`: `{"complete_events": <int>, "truncated_at_byte": <len(body)>, "tail_b64":
<base64 of the incomplete trailing bytes after the last complete unit>}`.

### early-close (class early_close), 10 fixtures
Connection drops after useful output, termination `early_close`, `error` one of
`ConnectionResetError`, `BrokenPipeError`, `ConnectionAbortedError`, `TimeoutError`
(at least three distinct). Cover: drop after N complete SSE events, after headers-only
(0 chunks, after_chunk -1), after a complete JSON array element in a chunked JSON array,
mid-chunk-free boundary (drop exactly on an event boundary), after a keepalive comment line
(`: ping`), after large chunk (64 KiB synthetic), after many tiny 1-byte chunks (≥50),
plain-text download cut, NDJSON log stream, and one that drops right after a split codepoint
completes. `expect`: `{"useful_prefix_b64": <bytes delivered>, "complete_events": <int|null>}`.

## Tests (new files)
- `tests/test_partial_split_codepoints.py`: for every split_codepoint fixture: replay bytes
  equal recorded; at least one chunk is not valid UTF-8 on its own (proves a real split);
  incremental decoding via `codecs.getincrementaldecoder("utf-8")` over the replayed chunks
  yields `expect.decoded_text` exactly with no U+FFFD; `split_points` are inside codepoints.
- `tests/test_partial_events.py`: for every partial_event fixture: replay yields the exact
  bytes then raises `StreamTruncated`; delivered byte count == `truncated_at_byte`; the body
  ends with `tail_b64`; number of complete SSE events / NDJSON lines == `complete_events`.
- `tests/test_partial_early_close.py`: replay yields `useful_prefix_b64` then raises
  `StreamClosedEarly` with `error` matching the fixture; `complete_events` checks.
- `tests/test_partial_replay_bytes.py`: parametrized over all 30 bundled fixtures: replay
  chunk list equals recorded chunk list (boundaries + order), sha256 matches, termination
  equals recorded; also via `areplay`.
- `tests/test_partial_guard.py`: exactly 30 fixtures, 10 per class, unique ids, every file
  canonical (`dump(load(text)) == text`), `scripts/build_partial_fixtures.py --check` passes
  (subprocess), `python -m vcr_core.partial count` prints
  `split_codepoint=10 partial_event=10 early_close=10 total=30`; no-migration: no file outside
  `vcr_core/partial/` contains the string `vcr-partial-stream/v1` except docs/.handoff/tests,
  and the frozen VCR files listed in the contract match hard-coded sha256 values computed
  from your base commit.
- Ensure the wheel built by `uv build` contains all 30 fixtures (extend nothing frozen; put
  that assertion in `tests/test_partial_guard.py`, building into tmp_path like
  tests/test_distribution.py does).

## Out of scope
Inspector UI, README.

## Acceptance
```
.venv/bin/python scripts/build_partial_fixtures.py --check
.venv/bin/python -m vcr_core.partial count
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest -q
```
(mypy config covers `vcr_core` and `tests`; also run `.venv/bin/mypy --strict scripts/`.)
