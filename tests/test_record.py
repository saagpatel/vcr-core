"""VCR record construction, schema validation, and vocabulary checks."""

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import jsonschema
import pytest

import vcr_core
from vcr_core import (
    CHECK_CATEGORIES,
    ENFORCED_CLASSES,
    POLARITIES,
    RESULT_VALUES,
    SUBJECT_KINDS,
    Verdict,
    base_schema,
    build_record,
    sha256_file,
    sha256_hex,
    validate_base,
)


def _record(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "subject_kind": "harness_config",
        "subject_name": "control.py@1",
        "subject_digest": "sha256:" + "a" * 64,
        "subject_media_type": "text/x-python",
        "check_id": "probe/history-destruction",
        "check_category": "guard",
        "check_version": "1.0.0",
        "config_ref_digest": "sha256:" + "b" * 64,
        "polarity": "must_block",
        "verdict": Verdict(result="pass", enforced="enforced"),
        "evidence_grade": "A",
        "evidence_digest": "sha256:" + "c" * 64,
        "ran_at": "2026-08-16T00:00:00Z",
        "env_digest": "sha256:" + "d" * 64,
        "duration_ms": 41,
        "runner": "probe-runner@0.1.0",
    }
    fields.update(overrides)
    return build_record(**fields)


def _enum(schema: dict[str, Any], *path: str) -> tuple[str, ...]:
    value: Any = schema
    for key in path:
        value = value[key]
    return tuple(value["enum"])


def test_base_record_validates() -> None:
    validate_base(_record())


@pytest.mark.parametrize(
    ("enum_path", "values"),
    [
        (
            ("properties", "predicate", "properties", "verdict", "properties", "result"),
            RESULT_VALUES,
        ),
        (
            ("properties", "predicate", "properties", "verdict", "properties", "enforced"),
            ENFORCED_CLASSES,
        ),
        (
            ("properties", "predicate", "properties", "check", "properties", "polarity"),
            POLARITIES,
        ),
        (
            ("properties", "subject", "items", "properties", "kind"),
            SUBJECT_KINDS,
        ),
        (
            ("properties", "predicate", "properties", "check", "properties", "category"),
            CHECK_CATEGORIES,
        ),
    ],
)
def test_value_sets_match_schema_enums(enum_path: tuple[str, ...], values: tuple[str, ...]) -> None:
    assert values == _enum(base_schema(), *enum_path)


def test_fresh_schema_mutation_does_not_change_validation() -> None:
    returned = base_schema()
    returned["properties"]["subject"]["items"]["properties"]["kind"]["enum"].append(
        "registry_listing"
    )

    with pytest.raises(jsonschema.ValidationError):
        validate_base(_record(subject_kind="registry_listing"))


def test_unknown_subject_kind_rejected() -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_base(_record(subject_kind="registry_listing"))


def test_file_hash_streams_multiple_chunks(tmp_path: Path) -> None:
    payload = bytes(range(256)) * (1024 * 1024 // 256 + 17)
    file_path = tmp_path / "large.bin"
    file_path.write_bytes(payload)

    assert sha256_file(file_path) == sha256_hex(payload)


def test_file_hash_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        sha256_file(tmp_path / "missing.bin")


def test_package_version_matches_distribution_metadata() -> None:
    assert vcr_core.__version__ == version("vcr-core")


def test_import_does_not_require_jsonschema() -> None:
    script = (
        "import sys; sys.modules['jsonschema'] = None; import vcr_core; assert vcr_core.__version__"
    )
    subprocess.run([sys.executable, "-c", script], check=True)


def test_schema_file_is_json() -> None:
    schema_path = Path(__file__).parents[1] / "vcr_core" / "schema" / "vcr-v0.1.schema.json"
    assert json.loads(schema_path.read_text())["$id"].endswith("/v0.1")
