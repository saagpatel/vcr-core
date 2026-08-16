# vcr-core

The shared spine for the **Verified-Check Record (VCR v0.1)** program: one home for the schema,
the verdict vocabulary, the record builder, and the **EES** metric. Imported by The Enforcement
Gap (N2) and [HarnessBench](https://github.com/saagpatel/harnessbench) so the
program cannot drift on how a check is recorded or scored.

- `vcr_core/schema/vcr-v0.1.schema.json` — the frozen VCR v0.1 JSON Schema (canonical copy).
- `vcr_core.build_record(...)` / `validate_base(record)` — assemble + base-validate a record.
- `vcr_core.Verdict`, `ENFORCED_CLASSES`, `RESULT_VALUES`, `POLARITIES` — the value sets.
- `vcr_core.score_ees(rows)` — EES = TPR − FPR (Youden's J); un-gameable, block-everything = 0.

Consumers add their own **profile** constraints on top of `validate_base` (e.g. N2 requires
`subject.kind == "harness_config"` and transcript-digest evidence); they never redefine the
field structure or the value enums.

## v0.1 (frozen 2026-08-16)

v0.1 is an additive, backward-compatible extension of v0, signed off by the program's schema
owner: it adds `over_blocked` and `declined` on `verdict.result`, and the optional `polarity`
field (`must_block`|`must_allow`) on the check. Nothing was removed, so every v0 record is still
valid. Sibling projects (N1, N4) may adopt the frozen result.

```bash
uv sync && uv run pytest
```
