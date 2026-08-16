# Publish path for vcr-core (recommendation)

vcr-core is the shared spine three projects depend on (N2, HarnessBench, and later N1/N4). For
HarnessBench's public branch to reference it cleanly, vcr-core needs a real distribution path,
not a bare `../vcr-core`. This is the recommendation; the actual public push is operator-gated
(outward-facing, so it waits for explicit go).

## Recommended: publish vcr-core as its own public package

1. **Own public repo** (for example `github.com/saagpatel/vcr-core`), MIT (matches HarnessBench).
2. **PyPI package `vcr-core`**, pure-stdlib core with `jsonschema` behind the `validate` extra.
3. Consumers depend on it normally:
   - HarnessBench: the optional `vcr` extra (already declared). Its core stays zero-dependency;
     `pip install harnessbench[vcr]` enables VCR emission.
   - N2 and N1/N4: a normal dependency (they already use `jsonschema`, so `vcr-core[validate]`).

Why this over the alternatives:

- **Versus vendoring a copy into each repo:** vendoring duplicates the spine and reintroduces
  the drift the shared library exists to prevent. If HarnessBench's zero-clone-step self-containment
  is required, vendor with a sync-check test that asserts the vendored copy is byte-identical to
  the published one, but prefer the dependency.
- **Versus a git submodule:** poor ergonomics and a common source of broken clones.

## Ordering (so nothing references a thing that is not yet public)

1. Operator approves the schema-delta (freezes `over_blocked`, `declined`, `polarity`), OR we
   publish vcr-core `0.1.0` marked pre-freeze with those values flagged experimental.
2. Push vcr-core to its public repo; publish `0.1.0` to PyPI.
3. Repoint HarnessBench's `feat/vcr-core-integration` optional extra from a path source to the
   published `vcr-core`, then push that branch.
4. N2 stays private; it can keep the local path source or move to the published package.

## Containment reminder

Nothing in vcr-core references `core-guard` or any harness guard body. It carries only the
schema, the verdict vocabulary, the record builder, and the metric. This is what makes it safe
to publish ahead of, and independently from, the private N2 measurement data.
