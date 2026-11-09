# Packet 01: partial-stream core (format, termination, recorder, replay)

Read `.handoff/partial-stream-contract.md` first; it is binding and gives exact signatures.

## Goal
Implement `vcr_core/partial/` core: `termination.py`, `cassette.py`, the JSON Schema
`schema/partial-stream-v1.schema.json`, `recorder.py`, `replay.py`, `__init__.py` (with
`FIXTURES_DIR = Path(__file__).parent / "fixtures"` and `iter_fixtures()` yielding loaded
cassettes sorted by path from `FIXTURES_DIR/**/*.pcas.json`, empty if none), plus a
minimal `__main__.py` supporting `validate <path...>` (validates files/dirs, nonzero exit on
any failure) and `count` (prints `split_codepoint=N partial_event=N early_close=N total=N`
from bundled fixtures).

## Scope
- Packaging: ensure the schema JSON and `fixtures/**` ship in the wheel (hatch includes package
  data under `vcr_core/` by default; verify). Create `vcr_core/partial/fixtures/.gitkeep`
  subdirs `split-codepoints/`, `partial-events/`, `early-close/` (each with `.gitkeep`).
- Tests (new files only), synthetic in-test streams, no fixtures needed:
  - `tests/test_partial_termination.py`: round-trips each of the 3 states through
    to_dict/from_dict and through a full cassette dump/load; rejects bad states,
    error rules, after_chunk mismatch.
  - `tests/test_partial_format.py`: valid cassette passes `validate_partial` and `jsonschema`
    against the schema file; each invalid case (wrong tag, missing key, extra key, bad b64,
    index gap, sha mismatch, bad class, header not a pair) raises ValueError; canonical
    dump/load idempotence; header order and duplicates preserved; empty chunks preserved.
  - `tests/test_partial_replay.py`: replayed bytes equal recorded chunk-by-chunk (same count,
    same boundaries) for clean/early/truncated cases incl. a multibyte UTF-8 char split 1+2 and
    a 4-byte emoji split 1+1+1+1; correct exception types/attrs; `areplay` parity
    (use `asyncio.run`); `replay_bytes`.
  - `tests/test_partial_recorder.py`: `record_iter` boundary preservation; sse/ndjson/raw
    truncation detection; incomplete-UTF-8 detection; source raising ConnectionResetError ->
    early_close with that error name; ValueError from the source propagates; `arecord_iter`
    parity.
  - `tests/test_partial_isolation.py`: `import vcr_core` in a fresh subprocess does not put
    `vcr_core.partial` in `sys.modules`; the frozen schema file sha256 equals
    the value computed from git HEAD of `vcr_core/schema/vcr-v0.1.schema.json` at the time you
    write the test (hard-code it).

## Out of scope
Fixture files (packet 02), inspector UI (packet 03), README (head does it). Do not touch any
file the contract lists as frozen.

## Acceptance
```
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest -q
```
All pass, including the 32 pre-existing tests unchanged. `python -m vcr_core.partial count`
prints zeros. Commit in small conventional commits.
