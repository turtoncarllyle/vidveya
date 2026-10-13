import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"


def target_platform() -> str:
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "windows-x64" if machine in {"amd64", "x86_64", "x64"} else "windows-unsupported"
    if sys.platform == "darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x86_64"
    raise RuntimeError(f"不支持的打包平台：{sys.platform}/{machine}")


def run(*command, env=None):
    subprocess.run([str(item) for item in command], cwd=ROOT, check=True, env=env)


def extract_current_release_notes(version: str) -> str:
    content = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    pattern = rf"(?ms)^(#\s*v?{re.escape(version)}\b.*?)(?=^#\s*v|\Z)"
    match = re.search(pattern, content)
    return match.group(1).strip() if match else content


def copy_documentation(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("README.md", "README.en.md", "THIRD_PARTY_NOTICES.md", "RELEASE_NOTES.md"):
        shutil.copyfile(ROOT / filename, destination / filename)


def wrap_macos_app(source: Path) -> Path:
    app = ROOT / "dist" / "VidVeya.app"
    if app.exists():
        shutil.rmtree(app)
    contents = app / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    for child in source.iterdir():
        shutil.move(str(child), str(macos / child.name))
    source.rmdir()
    copy_documentation(resources / "Documentation")
    (contents / "Info.plist").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleDisplayName</key><string>VidVeya</string>
<key>CFBundleExecutable</key><string>VidVeya</string>
<key>CFBundleIdentifier</key><string>com.vidveya.app</string>
<key>CFBundleName</key><string>VidVeya</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.2.0</string>
<key>CFBundleVersion</key><string>0.2.0</string>
<key>LSMinimumSystemVersion</key><string>12.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSPrincipalClass</key><string>NSApplication</string>
</dict></plist>
""", encoding="utf-8")
    for executable in (macos / "VidVeya", macos / "VidVeya.Worker"):
        if executable.exists():
            executable.chmod(0o755)
    return app


def component_environment(worker: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    if sys.platform == "win32":
        environment["PATH"] = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32")
    else:
        environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        library_dir = worker.parent / "_internal" / "components" / "lib"
        if library_dir.is_dir():
            environment["DYLD_LIBRARY_PATH"] = str(library_dir)
    environment.pop("PYTHONPATH", None)
    environment.pop("VIRTUAL_ENV", None)
    return environment


def verify_worker(worker: Path):
    probe = subprocess.run([str(worker)], input='{"command":"diagnostics"}\n', capture_output=True,
                           encoding="utf-8", errors="replace", env=component_environment(worker), timeout=90,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if probe.returncode:
        raise RuntimeError((probe.stdout or "") + (probe.stderr or ""))
    diagnostics = json.loads(probe.stdout)["data"]
    if not all(component["ok"] for component in diagnostics.values()):
        raise RuntimeError(json.dumps(diagnostics, ensure_ascii=False))
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "packaged-diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")


def macos_archive(app: Path, path: Path):
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, path)


def macos_dmg(app: Path, path: Path):
    run("hdiutil", "create", "-volname", "VidVeya", "-srcfolder", app, "-ov", "-format", "UDZO", path)


def macos_fix_component_rpaths(app: Path):
    components = app / "Contents" / "MacOS" / "_internal" / "components"
    for name in ("ffmpeg", "ffprobe"):
        executable = components / name
        if executable.exists():
            listing = subprocess.run(["otool", "-l", executable], capture_output=True, text=True, check=True)
            if "@loader_path/lib" not in listing.stdout:
                run("install_name_tool", "-add_rpath", "@loader_path/lib", executable)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-provision", action="store_true")
    parser.add_argument("--package-only", action="store_true")
    args = parser.parse_args()
    target = target_platform()
    tmp = ROOT / ".build" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(tmp)
    os.environ["TMP"] = str(tmp)
    os.environ["PYTHONUTF8"] = "1"
    if not args.package_only:
        if not args.skip_provision:
            run(sys.executable, "scripts/provision.py")
        run(sys.executable, "scripts/prepare_assets.py")
        stale_dist = ROOT / "dist" / "VidVeya"
        if stale_dist.exists():
            shutil.rmtree(stale_dist)
        stale_app = ROOT / "dist" / "VidVeya.app"
        if stale_app.exists():
            shutil.rmtree(stale_app)
        run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--workpath", ".build/pyinstaller",
            "packaging/vidveya.spec")

    destination = ROOT / "dist" / "VidVeya"
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    assets: list[Path] = []
    if sys.platform == "win32":
        copy_documentation(destination)
        worker = destination / "VidVeya.Worker.exe"
        verify_worker(worker)
        archive = release / f"VidVeya-{VERSION}-win-x64-portable.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as package:
            for path in sorted(destination.rglob("*")):
                if path.is_file():
                    package.write(path, path.relative_to(destination.parent))
        run(ROOT / ".tooling" / "inno" / "ISCC.exe", "packaging/installer.iss")
        assets = [archive, release / f"VidVeya-{VERSION}-win-x64-setup.exe"]
    else:
        app = wrap_macos_app(destination)
        macos_fix_component_rpaths(app)
        worker = app / "Contents" / "MacOS" / "VidVeya.Worker"
        verify_worker(worker)
        archive = release / f"VidVeya-{VERSION}-{target}.zip"
        dmg = release / f"VidVeya-{VERSION}-{target}.dmg"
        macos_archive(app, archive)
        macos_dmg(app, dmg)
        assets = [dmg, archive]

    checksums = [f"{sha256(path)}  {path.name}" for path in assets]
    (release / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    (release / "RELEASE_NOTES_CURRENT.md").write_text(extract_current_release_notes(VERSION) + "\n", encoding="utf-8")
    print(f"Release assets ready for {target}: {release}", flush=True)


if __name__ == "__main__":
    main()
