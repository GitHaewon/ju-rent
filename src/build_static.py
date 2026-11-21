"""Package only the committed service inputs needed by the browser runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "web/public/py"
MODULES = [
    "src/analyze_rentals.py", "src/jurent/__init__.py",
    "src/jurent/area.py", "src/jurent/commute.py", "src/jurent/compare.py",
    "src/jurent/data.py", "src/jurent/dataset.py", "src/jurent/engine.py",
    "src/jurent/explanation.py", "src/jurent/service.py",
]
FORBIDDEN = (".env", "data/raw/", "reviews/", "outputs/compare/", "outputs/static/")
KEY_MARKERS = (b"OPENAI_API_KEY=", b"serviceKey=", b"SERVICE_KEY=")


def selected_files() -> list[Path]:
    result = [ROOT / relative for relative in MODULES]
    result += [ROOT / "config/settings.toml"]
    for folder in ("data/processed/current", "outputs/bus"):
        result += sorted(path for path in (ROOT / folder).rglob("*") if path.is_file())
    return result


def build() -> dict[str, str]:
    files = selected_files()
    manifest: dict[str, str] = {}
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if (path.name == ".env" or any(relative == rule or relative.startswith(rule) for rule in FORBIDDEN)
                or not (relative in MODULES or relative == "config/settings.toml"
                        or relative.startswith(("data/processed/current/", "outputs/bus/")))):
            raise ValueError(f"Forbidden path in static bundle: {relative}")
        if not path.exists():
            raise FileNotFoundError(path)
        content = path.read_bytes()
        if any(marker in content for marker in KEY_MARKERS):
            raise ValueError(f"Key marker in static bundle input: {relative}")
        manifest[relative] = hashlib.sha256(content).hexdigest()
    DEST.mkdir(parents=True, exist_ok=True)
    with ZipFile(DEST / "jurent_bundle.zip", "w", compression=ZIP_DEFLATED) as bundle:
        for relative in sorted(manifest):
            bundle.write(ROOT / relative, relative)
    (DEST / "bundle_manifest.json").write_text(
        json.dumps({"files": manifest}, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(f"정적 묶음 {len(build())}개 파일 생성")
