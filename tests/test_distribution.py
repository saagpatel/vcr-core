"""Built wheel and source archive contents."""

import subprocess
import tarfile
import zipfile
from pathlib import Path


def test_built_artifacts_include_runtime_files_and_exclude_venv(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    subprocess.run(["uv", "build", "--out-dir", str(tmp_path)], cwd=root, check=True)

    wheels = list(tmp_path.glob("*.whl"))
    sdists = list(tmp_path.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1

    with zipfile.ZipFile(wheels[0]) as wheel:
        wheel_names = set(wheel.namelist())
    assert "vcr_core/py.typed" in wheel_names
    assert "vcr_core/schema/vcr-v0.1.schema.json" in wheel_names

    with tarfile.open(sdists[0], "r:gz") as sdist:
        sdist_names = sdist.getnames()
    assert any(name.endswith("/vcr_core/py.typed") for name in sdist_names)
    assert any(name.endswith("/vcr_core/schema/vcr-v0.1.schema.json") for name in sdist_names)
    assert not any(".venv" in name.split("/") for name in sdist_names)
