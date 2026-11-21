"""SPEC-007: preserve HTTP outputs and exclude private data from Pages."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src import build_static, static_parity
from src.jurent import service

ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(app)


def test_main_api_baseline_stays_exact():
    baseline = json.loads((ROOT / "outputs/static/main_api_baseline.json").read_text(encoding="utf-8"))
    meta = CLIENT.get("/api/meta").json()
    assert meta == baseline["meta"]
    assert CLIENT.post("/api/budget", json={"campus": meta["campuses"][0], "deposit": 500,
                                            "monthly": 35}).json() == baseline["budget"]
    assert CLIENT.get("/api/compare").json() == baseline["compare"]


def test_service_matches_http_for_fixed_inputs():
    for case in static_parity.cases():
        if case["path"].startswith("/api/explain"):
            continue  # API mode may call optional AI; static mode always uses rules.
        path, body = case["path"], case["body"]
        response = CLIENT.post(path, json=body) if body is not None else CLIENT.get(path)
        expected = static_parity.run(path, body)
        assert response.status_code == expected["status"]
        assert response.json() == expected["body"]


def test_service_import_has_no_server_or_ai_dependencies():
    code = "import sys; import src.jurent.service; print(','.join(sorted(set(sys.modules)&{'fastapi','uvicorn','openai','dotenv','pandas'})))"
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == ""


def test_static_bundle_is_allowlisted_and_secret_free():
    manifest = build_static.build()
    archive = ROOT / "web/public/py/jurent_bundle.zip"
    assert manifest
    with ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == set(manifest)
        for name in bundle.namelist():
            assert name.startswith(("src/", "data/processed/current/", "outputs/bus/", "config/settings.toml"))
            assert hashlib.sha256(bundle.read(name)).hexdigest() == manifest[name]
    from src.check_static_secrets import check

    assert check([ROOT / "web/public/py", ROOT / "web/dist"]) >= 2


def test_static_service_errors_match_422():
    cases = static_parity.cases()[-3:]
    assert len(cases) == 3
    for case in cases:
        with pytest.raises(service.InputError) as error:
            (service.budget if case["path"] == "/api/budget" else service.judge)(case["body"])
        assert str(error.value) == static_parity.run(case["path"], case["body"])["body"]["detail"]


def test_captured_actions_log_key_scan(tmp_path):
    from src.check_static_secrets import check

    log = tmp_path / "pages-build.log"
    log.write_text("tests passed\n", encoding="utf-8")
    assert check([log]) == 1
    log.write_text("serviceKey=sentinel", encoding="utf-8")
    with pytest.raises(ValueError, match="Key content found"):
        check([log])


def test_bundle_refuses_hidden_env_even_under_bus(tmp_path, monkeypatch):
    hidden = tmp_path / "outputs/bus/.env"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(build_static, "ROOT", tmp_path)
    monkeypatch.setattr(build_static, "DEST", tmp_path / "public")
    monkeypatch.setattr(build_static, "selected_files", lambda: [hidden])
    with pytest.raises(ValueError, match="Forbidden path"):
        build_static.build()
