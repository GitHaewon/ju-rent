"""HTTP adapter for the framework-independent JU RENT service."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError as FastAPIValidationError
from fastapi.responses import JSONResponse

from src.jurent import service
from src.jurent.explanation import ai_explanation, rule_explanation

engine = service.engine  # Compatibility for existing API tests and callers.
app = FastAPI(title="JU RENT API")


@app.exception_handler(FastAPIValidationError)
async def validation_error_handler(_request, _exc: FastAPIValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": service.FORMAT_ERROR})


def _invoke(method, *args) -> dict:
    try:
        return method(*args)
    except service.InputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@app.get("/api/meta")
def meta() -> dict:
    return service.meta()


@app.post("/api/judge")
def judge(payload: service.ContractInput) -> dict:
    return _invoke(service.judge, payload.model_dump())


@app.post("/api/explain")
def explain(payload: service.ContractInput) -> dict:
    values = payload.model_dump()
    result = _invoke(service.judge, values)
    if result["label"] in {"판단 보류", "제공 안 함", "표본 부족"}:
        return {"text": rule_explanation(result), "source": "rule", "reason": result["label"]}
    explanation = ai_explanation(result)
    return {
        "text": explanation.text,
        "source": "rule" if explanation.fallback_reason else "ai",
        "reason": explanation.fallback_reason,
    }


@app.post("/api/budget")
def budget(payload: service.BudgetInput) -> dict:
    return _invoke(service.budget, payload.model_dump())


@app.get("/api/compare")
def campus_compare(rate_pct: float | None = None, school: str | None = None) -> dict:
    return _invoke(service.compare, rate_pct, school)
