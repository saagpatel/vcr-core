"""vcr-core: record build + base validation, and the shared EES metric."""

import jsonschema
import pytest

from vcr_core import Verdict, build_record, score_ees, validate_base


def _record(**over):
    base = dict(
        subject_kind="harness_config",
        subject_name="claude-code/core-guard.py@1",
        subject_digest="sha256:" + "a" * 64,
        subject_media_type="text/x-python",
        check_id="probe/history-destruction/force-push-canonical",
        check_category="guard",
        check_version="1.0.0",
        config_ref_digest="sha256:" + "b" * 64,
        polarity="must_block",
        verdict=Verdict(result="pass", enforced="enforced"),
        evidence_grade="A",
        evidence_digest="sha256:" + "c" * 64,
        ran_at="2026-08-16T00:00:00Z",
        env_digest="sha256:" + "d" * 64,
        duration_ms=41,
        runner="n2-probe-runner@0.1.0",
    )
    base.update(over)
    return build_record(**base)


def test_base_record_validates():
    validate_base(_record())


def test_schema_delta_values_and_polarity_validate():
    validate_base(
        _record(verdict=Verdict(result="over_blocked", enforced="enforced"), polarity="must_allow")
    )
    validate_base(_record(verdict=Verdict(result="declined", enforced="advisory")))


def test_unknown_result_rejected():
    rec = _record()
    rec["predicate"]["verdict"]["result"] = "sorta"
    with pytest.raises(jsonschema.ValidationError):
        validate_base(rec)


def test_ees_block_everything_is_zero():
    e = score_ees([("must_block", "pass"), ("must_allow", "over_blocked")])
    assert e.tpr == 1.0 and e.fpr == 1.0 and e.ees == 0.0


def test_ees_excludes_declined():
    e = score_ees([("must_block", "pass"), ("must_block", "declined")])
    assert e.excluded == 1 and e.tpr == 1.0
