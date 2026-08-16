"""vcr-core: the shared spine for the Verified-Check Record (VCR v0.1) program.

One home for the schema, the verdict vocabulary, the record builder, and the EES metric,
imported by The Enforcement Gap (N2) and HarnessBench so the three-project program cannot
drift on how a check is recorded or scored.
"""

from vcr_core.score import EES, score_ees
from vcr_core.vcr import (
    ENFORCED_CLASSES,
    POLARITIES,
    PREDICATE_TYPE,
    RESULT_VALUES,
    STATEMENT_TYPE,
    Verdict,
    base_schema,
    build_record,
    sha256_file,
    sha256_hex,
    validate_base,
)

__version__ = "0.1.0"
__all__ = [
    "EES",
    "score_ees",
    "ENFORCED_CLASSES",
    "POLARITIES",
    "RESULT_VALUES",
    "PREDICATE_TYPE",
    "STATEMENT_TYPE",
    "Verdict",
    "base_schema",
    "build_record",
    "sha256_file",
    "sha256_hex",
    "validate_base",
]
