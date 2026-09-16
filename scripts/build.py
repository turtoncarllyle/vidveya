import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.6"


def run(*command):
    subprocess.run([str(item) for item in command], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-provision", action="store_true")
    parser.add_argument("--package-only", action="store_true")
    args = parser.parse_args()
    tmp = ROOT / ".build" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(tmp)
    os.environ["TMP"] = str(tmp)
    os.environ["PYTHONUTF8"] = "1"
    if not args.package_only:
        if not args.skip_provision:
            run(sys.executable, "scripts/provision.py")
        run(sys.executable, "scripts/prepare_assets.py")
        # Remove stale one-folder files before COLLECT so a previous build
        # cannot leave conflicting native DLLs in the portable package.
        stale_dist = ROOT / "dist" / "VidVeya"
        if stale_dist.exists():
            shutil.rmtree(stale_dist)
        run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--workpath", ".build/pyinstaller", "packaging/vidveya.spec")
    destination = ROOT / "dist" / "VidVeya"
    for filename in ("README.md", "README.en.md", "THIRD_PARTY_NOTICES.md", "RELEASE_NOTES.md"):
        shutil.copyfile(ROOT / filename, destination / filename)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("VIRTUAL_ENV", None)
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    probe = subprocess.run([str(destination / "VidVeya.Worker.exe")], input='{"command":"diagnostics"}\n',
                           capture_output=True, encoding="utf-8", env=environment, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if probe.returncode:
        raise RuntimeError(probe.stdout + probe.stderr)
    diagnostics = json.loads(probe.stdout)["data"]
    if not all(component["ok"] for component in diagnostics.values()):
        raise RuntimeError(json.dumps(diagnostics))
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "packaged-diagnostics.json").write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    archive = release / f"VidVeya-{VERSION}-win-x64-portable.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(destination.parent))
    run(ROOT / ".tooling" / "inno" / "ISCC.exe", "packaging/installer.iss")
    checksums = []
    for path in (archive, release / f"VidVeya-{VERSION}-win-x64-setup.exe"):
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        checksums.append(f"{sha}  {path.name}")
    (release / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print("Release assets ready:", release, flush=True)


if __name__ == "__main__":
    main()
