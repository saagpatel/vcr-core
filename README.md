# vcr-core

The shared spine for the **Verified-Check Record (VCR v0.1)** program: one home for the schema,
the verdict vocabulary, the record builder, and the **EES** metric. Imported by The Enforcement
Gap (N2) and [HarnessBench](https://github.com/saagpatel/harnessbench) so the
program cannot drift on how a check is recorded or scored.

- `vcr_core/schema/vcr-v0.1.schema.json` — the frozen VCR v0.1 JSON Schema (canonical copy).
- `vcr_core.build_record(...)` assembles a record. `validate_base(record)` checks it with the `validate` extra.
- `vcr_core.Verdict` holds the outcome. `ENFORCED_CLASSES`, `RESULT_VALUES`, `POLARITIES`,
  `SUBJECT_KINDS`, and `CHECK_CATEGORIES` are the value sets.
- `vcr_core.score_ees(rows)` — EES = TPR − FPR (Youden's J). Blocking everything scores 0
  when both polarities have evaluable rows.

Consumers add their own **profile** constraints on top of `validate_base` (e.g. N2 requires
`subject.kind == "harness_config"` and transcript-digest evidence); they never redefine the
field structure or the value enums.

## Schema history

### v0.1 (frozen 2026-08-16)

The v0.1 freeze approved `over_blocked` and `declined` on `verdict.result` and the optional
`polarity` field (`must_block`|`must_allow`) on the check. It also changed the required
`predicateType` from the v0 URI to the v0.1 URI, so unchanged v0 records fail base validation.
Sibling projects (N1, N4) may adopt the frozen result.

**Delta signed off 2026-08-24** (additive within v0.1, same predicateType): `subject.kind`
gains `skill_bundle` and `mcp_server` for the agent-tooling attestation profile (N3). Earlier
v0.1 validators reject the new kinds. Previously valid v0.1 records still validate.

## Build and test

Use `make` and **uv 0.13.9 or any later 0.13.x**. The checkout selects Python 3.15.0
via `.python-version`. uv can download it during setup. The repo pins uv
(`required-version = ">=0.13.9,<0.14"` in `pyproject.toml`).
CI runs exactly 0.13.9. Check yours with `uv --version`; see the
[uv install docs](https://docs.astral.sh/uv/) if you need to install or upgrade.

```bash
make setup                  # uv sync --locked
make check                  # lockfile check, ruff lint and format check, mypy, pytest, wheel build check
uv run --locked pytest -q   # tests only
```

## Status

### Stack

Python 3.12+ library with a zero-dependency runtime core. `jsonschema` is available through the
optional `validate` extra. Development uses pinned uv, Hatchling, Ruff, mypy, and pytest.

### Known risks

- Owner decision: whether to support unchanged v0 records by dispatching on predicate type.
- Owner decision: how to report EES when one polarity has no evaluable rows. Its rate defaults
  to `0.0`, and the other polarity still contributes to EES.
- Owner decision: whether to tighten the frozen schema's digest pattern, `additionalProperties`, or
  date-time format rules.

### Next steps

Resolve the listed owner decisions before changing schema compatibility or score reporting.

## Partial Stream Studio (opt-in)

`vcr_core.partial` records and replays HTTP-style response bodies that arrive in fragments
and may stop midway, byte for byte. It is a separate, opt-in format (`vcr-partial-stream/v1`,
`*.pcas.json`) beside the VCR v0.1 record. `import vcr_core` never loads it, and nothing in
the frozen v0.1 schema or API changed.

- A cassette holds ordered byte chunks (canonical base64) plus one termination state:
  `clean_close`, `early_close` (transport dropped, possibly before the first chunk), or
  `truncated_mid_event` (an SSE event, JSON value or UTF-8 sequence cut off).
- `record` / `record_iter` / `arecord_iter` capture chunk boundaries exactly. Truncation
  detection is framing-aware (`sse`, `ndjson`, `raw`), and an `OSError` from the source is
  recorded as `early_close`.
- `replay` / `areplay` yield the recorded bytes in recorded order, then end the way the stream
  ended: normally, `StreamClosedEarly` (a `ConnectionError`), or `StreamTruncated` (an
  `EOFError`). Nothing is decoded or re-chunked.
- 30 original synthetic fixtures ship with the package, 10 each for split codepoints, partial
  events and early close (`vcr_core.partial.iter_fixtures()`). They are regenerated
  deterministically by `scripts/build_partial_fixtures.py` (`--check` verifies them).

```bash
uv run python -m vcr_core.partial count                 # 10 / 10 / 10, total 30
uv run python -m vcr_core.partial validate vcr_core/partial/fixtures
uv run python -m vcr_core.partial inspect --bundled     # writes partial-inspect/index.html (--out sets the directory)
uv run python -m vcr_core.partial serve --bundled       # serves on 127.0.0.1:8765 (--port sets the port)
```
