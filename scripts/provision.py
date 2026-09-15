"""Build-time component provisioning; never invoked by the released application."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / ".tooling"
RUNTIME = TOOLING / "runtime"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def provision(name, item):
    cache = TOOLING / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / item["url"].rsplit("/", 1)[1]
    if not archive.exists() or digest(archive) != item["sha256"]:
        print(f"Downloading {name} {item['version']}...", flush=True)
        partial = archive.with_suffix(archive.suffix + ".part")
        request = urllib.request.Request(item["url"], headers={"User-Agent": "VidVeya-build/0.1.5"})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as target:
            shutil.copyfileobj(response, target, 1024 * 1024)
        if digest(partial) != item["sha256"]:
            raise RuntimeError(f"{name}: SHA-256 mismatch")
        partial.replace(archive)
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
        with zipfile.ZipFile(archive) as bundle:
            for filename in item["files"]:
                members = [n for n in bundle.namelist() if n.rsplit("/", 1)[-1] == filename]
                if len(members) != 1:
                    raise RuntimeError(f"{filename}: expected exactly one archive member")
                with bundle.open(members[0]) as source, (RUNTIME / filename).open("wb") as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
            for member in bundle.namelist():
                if "license" in member.lower() and not member.endswith("/"):
                    destination = RUNTIME / "licenses" / name / member.replace("/", "_")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(bundle.read(member))
    print(f"Verified {name} {item['version']}", flush=True)


if __name__ == "__main__":
    manifest = json.loads((ROOT / "scripts" / "components.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(provision, name, item) for name, item in manifest.items()]
        for future in futures:
            future.result()
    (RUNTIME / "components.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
