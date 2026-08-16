# vcr-core

The shared spine for the **Verified-Check Record (VCR v0)** program: one home for the schema,
the verdict vocabulary, the record builder, and the **EES** metric. Imported by
[The Enforcement Gap (N2)](../enforcement-gap) and [HarnessBench](../harnessbench) so the
program cannot drift on how a check is recorded or scored.

- `vcr_core/schema/vcr-v0.schema.json` — the frozen VCR v0 JSON Schema (canonical copy).
- `vcr_core.build_record(...)` / `validate_base(record)` — assemble + base-validate a record.
- `vcr_core.Verdict`, `ENFORCED_CLASSES`, `RESULT_VALUES`, `POLARITIES` — the value sets.
- `vcr_core.score_ees(rows)` — EES = TPR − FPR (Youden's J); un-gameable, block-everything = 0.

Consumers add their own **profile** constraints on top of `validate_base` (e.g. N2 requires
`subject.kind == "harness_config"` and transcript-digest evidence); they never redefine the
field structure or the value enums.

## Pending home-base sign-off

These value additions are proposed and live in the schema but are **not frozen** until the
program's schema owner signs off (they propagate to N1/N4 on freeze): `over_blocked` and
`declined` on `verdict.result`, and `polarity` on the check.

```bash
uv sync && uv run pytest
```
