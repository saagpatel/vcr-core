"""Fixture inventory, canonical form, source boundaries, and package contents."""

import hashlib
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from vcr_core.partial import FIXTURES_DIR, FORMAT_TAG, dump, load

ROOT = Path(__file__).parents[1]
FROZEN = {
    "vcr_core/schema/vcr-v0.1.schema.json": (
        "4117ccad2815cf870a6465406635443eb481bcc888e8d983f988320a8e6bd834"
    ),
    "vcr_core/__init__.py": "3843c4de26c41a30360187b6db0080d2d0204ae0566db500803b094c197ed207",
    "vcr_core/vcr.py": "8ab38df877641e7fe1c94cb99b90ff6274432c473f2e4e9fee57053c1a270d9f",
    "vcr_core/score.py": "1125a1703e62ab49bb3bf591705d3bf8e8586af4d872ceea73c96ec625f84853",
    "tests/test_record.py": "aa9f4cc57f217a60105f344f4c3c46497db599b14dda1b68d74cb59675f91f15",
    "tests/test_score.py": "38954d695b086aa731e9c0c3e4f52e3c9ebc86a6f1009227f0e72c3bd2905d20",
    "tests/test_distribution.py": (
        "f26f0cde624442e681227b954e8a6114bc405c09dbb352711232fe219d1351f3"
    ),
}


def test_fixture_inventory_and_canonical_files() -> None:
    files = sorted(FIXTURES_DIR.glob("**/*.pcas.json"))
    fixtures = [load(path) for path in files]
    assert len(fixtures) == 30
    assert {c.cls: sum(item.cls == c.cls for item in fixtures) for c in fixtures} == {
        "split_codepoint": 10,
        "partial_event": 10,
        "early_close": 10,
    }
    assert len({c.id for c in fixtures}) == 30
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert dump(load(text)) == text
    subprocess.run(
        [sys.executable, "scripts/build_partial_fixtures.py", "--check"], cwd=ROOT, check=True
    )
    count = subprocess.run(
        [sys.executable, "-m", "vcr_core.partial", "count"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert count.stdout.strip() == "split_codepoint=10 partial_event=10 early_close=10 total=30"


def test_format_tag_does_not_migrate_into_frozen_surface() -> None:
    exceptions = (".handoff/", "tests/")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "vcr_core/partial" in path.as_posix():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(exceptions):
            continue
        assert FORMAT_TAG not in path.read_text(encoding="utf-8", errors="ignore"), relative
    for relative, expected in FROZEN.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_wheel_and_sdist_include_schema_and_all_fixtures(tmp_path: Path) -> None:
    subprocess.run(["uv", "build", "--out-dir", str(tmp_path)], cwd=ROOT, check=True)
    wheel = next(tmp_path.glob("*.whl"))
    sdist = next(tmp_path.glob("*.tar.gz"))
    fixture_paths = {p.relative_to(ROOT).as_posix() for p in FIXTURES_DIR.glob("**/*.pcas.json")}
    schema = "vcr_core/partial/schema/partial-stream-v1.schema.json"
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert fixture_paths <= names
    assert schema in names
    with tarfile.open(sdist, "r:gz") as archive:
        names = {name.split("/", 1)[1] for name in archive.getnames() if "/" in name}
    assert fixture_paths <= names
    assert schema in names
