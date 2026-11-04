# Purpose

`vcr-core` is the shared Python library for building, validating, and scoring Verified-Check
Records. Keep changes small and preserve the frozen v0.1 schema contract.

# Layout

- `vcr_core/` contains the zero-dependency record, digest, and EES implementation.
- `vcr_core/schema/vcr-v0.1.schema.json` is the canonical base schema.
- `tests/` covers scoring, record validation, and built distributions.
- `pyproject.toml` and `uv.lock` define package metadata and the locked toolchain.

# Setup

Install Python 3.15 and uv 0.13.0, then run `make setup`.

# Checks

Run `make check` for dependency-lock, lint, format, type, test, and distribution checks.

# Boundaries

- The v0.1 schema is frozen; do not change its contract without an owner decision.
- The core runtime has no third-party dependencies; `jsonschema` remains optional.
- The package version (`0.2.0`) and schema version (`v0.1`) are separate version domains.

# Delivery

Changes should pass `make check` and `git diff --check` before delivery. Releases use a `v*` tag
with the PyPI OIDC trusted publisher configured for this workflow and the `pypi` environment.
