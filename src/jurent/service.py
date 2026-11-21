"""Framework-independent product operations shared by API and static site."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src import analyze_rentals as audit
from src.jurent import area, commute, engine
from src.jurent import dataset as rental_dataset
from src.jurent.explanation import rule_explanation

HOUSING = [
    {"code": "oneroom", "name": "원룸·투룸·빌라", "description": "단독다가구·연립다세대 합친 비교"},
    {"code": "detached_multiunit", "name": "원룸·다가구", "description": "단독다가구 실거래 자료"},
    {"code": "officetel", "name": "오피스텔", "description": "오피스텔 실거래 자료"},
    {"code": "multifamily", "name": "빌라", "description": "연립다세대 실거래 자료"},
    {"code": "apartment", "name": "아파트", "description": "아파트 실거래 자료"},
]
FORMAT_ERROR = "입력 형식이 맞지 않아요. 숫자와 필수 항목을 확인해 주세요."


class InputError(ValueError):
    """A user-facing error with the same 422 detail as the HTTP API."""


class ContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campus: str
    housing_type: str
    area: float
    deposit: float
    monthly: float
    construction_year: int | None = None
    rate_pct: float | None = None
    dong: str | None = None
    school: str | None = None


class BudgetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campus: str
    deposit: float
    monthly: float
    min_area: float | None = None
    housing: str | None = None
    priority: str = "cheap"
    rate_pct: float | None = None
    scope: str = Field(default="commute", description="기본 통학권: 대학가 동과 선택 학교의 직행 통학권 동. campus를 주면 대학가 동만 비교합니다.")
    school: str | None = None


def area_input_error(exc: ValueError) -> str:
    message = str(exc)
    if "school" in message or "scope" in message:
        return "학교와 추천 범위를 목록에서 다시 선택해 주세요."
    if "campus" in message or "housing type" in message:
        return "대학가와 집 종류를 목록에서 다시 선택해 주세요."
    if "priority" in message:
        return "정렬 기준을 목록에서 다시 선택해 주세요."
    if "area" in message:
        return "최소 면적을 집 종류의 허용 범위 안에서 입력해 주세요."
    if "budget" in message:
        return "보증금과 월세 예산은 0 이상으로 입력해 주세요."
    if "rate" in message or "Rate" in message or "numbers" in message:
        return "환산율은 2% 이상 10% 이하로 입력해 주세요."
    return "입력값을 확인하고 다시 시도해 주세요."


def input_error(exc: ValueError) -> str:
    message = str(exc)
    if "school" in message or "dong" in message:
        return "학교와 동네를 목록에서 다시 선택해 주세요."
    if "campus" in message or "housing type" in message:
        return "대학가와 집 종류를 목록에서 다시 선택해 주세요."
    if "Area" in message:
        if "apartment" in message:
            return "아파트 면적은 132㎡ 이하로 입력해 주세요."
        return "면적은 15㎡ 이상 45㎡ 이하로 입력해 주세요."
    if "Deposit" in message:
        return "보증금은 0 이상, 월세는 0보다 크게 입력해 주세요."
    if "rate" in message or "Rate" in message:
        return "환산율은 허용 범위 안에서 선택해 주세요."
    if "construction" in message:
        return "건축년도는 허용 범위 안의 정수로 입력해 주세요."
    return "입력값을 확인하고 다시 시도해 주세요."


def _validate(model: type[BaseModel], values: dict) -> BaseModel:
    try:
        return model.model_validate(values)
    except ValidationError:
        raise InputError(FORMAT_ERROR) from None


def meta() -> dict:
    config = engine.settings()
    window = rental_dataset.select("current")
    return {
        "campuses": list(audit.CAMPUS_AREAS),
        "schools_by_campus": {campus: list(schools) for campus, schools in commute.SCHOOLS_BY_CAMPUS.items()},
        "commute_deal_counts_by_school": area.commute_dong_deal_counts("current"),
        "commute_by_school": {
            school: commute.commute_rows(campus, school)
            for campus, schools in commute.SCHOOLS_BY_CAMPUS.items()
            for school in schools
        },
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
        "data_as_of": window.data_end,
        "refreshed_on": window.refreshed_on,
    }


def judge(values: dict) -> dict:
    payload = _validate(ContractInput, values)
    try:
        kwargs = payload.model_dump(exclude={"dong", "school"})
        if payload.dong is not None:
            kwargs.update(dong=payload.dong, school=payload.school)
        return engine.judge(**kwargs, dataset="current")
    except ValueError as exc:
        raise InputError(input_error(exc)) from None


def explain_rule(values: dict) -> dict:
    result = judge(values)
    return {"text": rule_explanation(result), "source": "rule", "reason": result["label"]}


def budget(values: dict) -> dict:
    payload = _validate(BudgetInput, values)
    minimum = (40 if payload.housing == "apartment" else 15) if payload.min_area is None else payload.min_area
    try:
        return area.budget_search(
            payload.campus, payload.deposit, payload.monthly, minimum,
            payload.housing, payload.priority, payload.rate_pct,
            scope=payload.scope, school=payload.school, dataset="current",
        )
    except ValueError as exc:
        raise InputError(area_input_error(exc)) from None


def compare(rate_pct: float | None = None, school: str | None = None) -> dict:
    try:
        return area.campus_compare(rate_pct, school, dataset="current")
    except ValueError as exc:
        raise InputError(area_input_error(exc)) from None
