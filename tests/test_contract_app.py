"""PR-2 UI and optional explanation tests; all OpenAI calls are mocked."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from src.jurent import engine, explanation

ROOT = Path(__file__).resolve().parents[1]


def sample_result() -> dict:
    return {
        "label": "보통",
        "n": 30,
        "percentile": 50.0,
        "converted_monthly_10k_krw": 32.5,
        "comparison_period": {"start": "2024-11-01", "end": "2026-10-31"},
        "step": "기본",
    }


def test_number_guard_rejects_new_numbers():
    result = sample_result()
    assert not explanation.has_unsupported_numbers("백분위 50.00, 환산 월세 32.50만 원", result)
    assert explanation.has_unsupported_numbers("월세 33만 원", result)
    assert explanation.has_unsupported_numbers("50%이니 100% 안전합니다", result)


def test_missing_key_uses_rule_text(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENAI_MODEL=gpt-6-luna\n", encoding="utf-8")
    result = sample_result()
    assert explanation.ai_explanation(result, env) == explanation.rule_explanation(result)


def test_lowest_effort_varies_by_model():
    assert explanation.lowest_reasoning_effort("gpt-6-luna") == "none"
    assert explanation.lowest_reasoning_effort("gpt-6.1-terra") == "none"
    assert explanation.lowest_reasoning_effort("gpt-6.1-sol") == "low"


def test_openai_uses_only_engine_json_and_lowest_effort(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=test-key\nOPENAI_MODEL=gpt-6-luna\n", encoding="utf-8")
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("config", kwargs))
            self.responses = self

        def create(self, **kwargs):
            calls.append(("create", kwargs))
            return SimpleNamespace(output_text="백분위 50으로 보통입니다.")

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    result = sample_result()
    assert explanation.ai_explanation(result, env) == "백분위 50으로 보통입니다."
    assert calls[0][1]["timeout"] == 10
    assert calls[0][1]["max_retries"] == 0
    assert calls[1][1]["reasoning"] == {"effort": "none"}
    assert json.loads(calls[1][1]["input"]) == result
    assert len([call for call in calls if call[0] == "create"]) == 1


def test_explicit_effort_and_unsupported_output_fall_back(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "OPENAI_API_KEY=test-key\nOPENAI_MODEL=gpt-6-luna\nOPENAI_REASONING_EFFORT=low\n",
        encoding="utf-8",
    )
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text="월세 999만 원이 적정합니다.")

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    result = sample_result()
    assert explanation.ai_explanation(result, env) == explanation.rule_explanation(result)
    assert captured["reasoning"] == {"effort": "low"}


def test_timeout_uses_rule_text(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=test-key\nOPENAI_MODEL=gpt-6-luna\n", encoding="utf-8")

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            raise TimeoutError("timed out")

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    result = sample_result()
    assert explanation.ai_explanation(result, env) == explanation.rule_explanation(result)


def test_app_default_input_runs_without_error():
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not app.exception
    assert not app.error
    assert len(app.metric) == 3
    assert app.metric[0].value in {"저렴한 편", "보통", "비싼 편", "많이 비싼 편", "표본 부족"}


def test_histogram_counts_match_engine_sample():
    result = engine.judge("효자동권", "detached_multiunit", 25, 500, 35)
    assert sum(item["count"] for item in result["histogram_10k_krw"]) == result["n"]
