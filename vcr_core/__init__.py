"""vcr-core: the shared spine for the Verified-Check Record (VCR v0.1) program.

One home for the schema, the verdict vocabulary, the record builder, and the EES metric,
imported by The Enforcement Gap (N2) and HarnessBench so the three-project program cannot
drift on how a check is recorded or scored.
"""

from importlib.metadata import version

from vcr_core.score import EES, score_ees
from vcr_core.vcr import (
    CHECK_CATEGORIES,
    ENFORCED_CLASSES,
    POLARITIES,
    PREDICATE_TYPE,
    RESULT_VALUES,
    STATEMENT_TYPE,
    SUBJECT_KINDS,
    Verdict,
    base_schema,
    build_record,
    sha256_file,
    sha256_hex,
    validate_base,
)

__version__ = version("vcr-core")
__all__ = [
    "EES",
    "score_ees",
    "ENFORCED_CLASSES",
    "CHECK_CATEGORIES",
    "POLARITIES",
    "RESULT_VALUES",
    "SUBJECT_KINDS",
    "PREDICATE_TYPE",
    "STATEMENT_TYPE",
    "Verdict",
    "base_schema",
    "build_record",
    "sha256_file",
    "sha256_hex",
    "validate_base",
]
