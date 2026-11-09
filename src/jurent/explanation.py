"""Rule text and optional, number-checked OpenAI explanation of a judgment."""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import NamedTuple

from dotenv import dotenv_values
from openai import APITimeoutError

ROOT = Path(__file__).resolve().parents[2]
NUMBER = re.compile(r"(?<![0-9A-Za-z_.])\d+(?:,\d{3})*(?:\.\d+)?(?![0-9A-Za-z_.])")


class ExplanationResult(NamedTuple):
    text: str
    fallback_reason: str | None = None


def rule_explanation(result: dict) -> str:
    """Use only engine-returned facts and labels in the permanent explanation."""
    if result["label"] == "표본 부족":
        return (
            f"유사 거래 {result['n']}건으로 판단하기에 표본이 부족합니다. "
            f"비교 기간은 {result['comparison_period']['start']}~"
            f"{result['comparison_period']['end']}이고 적용 단계는 {result['step']}입니다."
        )
    return (
        f"입력 매물의 환산 월세는 {result['converted_monthly_10k_krw']:,.2f}만 원이며 "
        f"유사 거래 {result['n']}건 중 백분위 {result['percentile']:,.2f}로 "
        f"{result['label']}입니다. 비교 기간은 {result['comparison_period']['start']}~"
        f"{result['comparison_period']['end']}이고 적용 단계는 {result['step']}입니다."
    )


def _numbers(value: object) -> set[Decimal]:
    found: set[Decimal] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(_numbers(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_numbers(item))
    elif isinstance(value, (int, float, str)) and not isinstance(value, bool):
        for match in NUMBER.finditer(str(value)):
            found.add(Decimal(match.group().replace(",", "")))
    return found


def unsupported_numbers(text: str, result: dict) -> list[str]:
    """Find tokens unequal to every input number rounded to their shown precision."""
    allowed = _numbers(result)
    rejected: list[str] = []
    for match in NUMBER.finditer(text):
        token = match.group()
        amount = Decimal(token.replace(",", ""))
        places = len(token.partition(".")[2]) if "." in token else 0
        quantum = Decimal(1).scaleb(-places)
        if not any(value.quantize(quantum, rounding=ROUND_HALF_UP) == amount for value in allowed) and (
            token not in rejected
        ):
            rejected.append(token)
    return rejected


def has_unsupported_numbers(text: str, result: dict) -> bool:
    """Keep a boolean check for callers that do not need rejected tokens."""
    return bool(unsupported_numbers(text, result))


def lowest_reasoning_effort(model: str) -> str | None:
    """Return the lowest documented effort, or omit it for unknown models."""
    model = model.lower()
    if model.startswith((
        "gpt-6-sol", "gpt-6-luna", "gpt-6.1-terra",
        "gpt-5.2", "gpt-5.4", "gpt-5.5", "gpt-5.6",
    )):
        return "none"
    if model.startswith(("gpt-6-astra", "gpt-6.1-sol")):
        return "low"
    return None


def ai_explanation(result: dict, env_path: Path = ROOT / ".env") -> ExplanationResult:
    """Make one bounded API request and return text with a safe fallback reason."""
    fallback = rule_explanation(result)
    try:
        config = dotenv_values(env_path)
        key = config.get("OPENAI_API_KEY")
        model = config.get("OPENAI_MODEL")
        if not key:
            return ExplanationResult(fallback, "API 키 없음")
        if not model:
            return ExplanationResult(fallback, "모델 없음")
        effort = config.get("OPENAI_REASONING_EFFORT") or lowest_reasoning_effort(model)
        from openai import OpenAI

        client = OpenAI(api_key=key, timeout=10, max_retries=0)
        request = {
            "model": model,
            "instructions": (
                "대학생에게 존댓말로 3~4문장으로 설명하세요. 숫자는 입력 JSON에 있는 값을 "
                "그대로 쓰거나 반올림만 하세요. 차이와 비율을 새로 계산하지 마세요. "
                "입력 JSON의 warnings 중 하나를 꼭 포함하세요."
            ),
            "input": json.dumps(result, ensure_ascii=False),
            "max_output_tokens": 500,
        }
        if effort is not None:
            request["reasoning"] = {"effort": effort}
        response = client.responses.create(**request)
        output = response.output_text.strip()
        if not output:
            return ExplanationResult(fallback, "빈 응답")
        rejected = unsupported_numbers(output, result)
        if rejected:
            return ExplanationResult(fallback, f"숫자 검사 실패: {', '.join(rejected)}")
        return ExplanationResult(output)
    except (TimeoutError, APITimeoutError):
        return ExplanationResult(fallback, "시간 초과")
    except Exception as exc:  # noqa: BLE001 - optional service failures must never stop judgment
        return ExplanationResult(fallback, f"API 오류({type(exc).__name__})")
