"""Build-time component provisioning; never invoked by the released application."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / ".tooling"
RUNTIME = TOOLING / "runtime"


def runtime_platform() -> str:
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "windows-x64" if machine in {"amd64", "x86_64", "x64"} else "windows-unsupported"
    if sys.platform == "darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x86_64"
    raise RuntimeError(f"不支持的构建平台：{sys.platform}/{machine}")


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def archive_path(item: dict) -> Path:
    cache = TOOLING / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    return cache / item["url"].rsplit("/", 1)[1]


def download_verified(name: str, item: dict) -> Path:
    archive = archive_path(item)
    if not archive.exists() or digest(archive) != item["sha256"]:
        print(f"Downloading {name} {item['version']}...", flush=True)
        partial = archive.with_suffix(archive.suffix + ".part")
        request = urllib.request.Request(item["url"], headers={"User-Agent": "VidVeya-build/0.2.0"})
        with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as target:
            shutil.copyfileobj(response, target, 1024 * 1024)
        if digest(partial) != item["sha256"]:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"{name}: SHA-256 mismatch")
        partial.replace(archive)
    return archive


def file_rules(item: dict) -> list[tuple[str, str]]:
    files = item.get("files", [])
    if isinstance(files, dict):
        return [(str(member), str(destination)) for member, destination in files.items()]
    return [(str(member), Path(str(member)).name) for member in files]


def find_member(names: list[str], requested: str) -> str:
    requested = requested.replace("\\", "/")
    exact = [name for name in names if name.rstrip("/") == requested]
    if exact:
        return exact[0]
    basename = Path(requested).name
    matches = [name for name in names if Path(name).name == basename and not name.endswith("/")]
    if len(matches) != 1:
        raise RuntimeError(f"{requested}: expected exactly one archive member, found {len(matches)}")
    return matches[0]


def safe_destination(relative: str) -> Path:
    destination = (RUNTIME / relative).resolve()
    if not destination.is_relative_to(RUNTIME.resolve()):
        raise RuntimeError(f"组件输出路径越界：{relative}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def extract_zip(name: str, item: dict, archive: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        for requested, destination_name in file_rules(item):
            member = find_member(names, requested)
            destination = safe_destination(destination_name)
            with bundle.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
            if sys.platform != "win32":
                destination.chmod(0o755)

        for pattern in item.get("include", []):
            matches = [name for name in names if fnmatch.fnmatch(name, pattern) and not name.endswith("/")]
            if not matches:
                raise RuntimeError(f"{pattern}: archive member not found")
            for member in matches:
                destination = safe_destination(str(PurePosixPath(member)))
                with bundle.open(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
                if destination.suffix == ".dylib":
                    destination.chmod(0o755)

        for member in names:
            if "license" in member.lower() or "copying" in member.lower() or "notice" in member.lower():
                if member.endswith("/"):
                    continue
                destination = safe_destination(f"licenses/{name}/{Path(member).name}")
                destination.write_bytes(bundle.read(member))


def provision(name: str, item: dict) -> None:
    archive = download_verified(name, item)
    if name == "inno":
        folder = TOOLING / "inno"
        if not (folder / "ISCC.exe").exists():
            result = subprocess.run([str(archive), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                                     "/CURRENTUSER", f"/DIR={folder}", "/NOICONS"],
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode != 0:
                raise RuntimeError(f"Inno Setup installer returned {result.returncode}")
    else:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        extract_zip(name, item, archive)
    print(f"Verified {name} {item['version']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default=None, help="覆盖自动识别的平台标识")
    args = parser.parse_args()
    target = args.platform or runtime_platform()
    manifest_path = ROOT / "scripts" / f"components-{target}.json"
    if not manifest_path.exists():
        raise RuntimeError(f"没有找到平台组件清单：{manifest_path.name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("platform", None)
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=min(3, len(manifest))) as pool:
        futures = [pool.submit(provision, name, item) for name, item in manifest.items()]
        for future in futures:
            future.result()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    runtime_manifest = {"platform": target, "components": manifest}
    (RUNTIME / "components.json").write_text(json.dumps(runtime_manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
