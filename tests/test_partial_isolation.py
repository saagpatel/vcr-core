"""The existing top-level import stays independent of partial stream support."""

import hashlib
import subprocess
import sys
from pathlib import Path


def test_import_vcr_core_does_not_load_partial_package() -> None:
    root = Path(__file__).parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, vcr_core; assert 'vcr_core.partial' not in sys.modules",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_frozen_v01_schema_hash_is_unchanged() -> None:
    root = Path(__file__).parents[1]
    schema_path = root / "vcr_core/schema/vcr-v0.1.schema.json"
    digest = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    assert digest == "4117ccad2815cf870a6465406635443eb481bcc888e8d983f988320a8e6bd834"
