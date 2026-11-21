"""Fail before publishing if a bundle, build, or captured Actions log contains a key."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MARKERS = (b"OPENAI_API_KEY=", b"serviceKey=", b"SERVICE_KEY=")


def secret_values() -> tuple[bytes, ...]:
    path = ROOT / ".env"
    if not path.exists():
        return ()
    values = []
    for line in path.read_bytes().splitlines():
        key, separator, value = line.partition(b"=")
        if separator and (b"KEY" in key.upper() or b"SECRET" in key.upper()) and len(value.strip()) >= 8:
            values.append(value.strip().strip(b"\"'"))
    return tuple(values)


def check(paths: list[Path]) -> int:
    secrets = MARKERS + secret_values()
    checked = 0
    for path in paths:
        candidates = (p for p in path.rglob("*") if p.is_file()) if path.is_dir() else (path,)
        for candidate in candidates:
            if not candidate.exists():
                continue
            content = candidate.read_bytes()
            if any(secret and secret in content for secret in secrets):
                raise ValueError(f"Key content found in {candidate.relative_to(ROOT) if candidate.is_relative_to(ROOT) else candidate.name}")
            if candidate.suffix == ".zip":
                with ZipFile(candidate) as archive:
                    for name in archive.namelist():
                        if any(secret and secret in archive.read(name) for secret in secrets):
                            raise ValueError(f"Key content found in archive member: {name}")
            checked += 1
    return checked


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    targets = [ROOT / "web/public/py", ROOT / "web/dist"]
    if args.log:
        targets.append(args.log)
    print(f"비밀키 검사 통과: {check(targets)}개 파일")
