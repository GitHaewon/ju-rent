"""Thin HTTP adapter around the existing contract judgment engine."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError as FastAPIValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src import analyze_rentals as audit
from src.jurent import engine
from src.jurent.explanation import ai_explanation

app = FastAPI(title="JU RENT API")

HOUSING = [
    {"code": "detached_multiunit", "name": "원룸·다가구", "description": "단독다가구 실거래 자료"},
    {"code": "officetel", "name": "오피스텔", "description": "오피스텔 실거래 자료"},
    {"code": "multifamily", "name": "빌라", "description": "연립다세대 실거래 자료"},
    {"code": "apartment", "name": "아파트", "description": "아파트 실거래 자료"},
]


class ContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campus: str
    housing_type: str
    area: float
    deposit: float
    monthly: float
    construction_year: int | None = None
    rate_pct: float | None = None


def input_error(exc: ValueError) -> str:
    message = str(exc)
    if "campus" in message or "housing type" in message:
        return "대학가와 집 종류를 목록에서 다시 선택해 주세요."
    if "Area" in message:
        return "면적은 15㎡ 이상 45㎡ 이하로 입력해 주세요."
    if "Deposit" in message:
        return "보증금은 0 이상, 월세는 0보다 크게 입력해 주세요."
    if "rate" in message or "Rate" in message:
        return "환산율은 허용 범위 안에서 선택해 주세요."
    if "construction" in message:
        return "건축년도는 허용 범위 안의 정수로 입력해 주세요."
    return "입력값을 확인하고 다시 시도해 주세요."


@app.exception_handler(FastAPIValidationError)
async def validation_error_handler(_request, _exc: FastAPIValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "입력 형식이 맞지 않아요. 숫자와 필수 항목을 확인해 주세요."},
    )


@app.get("/api/meta")
def meta() -> dict:
    config = engine.settings()
    return {
        "campuses": list(audit.CAMPUS_AREAS),
        "housing_types": HOUSING,
        "rate": {
            "default_pct": engine.default_rate_pct(config),
            "base_rate_pct": config["base_rate_pct"],
            "base_rate_date": config["base_rate_date"],
            "legal_spread_pct": config["legal_spread_pct"],
            "legal_cap_pct": config["legal_cap_pct"],
            "min_pct": config["user_min_pct"],
            "max_pct": config["user_max_pct"],
        },
        "data_as_of": engine.DATA_END,
    }


def calculate(payload: ContractInput) -> dict:
    try:
        return engine.judge(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=input_error(exc)) from None


@app.post("/api/judge")
def judge(payload: ContractInput) -> dict:
    return calculate(payload)


@app.post("/api/explain")
def explain(payload: ContractInput) -> dict:
    result = calculate(payload)
    explanation = ai_explanation(result)
    return {
        "text": explanation.text,
        "source": "rule" if explanation.fallback_reason else "ai",
        "reason": explanation.fallback_reason,
    }
