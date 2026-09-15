import importlib.metadata
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def main():
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 252, 252), radius=55, fill="#E33D45")
    draw.polygon([(53, 67), (89, 67), (128, 151), (167, 67), (203, 67), (145, 191), (111, 191)], fill="#FFFFFF")
    draw.rounded_rectangle((84, 205, 172, 217), radius=6, fill="#FFFFFF")
    image.save(assets / "vidveya.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    image.save(assets / "vidveya.png")

    licenses = ROOT / ".build" / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    records = []
    dev = {"pytest", "pytest-qt", "ruff", "pillow", "pygments", "iniconfig", "pluggy", "packaging", "typing_extensions", "vidveya"}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if name.lower() in dev:
            continue
        records.append({"name": name, "version": distribution.version,
                        "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License", "See included notices"),
                        "project_urls": distribution.metadata.get_all("Project-URL", [])})
        for entry in distribution.files or []:
            if "license" in str(entry).lower() or "copying" in str(entry).lower():
                source = Path(distribution.locate_file(entry))
                if source.is_file() and source.suffix.lower() not in {".py", ".pyc", ".dll", ".exe"}:
                    destination = licenses / name / str(entry).replace("/", "_").replace("\\", "_")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    (licenses / "python-packages.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
