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
    assert explanation.has_unsupported_numbers("월세 34만 원", result)
    assert explanation.has_unsupported_numbers("50%이니 100% 안전합니다", result)
    assert explanation.unsupported_numbers("월세 34만 원, 차이 999만 원", result) == ["34", "999"]


def test_number_guard_allows_rounding_to_shown_places():
    result = {"values": [37.08, 65.54]}
    assert explanation.unsupported_numbers("37.1, 37, 65.5, 66", result) == []
    assert explanation.unsupported_numbers("37.2, 65.6, 차이 28.46", result) == ["37.2", "65.6", "28.46"]


def test_missing_key_uses_rule_text(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENAI_MODEL=gpt-6-luna\n", encoding="utf-8")
    result = sample_result()
    assert explanation.ai_explanation(result, env) == explanation.ExplanationResult(
        explanation.rule_explanation(result), "API 키 없음",
    )


def test_missing_model_uses_rule_text(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    result = sample_result()
    assert explanation.ai_explanation(result, env).fallback_reason == "모델 없음"


def test_lowest_effort_varies_by_model():
    assert explanation.lowest_reasoning_effort("gpt-6-luna") == "none"
    assert explanation.lowest_reasoning_effort("gpt-6.1-terra") == "none"
    assert explanation.lowest_reasoning_effort("gpt-6.1-sol") == "low"
    assert explanation.lowest_reasoning_effort("custom-model") is None


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
    assert explanation.ai_explanation(result, env) == explanation.ExplanationResult(
        "백분위 50으로 보통입니다.",
    )
    assert calls[0][1]["timeout"] == 10
    assert calls[0][1]["max_retries"] == 0
    assert calls[1][1]["reasoning"] == {"effort": "none"}
    assert calls[1][1]["max_output_tokens"] == 500
    assert "존댓말로 3~4문장" in calls[1][1]["instructions"]
    assert "차이와 비율을 새로 계산하지 마세요" in calls[1][1]["instructions"]
    assert "warnings 중 하나" in calls[1][1]["instructions"]
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
    assert explanation.ai_explanation(result, env) == explanation.ExplanationResult(
        explanation.rule_explanation(result), "숫자 검사 실패: 999",
    )
    assert captured["reasoning"] == {"effort": "low"}


def test_unknown_model_omits_reasoning(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=test-key\nOPENAI_MODEL=custom-model\n", encoding="utf-8")
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text="보통입니다.")

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    assert explanation.ai_explanation(sample_result(), env).fallback_reason is None
    assert "reasoning" not in captured


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
    assert explanation.ai_explanation(result, env) == explanation.ExplanationResult(
        explanation.rule_explanation(result), "시간 초과",
    )


def test_api_error_reports_class_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=test-key\nOPENAI_MODEL=gpt-6-luna\n", encoding="utf-8")

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            raise RuntimeError("secret-key-must-not-appear")

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    result = explanation.ai_explanation(sample_result(), env)
    assert result.fallback_reason == "API 오류(RuntimeError)"
    assert "secret-key" not in str(result)


def test_app_default_input_runs_without_error():
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not app.exception
    assert not app.error
    assert len(app.metric) == 3
    assert app.metric[0].value in {"저렴한 편", "보통", "비싼 편", "많이 비싼 편", "표본 부족"}


def test_app_fallback_shows_reason_once(monkeypatch):
    monkeypatch.setattr(
        explanation, "ai_explanation",
        lambda result: explanation.ExplanationResult(explanation.rule_explanation(result), "시간 초과"),
    )
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    app.button[0].click().run()
    assert not app.exception
    assert any("사유: 시간 초과" in item.proto.body for item in app.info)
    assert sum("입력 매물의 환산 월세는" in item.value for item in app.markdown) == 1


def test_histogram_counts_match_engine_sample():
    result = engine.judge("효자동권", "detached_multiunit", 25, 500, 35)
    assert sum(item["count"] for item in result["histogram_10k_krw"]) == result["n"]
