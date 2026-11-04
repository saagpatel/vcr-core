"""VCR v0.1 spine: digests, the verdict vocabulary, the record builder, and base validation.

This is the single source of truth for the Verified-Check Record schema and its value sets.
Consumers (N2, HarnessBench) import from here; they add their own PROFILE constraints on top
of `validate_base`, but never redefine the field structure or the value enums.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast, get_args

# jsonschema is imported lazily inside validate_base so importing vcr-core for build_record /
# verdicts / EES stays pure-stdlib. This lets HarnessBench (deliberately zero-third-party-dep)
# import the spine without pulling jsonschema; only validation needs it.

PREDICATE_TYPE = "https://saagarpatel.dev/schema/vcr/v0.1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "vcr-v0.1.schema.json"

# The canonical value sets. v0.1 (frozen 2026-08-16) added over_blocked, declined (result) and
# polarity on the check; they propagate from here to every consumer.
ResultValue = Literal[
    "pass", "fail", "bypassed", "over_blocked", "declined", "not_applicable", "error"
]
EnforcedClass = Literal["enforced", "advisory", "observed", "absent"]
Polarity = Literal["must_block", "must_allow"]
SubjectKind = Literal["harness_config", "work_product", "artifact", "skill_bundle", "mcp_server"]
CheckCategory = Literal["guard", "policy", "quality", "provenance"]

ENFORCED_CLASSES = get_args(EnforcedClass)
RESULT_VALUES = get_args(ResultValue)
POLARITIES = get_args(Polarity)
SUBJECT_KINDS = get_args(SubjectKind)
CHECK_CATEGORIES = get_args(CheckCategory)


def sha256_hex(data: bytes) -> str:
    """A VCR digest string for raw bytes."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """A VCR digest string for a file's contents."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


@cache
def _cached_schema() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(_SCHEMA_PATH.read_text()))


def base_schema() -> dict[str, Any]:
    """Return a fresh copy of the frozen base schema."""
    return deepcopy(_cached_schema())


@dataclass(frozen=True)
class Verdict:
    """The measured outcome of one check run.

    `enforced` is the control's binding CLASS; `result` is what this run measured. Bypass and
    over_block are run-level events, so they live on `result`, never on `enforced`.
    """

    result: ResultValue
    enforced: EnforcedClass | None = None
    score: float | None = None


def build_record(
    *,
    subject_kind: SubjectKind,
    subject_name: str,
    subject_digest: str,
    subject_media_type: str,
    check_id: str,
    check_category: CheckCategory,
    check_version: str,
    verdict: Verdict,
    evidence_grade: str,
    evidence_digest: str,
    ran_at: str,
    runner: str,
    env_digest: str | None = None,
    duration_ms: int | None = None,
    config_ref_digest: str | None = None,
    polarity: Polarity | None = None,
    authority: str = "operator",
    trust: str = "trusted",
    instruction_boundary: str = "direct",
    evidence_kind: str = "transcript-digest",
) -> dict[str, Any]:
    """Assemble one VCR v0.1 record. Generic across profiles; call a profile's validate()."""
    verdict_obj: dict[str, Any] = {"result": verdict.result}
    if verdict.enforced is not None:
        verdict_obj["enforced"] = verdict.enforced
    if verdict.score is not None:
        verdict_obj["score"] = verdict.score

    check: dict[str, Any] = {"id": check_id, "category": check_category, "version": check_version}
    if config_ref_digest is not None:
        check["config_ref"] = {"sha256": config_ref_digest}
    if polarity is not None:
        check["polarity"] = polarity

    runtime: dict[str, Any] = {"ran_at": ran_at, "runner": runner}
    if env_digest is not None:
        runtime["env_digest"] = env_digest
    if duration_ms is not None:
        runtime["duration_ms"] = duration_ms

    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "kind": subject_kind,
                "name": subject_name,
                "mediaType": subject_media_type,
                "digest": {"sha256": subject_digest},
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "check": check,
            "verdict": verdict_obj,
            "evidence": {
                "kind": evidence_kind,
                "grade": evidence_grade,
                "digest": {"sha256": evidence_digest},
            },
            "runtime": runtime,
            "provenance": {
                "authority": authority,
                "trust": trust,
                "instruction_boundary": instruction_boundary,
            },
        },
    }


def validate_base(record: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError on any base-schema violation. Profiles add more.

    Requires the optional `jsonschema` extra (``pip install vcr-core[validate]``). Callers that
    only build/score records never need it.
    """
    try:
        import jsonschema
    except ImportError as e:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "validate_base needs the optional 'jsonschema' dependency (vcr-core[validate])"
        ) from e
    jsonschema.validate(record, _cached_schema())
