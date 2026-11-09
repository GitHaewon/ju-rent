"""Rule text and optional, number-checked OpenAI explanation of a judgment."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
NUMBER = re.compile(r"(?<![0-9A-Za-z_.])\d+(?:,\d{3})*(?:\.\d+)?(?![0-9A-Za-z_.])")


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
        for key, item in value.items():
            found.update(_numbers(str(key)))
            found.update(_numbers(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_numbers(item))
    elif isinstance(value, (int, float, str)) and not isinstance(value, bool):
        for match in NUMBER.finditer(str(value)):
            try:
                found.add(Decimal(match.group().replace(",", "")))
            except InvalidOperation:
                continue
    return found


def has_unsupported_numbers(text: str, result: dict) -> bool:
    """Reject any numerical token absent from the engine result JSON."""
    return not _numbers(text).issubset(_numbers(result))


def lowest_reasoning_effort(model: str) -> str:
    """Use the lowest documented effort for the supported model family."""
    model = model.lower()
    if model.startswith((
        "gpt-6-sol", "gpt-6-luna", "gpt-6.1-terra",
        "gpt-5.2", "gpt-5.4", "gpt-5.5", "gpt-5.6",
    )):
        return "none"
    if model.startswith(("gpt-6-astra", "gpt-6.1-sol")):
        return "low"
    raise ValueError("Set OPENAI_REASONING_EFFORT for this model")


def ai_explanation(result: dict, env_path: Path = ROOT / ".env") -> str:
    """Make one bounded API request, then fall back safely on any failure."""
    fallback = rule_explanation(result)
    try:
        config = dotenv_values(env_path)
        key = config.get("OPENAI_API_KEY")
        model = config.get("OPENAI_MODEL")
        if not key or not model:
            return fallback
        effort = config.get("OPENAI_REASONING_EFFORT") or lowest_reasoning_effort(model)
        from openai import OpenAI

        client = OpenAI(api_key=key, timeout=10, max_retries=0)
        response = client.responses.create(
            model=model,
            reasoning={"effort": effort},
            instructions=(
                "한국어로 이 계약 판단을 간단히 설명하세요. 입력 JSON의 사실과 숫자만 사용하고 "
                "새로운 수치나 가격을 만들어내지 마세요."
            ),
            input=json.dumps(result, ensure_ascii=False),
        )
        output = response.output_text.strip()
        if not output or has_unsupported_numbers(output, result):
            return fallback
        return output
    except Exception:  # noqa: BLE001 - optional service failures must never stop judgment
        return fallback
