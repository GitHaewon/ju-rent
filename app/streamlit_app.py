"""JU RENT contract comparison screen (SPEC-002 PR-2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.jurent.engine import default_rate_pct, judge, settings
from src.jurent.explanation import ai_explanation, rule_explanation

HOUSING = {
    "원룸·다가구": "detached_multiunit",
    "빌라(연립·다세대)": "multifamily",
    "오피스텔": "officetel",
    "아파트": "apartment",
}
HOUSING_HELP = (
    "원룸·다가구는 단독다가구 실거래, 빌라는 연립다세대 실거래입니다. "
    "오피스텔과 아파트는 각각 별도 유형입니다."
)


def show_histogram(result: dict) -> None:
    bins = result["histogram_10k_krw"]
    if not bins:
        return
    plot_rows = [
        {"환산 월세": (item["left"] + item["right"]) / 2, "거래 수": item["count"]}
        for item in bins
    ]
    st.vega_lite_chart(
        pd.DataFrame(plot_rows),
        {
            "layer": [
                {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "환산 월세", "type": "quantitative", "title": "환산 월세 (만 원)"},
                        "y": {"field": "거래 수", "type": "quantitative"},
                        "tooltip": ["환산 월세", "거래 수"],
                    },
                },
                {
                    "data": {"values": [{"입력 위치": result["converted_monthly_10k_krw"]}]},
                    "mark": {"type": "rule", "color": "#dc2626", "strokeWidth": 2},
                    "encoding": {"x": {"field": "입력 위치", "type": "quantitative"}},
                },
            ]
        },
        width="stretch",
    )
    st.caption("빨간 선: 입력 매물의 환산 월세")


def main() -> None:
    st.set_page_config(page_title="JU RENT 계약 판단", layout="wide")
    st.title("JU RENT · 계약 판단")
    st.caption("전주시 대학가 법정동 실거래를 바탕으로 입력 계약의 상대 위치를 보여줍니다.")

    with st.sidebar:
        st.header("계약 조건")
        campus = st.selectbox("대학가", ["효자동권", "전북대권"])
        housing_label = st.selectbox("집 종류", list(HOUSING), help=HOUSING_HELP)
        area = st.number_input("면적 (㎡)", min_value=15.0, max_value=45.0, value=25.0, step=0.1)
        st.caption(f"약 {area / 3.305785:.1f}평")
        deposit = st.number_input("보증금 (만 원)", min_value=0.0, value=500.0, step=10.0)
        monthly = st.number_input("월세 (만 원)", min_value=0.01, value=35.0, step=1.0)
        fee = st.number_input(
            "관리비 (만 원, 선택)", min_value=0.0, value=0.0, step=1.0,
            help="계약 판단에서는 제외하고 총 월 부담에만 더합니다.",
        )
        use_year = st.checkbox("건축년도 입력")
        construction_year = (
            int(st.number_input("건축년도", min_value=1800, max_value=2026, value=2020))
            if use_year else None
        )
        conversion = settings()
        rate = st.slider(
            "보증금 월 환산율 (%)",
            min_value=float(conversion["user_min_pct"]),
            max_value=float(conversion["user_max_pct"]),
            value=float(default_rate_pct()),
            step=0.1,
        )
        st.caption(
            f"기준금리 {conversion['base_rate_pct']:.2f}% "
            f"({conversion['base_rate_date']}) + 법정 가산 {conversion['legal_spread_pct']:.1f}%p, "
            f"상한 {conversion['legal_cap_pct']:.1f}%. 시장 전환율이 아닙니다."
        )

    try:
        result = judge(
            campus, HOUSING[housing_label], area, deposit, monthly,
            construction_year=construction_year, rate_pct=rate,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        st.error(f"계약 판단을 표시할 수 없습니다: {exc}")
        return

    first, second, third = st.columns(3)
    first.metric("판단", result["label"])
    second.metric("백분위", "표본 부족" if result["percentile"] is None else f"{result['percentile']:.2f}")
    third.metric("환산 월세", f"{result['converted_monthly_10k_krw']:,.2f}만 원")
    st.caption(f"총 월 부담(월세 + 관리비): {monthly + fee:,.2f}만 원 · 관리비는 판단에서 제외")

    period = result["comparison_period"]
    st.write(
        f"유사 거래 **{result['n']}건** · 계약일 **{period['start']}~{period['end']}** "
        f"· 표본 확대 단계 **{result['step']}** (신규·미기재 계약)"
    )
    st.subheader("유사 거래 분포")
    show_histogram(result)
    if result["quantiles_10k_krw"]:
        q = result["quantiles_10k_krw"]
        st.table(pd.DataFrame([{"분위": key, "환산 월세 (만 원)": value} for key, value in q.items()]))
    else:
        st.info("유사 거래가 부족해 분위수를 표시하지 않습니다.")

    age = result["age_band_result"]
    if age:
        age_rank = "표본 부족" if age["percentile"] is None else f"{age['percentile']:.2f}"
        st.write(f"같은 경과연수구간({age['band']}) {age['n']}건: {age['label']} (백분위 {age_rank})")

    st.subheader("설명")
    st.write(rule_explanation(result))
    if st.button("AI로 쉽게 설명"):
        ai_result = ai_explanation(result)
        if ai_result.fallback_reason:
            st.info(f"AI 설명을 쓰지 못해 기본 설명을 유지합니다(사유: {ai_result.fallback_reason})")
        else:
            st.write(ai_result.text)

    st.subheader("해석 시 주의")
    for warning in result["warnings"]:
        st.warning(warning)
    st.caption(f"자료: 국토교통부 실거래가 공개시스템 · 계약 기준일 {result['data_as_of']}")


if __name__ == "__main__":
    main()
