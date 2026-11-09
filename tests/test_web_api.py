"""SPEC-003 API is only an adapter; verified engine output stays identical."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api import main
from src.jurent import engine
from src.jurent.explanation import ExplanationResult

client = TestClient(main.app)
BASE = {"area": 25, "deposit": 500, "monthly": 35}


def test_meta_comes_from_engine_configuration():
    response = client.get("/api/meta")
    assert response.status_code == 200
    meta = response.json()
    assert meta["campuses"] == ["효자동권", "전북대권"]
    assert {item["code"] for item in meta["housing_types"]} == {
        "detached_multiunit", "officetel", "multifamily", "apartment",
    }
    assert meta["rate"]["default_pct"] == engine.default_rate_pct()
    assert meta["data_as_of"] == engine.DATA_END


def test_judge_matches_engine_for_every_campus_and_type():
    for campus in ("효자동권", "전북대권"):
        for housing_type in ("detached_multiunit", "officetel", "multifamily", "apartment"):
            payload = {**BASE, "campus": campus, "housing_type": housing_type}
            response = client.post("/api/judge", json=payload)
            assert response.status_code == 200
            assert response.json() == engine.judge(**payload)


def test_invalid_inputs_return_korean_422():
    valid = {**BASE, "campus": "효자동권", "housing_type": "detached_multiunit"}
    for change in ({"area": 14.99}, {"area": 45.01}, {"monthly": 0},
                   {"rate_pct": 10.01}, {"campus": "없는 대학가"}):
        response = client.post("/api/judge", json={**valid, **change})
        assert response.status_code == 422
        assert "주세요" in response.json()["detail"]
    response = client.post("/api/judge", json={**valid, "area": "잘못된 숫자"})
    assert response.status_code == 422
    assert "확인해 주세요" in response.json()["detail"]


def test_explain_recomputes_on_server_and_rejects_result_dict(monkeypatch):
    captured = []

    def fake_judge(**kwargs):
        captured.append(kwargs)
        return {"label": "보통", "n": 30}

    def fake_explanation(result):
        captured.append(result)
        return ExplanationResult("기본 설명", "시간 초과")

    monkeypatch.setattr(main.engine, "judge", fake_judge)
    monkeypatch.setattr(main, "ai_explanation", fake_explanation)
    payload = {**BASE, "campus": "효자동권", "housing_type": "detached_multiunit"}
    response = client.post("/api/explain", json=payload)
    assert response.json() == {"text": "기본 설명", "source": "rule", "reason": "시간 초과"}
    assert captured[0] == {**payload, "construction_year": None, "rate_pct": None}
    assert captured[1] == {"label": "보통", "n": 30}
    assert client.post("/api/explain", json={**payload, "result": {"label": "가짜"}}).status_code == 422


def test_api_never_serializes_key(monkeypatch):
    secret = "TEST_KEY_MUST_STAY_SERVER_SIDE"
    monkeypatch.setattr(main.engine, "judge", lambda **_kwargs: {"label": "보통"})
    monkeypatch.setattr(main, "ai_explanation", lambda _result: ExplanationResult("설명", "API 오류(RuntimeError)"))
    payload = {**BASE, "campus": "효자동권", "housing_type": "detached_multiunit"}
    assert secret not in client.post("/api/judge", json=payload).text
    assert secret not in client.post("/api/explain", json=payload).text
