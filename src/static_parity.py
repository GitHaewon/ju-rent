"""Create fixed CPython service outcomes for exact Pyodide comparison."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.jurent import service

OUT = Path(__file__).resolve().parents[1] / "outputs/static/parity_expected.json"


def cases() -> list[dict]:
    meta = service.meta()
    campuses = meta["campuses"]
    schools = [school for names in meta["schools_by_campus"].values() for school in names]
    result = [{"path": "/api/meta", "body": None}]
    base = {"area": 25, "deposit": 500, "monthly": 35}
    for campus in campuses:
        for housing in ("oneroom", "detached_multiunit", "officetel", "multifamily"):
            result.append({"path": "/api/judge", "body": {**base, "campus": campus, "housing_type": housing}})
    for campus, school in zip(campuses, (schools[0], schools[-1]), strict=True):
        dong = next(row["dong"] for row in meta["commute_by_school"][school] if not row["campus_area"])
        result.append({"path": "/api/judge", "body": {**base, "campus": campus, "housing_type": "oneroom", "dong": dong, "school": school}})
    first = {**base, "campus": campuses[0], "housing_type": "oneroom"}
    result += [
        {"path": "/api/judge", "body": {**first, "area": 132, "housing_type": "apartment"}},
        {"path": "/api/judge", "body": {**first, "area": 39.9, "housing_type": "apartment"}},
        {"path": "/api/judge", "body": {**first, "construction_year": 2020}},
        {"path": "/api/judge", "body": {**first, "rate_pct": 3}},
        {"path": "/api/judge", "body": {**first, "rate_pct": 8}},
        {"path": "/api/explain", "body": first},
        {"path": "/api/explain", "body": {**first, "area": 39.9, "housing_type": "apartment"}},
    ]
    for campus in campuses:
        for scope in ("commute", "campus"):
            for priority in ("cheap", "large"):
                result.append({"path": "/api/budget", "body": {"campus": campus, "deposit": 500, "monthly": 35, "scope": scope, "priority": priority}})
    for school in schools:
        result.append({"path": f"/api/compare?rate_pct=5&school={school}", "body": None})
    result.append({"path": "/api/compare?rate_pct=bad", "body": None})
    result += [
        {"path": "/api/judge", "body": {**first, "monthly": 0}},
        {"path": "/api/judge", "body": {**first, "area": "bad"}},
        {"path": "/api/budget", "body": {"campus": campuses[0], "deposit": -1, "monthly": 35}},
    ]
    return result


def run(path: str, body: dict | None) -> dict:
    url = urlsplit(path)
    try:
        if url.path == "/api/meta":
            value = service.meta()
        elif url.path == "/api/judge":
            value = service.judge(body)
        elif url.path == "/api/explain":
            value = service.explain_rule(body)
        elif url.path == "/api/budget":
            value = service.budget(body)
        else:
            query = parse_qs(url.query, keep_blank_values=True)
            rate = float(query["rate_pct"][0]) if "rate_pct" in query else None
            value = service.compare(rate, query.get("school", [None])[0])
        return {"status": 200, "body": value}
    except service.InputError as exc:
        return {"status": 422, "body": {"detail": str(exc)}}
    except ValueError:
        return {"status": 422, "body": {"detail": service.FORMAT_ERROR}}


def write() -> list[dict]:
    records = [{"path": case["path"], "input": case["body"],
                **run(case["path"], case["body"])} for case in cases()]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"cases": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


if __name__ == "__main__":
    print(f"정적 동등성 기준 {len(write())}건 저장")
