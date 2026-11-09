# Partial Stream Studio contract (binding for every packet)

vcr-core is the Verified-Check Record (VCR v0.1) spine. It has no HTTP cassette format today.
Partial Stream Studio adds an **opt-in** subpackage `vcr_core.partial` that records and replays
HTTP-style response bodies delivered as ordered byte chunks that may stop midway. Nothing in the
existing VCR v0.1 surface changes.

## Hard invariants
- Do not modify `vcr_core/__init__.py`, `vcr_core/vcr.py`, `vcr_core/score.py`,
  `vcr_core/schema/vcr-v0.1.schema.json`, `tests/test_record.py`, `tests/test_score.py`,
  `tests/test_distribution.py`. `import vcr_core` must not import `vcr_core.partial`.
- Runtime is pure stdlib (Python >= 3.12). `jsonschema` may be used only in tests.
- `make check` must pass (ruff check, ruff format --check, mypy --strict over vcr_core and tests,
  pytest, build). uv is pinned to 0.13.0; if `uv` on PATH is another version, run the tools via
  `.venv/bin/` (`.venv/bin/ruff`, `.venv/bin/mypy`, `.venv/bin/pytest`). Your worktree has no
  `.venv` yet and network is off: create it with the pinned binary from the warm cache,
  `/Users/d/.cache/uv/archive-v0/ROblRnaet5A6QO8-/bin/uv sync --locked --offline`.
- Typing: `unknown`-style narrowing (`object` + isinstance) over `Any`; string `Literal` unions,
  no `enum`. Errors are raised, never swallowed.
- All fixtures are original synthetic content. No real hosts, keys, names or emails
  (use `https://example.test/...`).

## Package layout
```
vcr_core/partial/
  __init__.py        public API re-exports (below)
  termination.py     TerminationState, Termination
  cassette.py        Chunk, PartialCassette, load/dump, validate_partial
  schema/partial-stream-v1.schema.json
  recorder.py        record(), record_iter(), arecord_iter()
  replay.py          replay(), areplay(), replay_bytes(), StreamClosedEarly, StreamTruncated
  fixtures/{split-codepoints,partial-events,early-close}/*.pcas.json   (packet 02)
  inspect.py         HTML inspector + CLI (packet 03)
  __main__.py        `python -m vcr_core.partial {count,validate,inspect}` (packets 02/03 extend)
```

## Termination model (`termination.py`)
```python
TerminationState = Literal["clean_close", "early_close", "truncated_mid_event"]
@dataclass(frozen=True)
class Termination:
    state: TerminationState
    after_chunk: int          # index of the last delivered chunk (-1 if none delivered)
    error: str | None = None  # for early_close: error class name raised at the drop, e.g. "ConnectionResetError"
    detail: str | None = None # free text, e.g. "SSE event 3 cut after 'data: {\"tok'"
    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, d: object) -> "Termination": ...   # raises ValueError on anything invalid
```
- `clean_close`: transport closed normally after the last chunk; body is complete.
- `early_close`: transport dropped (reset/abort) after some useful output; replay raises.
- `truncated_mid_event`: transport ended while a framed unit (SSE event / JSON object / UTF-8
  sequence) was incomplete; replay delivers the partial bytes and then raises.
- `error` is required (non-empty) for `early_close`, forbidden for `clean_close`, optional for
  `truncated_mid_event`. `after_chunk` must equal `len(chunks) - 1`.

## Cassette format (`cassette.py`, on disk `*.pcas.json`)
```json
{
  "format": "vcr-partial-stream/v1",
  "id": "split-codepoints/01-euro-sign-2-1",
  "class": "split_codepoint" | "partial_event" | "early_close",
  "description": "...",
  "request": {"method": "GET", "url": "https://example.test/stream"},
  "response": {"status": 200, "headers": [["content-type", "text/event-stream"]]},
  "chunks": [{"index": 0, "b64": "..."}, ...],
  "termination": {"state": "...", "after_chunk": N, "error": "...", "detail": "..."},
  "body_sha256": "<hex sha256 of concatenated chunk bytes>",
  "expect": { ... optional, fixture-specific assertions, see packet 02 ... }
}
```
- Chunk bytes are standard base64 (byte-faithful; chunks may split UTF-8 sequences). Empty
  chunks are allowed (b64 ""). Indices are 0..n-1 in order.
- Headers are an ordered list of [name, value] pairs (order and duplicates preserved).
- `dump()` writes canonical JSON: `json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False)`
  plus trailing newline, key order exactly as above. `load(dump(c)) == c` and
  `dump(load(text)) == text` for canonical text.
- `validate_partial(doc: object) -> None` is a stdlib validator that raises `ValueError` with a
  clear message (unknown/missing keys, wrong format tag, bad b64, index gaps, sha mismatch,
  termination rules above). The JSON Schema file mirrors it for external tools; a test checks a
  valid doc passes `jsonschema` against it too.
```python
@dataclass(frozen=True)
class Chunk: index: int; data: bytes
@dataclass(frozen=True)
class PartialCassette:
    id: str; cls: Literal["split_codepoint","partial_event","early_close"]; description: str
    request: dict[str, str]; status: int; headers: tuple[tuple[str, str], ...]
    chunks: tuple[Chunk, ...]; termination: Termination; expect: dict[str, object] | None = None
    def body(self) -> bytes: ...           # concatenated chunk bytes
    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, d: object) -> "PartialCassette": ...   # validates
def load(path_or_text: Path | str) -> PartialCassette   # Path -> read file; str -> JSON text
def dump(c: PartialCassette) -> str
```

## Recorder (`recorder.py`)
- `record(chunks: Sequence[bytes], termination: Termination, *, id, cls, description, request,
  status=200, headers=(), expect=None) -> PartialCassette` (deterministic builder).
- `record_iter(source: Iterable[bytes], *, framing: Literal["sse","ndjson","raw"]="raw", ...meta)`
  consumes the source, keeping each yielded bytes object as one chunk (boundaries preserved).
  If the source finishes: termination is `clean_close` unless the delivered body ends inside an
  incomplete framed unit (for `sse`: body doesn't end with a blank line `\n\n`; for `ndjson`:
  doesn't end with `\n`; for any framing: body ends with an incomplete UTF-8 sequence), in which
  case `truncated_mid_event` with a `detail`. If the source raises `OSError`
  (ConnectionError family etc.), termination is `early_close` with `error=type(exc).__name__`.
  Other exceptions propagate.
- `arecord_iter(source: AsyncIterable[bytes], ...)` same semantics.

## Replay (`replay.py`)
- `class StreamClosedEarly(ConnectionError)` with attrs `cassette_id`, `delivered: int` (bytes),
  `error: str`.
- `class StreamTruncated(EOFError)` with attrs `cassette_id`, `delivered: int`, `detail`.
- `replay(c) -> Iterator[bytes]`: yields every chunk's bytes in recorded order (empty chunks
  included, identical objects' content), then: `clean_close` -> stop;
  `early_close` -> raise `StreamClosedEarly`; `truncated_mid_event` -> raise `StreamTruncated`.
- `areplay(c) -> AsyncIterator[bytes]` same.
- `replay_bytes(c) -> tuple[bytes, Termination]`: drains replay, catching only its own two
  exceptions, returns delivered bytes + termination.
- Never decodes, re-chunks, or normalizes bytes.

## Public API (`vcr_core/partial/__init__.py`)
`TerminationState, Termination, Chunk, PartialCassette, load, dump, validate_partial, record,
record_iter, arecord_iter, replay, areplay, replay_bytes, StreamClosedEarly, StreamTruncated,
FORMAT_TAG ("vcr-partial-stream/v1"), FIXTURES_DIR (Path to bundled fixtures), iter_fixtures()`.

## Amendments from the stress test (binding, supersede anything above)
1. **Recorder truncation inference** (no byte normalization, ever):
   - `sse`: complete iff body is empty or ends with a blank-line terminator: `\n\n`, `\r\n\r\n`,
     or `\r\r`. Otherwise `truncated_mid_event`.
   - `ndjson`: complete iff body is empty, or ends with `\n` and the last non-empty line
     (stripped of `\r`) parses as JSON. `{"x":\n` is truncated.
   - Incomplete-UTF-8-at-end check applies to `sse` and `ndjson` only. `raw` is always
     `clean_close` on normal end (binary bodies are legitimate).
   - `record_iter` accepts `termination_override: TerminationState | None = None` for
     fixtures that need an explicit state; with an override, `detail` may be passed in too.
2. **Canonical form and validation**:
   - `b64` must be canonical: `base64.b64encode(base64.b64decode(s, validate=True)) == s`
     (rejects `YR==` aliases). Empty chunk is `""`.
   - Optional fields (`termination.error`, `termination.detail`, `expect`) are **omitted**
     when absent, never `null`.
   - Integers (`index`, `after_chunk`, `status`) reject `bool`.
   - `body_sha256` is 64 lowercase hex characters, no `sha256:` prefix.
   - `request`/`expect` nested dict key order is preserved as given; `dump` never sorts.
   - Validation runs in `PartialCassette.from_dict`, `load`, `record*`, and `dump`.
   - The JSON Schema mirrors structure and enums only; sha256 match and
     `after_chunk == len(chunks) - 1` are procedural checks in `validate_partial`.
3. **Order**: packet 01 lands first; packets 02 and 03 branch from it. Packet 03 keeps the
   existing `count`/`validate` subcommands when adding `inspect`/`serve`.
4. **Packaging**: the sdist must include `scripts/` (add `"scripts/"` to the sdist `include`
   in pyproject; this is the one allowed pyproject edit). Wheel **and** sdist must contain the
   partial schema and all 30 fixtures (asserted in `tests/test_partial_guard.py`). `.gitkeep`
   files are never counted.
5. **Inspector robustness**: decode with an incremental UTF-8 decoder using
   `errors="replace"` for display only; render invalid bytes as hex badges; at the end, finalize
   the decoder and show any buffered incomplete tail as hex. Rendering never raises on
   arbitrary bytes. Synthetic edge-case tests always run, even when bundled fixtures exist.
6. **Fixtures**: the "cut after 3 full events" fixture includes an incomplete 4th event.
   Combining/ZWJ fixtures must also split an actual codepoint's bytes across chunks.
