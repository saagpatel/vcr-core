"""EES classification and input validation."""

import pytest

from vcr_core import score_ees


@pytest.mark.parametrize(
    ("polarity", "result", "counts"),
    [
        ("must_block", "pass", (1, 0, 0, 0, 0)),
        ("must_block", "fail", (0, 1, 0, 0, 0)),
        ("must_block", "bypassed", (0, 1, 0, 0, 0)),
        ("must_block", "over_blocked", (0, 1, 0, 0, 0)),
        ("must_block", "declined", (0, 0, 0, 0, 1)),
        ("must_block", "not_applicable", (0, 0, 0, 0, 1)),
        ("must_block", "error", (0, 0, 0, 0, 1)),
        ("must_allow", "pass", (0, 0, 0, 1, 0)),
        ("must_allow", "fail", (0, 0, 0, 1, 0)),
        ("must_allow", "bypassed", (0, 0, 0, 1, 0)),
        ("must_allow", "over_blocked", (0, 0, 1, 0, 0)),
        ("must_allow", "declined", (0, 0, 0, 0, 1)),
        ("must_allow", "not_applicable", (0, 0, 0, 0, 1)),
        ("must_allow", "error", (0, 0, 0, 0, 1)),
    ],
)
def test_valid_pairings_keep_their_classification(
    polarity: str, result: str, counts: tuple[int, int, int, int, int]
) -> None:
    scored = score_ees([(polarity, result)])
    assert (scored.tp, scored.fn, scored.fp, scored.tn, scored.excluded) == counts
    assert scored.n == 1


@pytest.mark.parametrize(
    ("row", "offending"),
    [
        (("typo", "pass"), "typo"),
        (("must_block", "unknown"), "unknown"),
        (("typo", "declined"), "typo"),
    ],
)
def test_unknown_values_fail_before_exclusion(row: tuple[str, str], offending: str) -> None:
    with pytest.raises(ValueError, match=r"row 1") as error:
        score_ees([("must_block", "pass"), row])
    assert offending in str(error.value)


def test_zero_denominators_remain_zero_and_exclusions_count_in_n() -> None:
    scored = score_ees([("must_block", "declined")])
    assert scored.n == 1
    assert scored.excluded == 1
    assert scored.tpr == 0.0
    assert scored.fpr == 0.0
    assert scored.ees == 0.0
