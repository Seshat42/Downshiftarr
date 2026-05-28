import hashlib
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from scripts.testing import verify_release_artifacts


def write_checksums(dist, *paths):
    lines = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}\n")
    (dist / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8")


def test_release_artifact_verifier_accepts_clean_wheel_and_sdist(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "downshiftarr-0.7.2-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("Downshiftarr.py", "print('clean')\n")
    sdist = dist / "downshiftarr-0.7.2.tar.gz"
    source = tmp_path / "Downshiftarr.py"
    source.write_text("print('clean')\n", encoding="utf-8")
    with tarfile.open(sdist, "w:gz") as archive:
        archive.add(source, arcname="downshiftarr-0.7.2/Downshiftarr.py")
    write_checksums(dist, wheel, sdist)

    assert verify_release_artifacts.find_artifact_findings(dist) == []


def test_release_artifact_verifier_runs_by_script_path(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "downshiftarr-0.7.2-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("Downshiftarr.py", "print('clean')\n")
    write_checksums(dist, wheel)

    script = Path(__file__).resolve().parents[1] / "scripts" / "testing" / "verify_release_artifacts.py"
    completed = subprocess.run([sys.executable, str(script), str(dist)], cwd=tmp_path, text=True, stdout=subprocess.PIPE)

    assert completed.returncode == 0


def test_release_artifact_verifier_rejects_secret_paths_and_values(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "downshiftarr-0.7.2-py3-none-any.whl"
    token = "AbCdEfGhIjKlMnOp" + "QrStUvWxYz123456"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("Downshiftarr.env", f"PLEX_TOKEN={token}\n")
    write_checksums(dist, wheel)

    findings = verify_release_artifacts.find_artifact_findings(dist)

    assert "forbidden path in downshiftarr-0.7.2-py3-none-any.whl: Downshiftarr.env" in findings
    assert "potential secret in downshiftarr-0.7.2-py3-none-any.whl:Downshiftarr.env:1 for PLEX_TOKEN" in findings


def test_release_artifact_verifier_rejects_missing_checksum(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "downshiftarr-0.7.2-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("Downshiftarr.py", "print('clean')\n")
    (dist / "SHA256SUMS.txt").write_text("", encoding="utf-8")

    findings = verify_release_artifacts.find_artifact_findings(dist)

    assert "missing checksum entry for downshiftarr-0.7.2-py3-none-any.whl" in findings
