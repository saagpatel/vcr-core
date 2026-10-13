.PHONY: setup check

setup:
	@command -v uv >/dev/null 2>&1 || { echo "Install uv 0.13.0 (https://docs.astral.sh/uv/)" >&2; exit 1; }
	uv sync --locked

check:
	@command -v uv >/dev/null 2>&1 || { echo "Install uv 0.13.0 (https://docs.astral.sh/uv/)" >&2; exit 1; }
	uv run --locked uv sync --locked --check
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked mypy
	uv run --locked pytest -q
	@tmp=$$(mktemp -d .check-build.XXXXXX); trap 'rm -rf "$$tmp"' EXIT; \
	  uv run --locked uv build --out-dir "$$tmp" && \
	  uv run --locked python -c 'import pathlib,sys,zipfile; p=pathlib.Path(sys.argv[1]); w=next(p.glob("*.whl")); z=zipfile.ZipFile(w); names=z.namelist(); assert "vcr_core/py.typed" in names; assert "vcr_core/schema/vcr-v0.1.schema.json" in names' "$$tmp"
