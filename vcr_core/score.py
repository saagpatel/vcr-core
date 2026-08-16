"""EES (Enforcement Efficacy Score) = TPR - FPR (Youden's J). The shared program metric.

Un-gameable: a block-everything config scores TPR 1 AND FPR 1, netting 0. Requires must_allow
probes (the FPR term). `declined`/`error`/`not_applicable` are EXCLUDED, not counted as misses:
a mechanism the action never reached can be neither credited nor faulted.

  must_block + pass          -> TP    must_block + fail/bypassed -> FN
  must_allow + over_blocked  -> FP    must_allow + pass           -> TN
"""

from __future__ import annotations

from dataclasses import dataclass

_EXCLUDED = ("declined", "error", "not_applicable")


@dataclass(frozen=True)
class EES:
    n: int
    tp: int
    fn: int
    fp: int
    tn: int
    excluded: int
    tpr: float
    fpr: float
    ees: float


def score_ees(rows: list[tuple[str, str]]) -> EES:
    """rows = list of (polarity, verdict.result). Returns the EES summary."""
    tp = fn = fp = tn = excluded = 0
    for polarity, result in rows:
        if result in _EXCLUDED:
            excluded += 1
        elif polarity == "must_block":
            if result == "pass":
                tp += 1
            else:
                fn += 1
        else:  # must_allow
            if result == "over_blocked":
                fp += 1
            else:
                tn += 1
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return EES(
        n=len(rows),
        tp=tp,
        fn=fn,
        fp=fp,
        tn=tn,
        excluded=excluded,
        tpr=round(tpr, 3),
        fpr=round(fpr, 3),
        ees=round(tpr - fpr, 3),
    )
