# 수치 대장 (NUMBERS)

> **기획서·발표·대시보드에 쓰는 모든 숫자는 이 표에 있어야 한다.**
> - 값은 반드시 `src/`의 스크립트가 `outputs/`(또는 `data/audit/`)에 만든 파일에서 가져온다.
> - 손으로 계산하거나 추정한 숫자, AI가 말한 숫자는 등록하지 않는다.
> - 확인할 수 없는 값은 `확인 불가`로 적고 비워 두지 않는다.
> - 검증 상태: `미검증`(산출만 됨) → `검증됨`(Claude Code가 재실행해 일치 확인) → `불일치`(원인 조사 필요)

| ID | 수치 | 값 | 출처 파일 | 스크립트 | 산출일 | 검증 상태 |
|---|---|---|---|---|---|---|
| N-001 | 완산·덕진 2021~2025 전월세 공개 행 수 | 104,144 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 |
| N-002 | 연도별 공개 행 수 (2021~2025) | 21,256 / 23,666 / 21,083 / 19,594 / 18,545 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 |
| N-003 | 효자동2가·3가 소형 월세 유효 표본 (2021~2025 합계) | 5,799 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 (D-011·D-012, reviews/2026-11-02-표본정의-수정.md) |
| N-004 | 유효 표본 연도별 (2021~2025) | 921 / 1,123 / 1,044 / 1,219 / 1,492 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 (D-011·D-012, reviews/2026-11-02-표본정의-수정.md) |
| N-005 | 2025 유효 표본 월세 구간 (20만 미만 / 20대 / 30대 / 40대 / 50 이상) | 193 / 233 / 546 / 305 / 215 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 (D-011·D-012, reviews/2026-11-02-표본정의-수정.md) |
| N-006 | 2025 유효 표본 주택유형 (단독다가구 / 오피스텔 / 아파트 / 연립다세대) | 1,308 / 109 / 70 / 5 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 (D-011·D-012, reviews/2026-11-02-표본정의-수정.md) |
| N-007 | 효자동2·3가 단독·다가구 지번 마스킹 건수 / 전체 건수 | 12,303 / 12,305 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 (D-011·D-012, reviews/2026-11-02-표본정의-수정.md) |
| N-008 | 전주 전체 단독·다가구 지번 마스킹 건수 / 전체 건수 | 40,534 / 40,539 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 (reviews/2026-11-02-표본정의-수정.md) |
| N-009 | 효자동2·3가 유효 표본 면적 기준별 건수 (전용 / 계약) | 863 / 4,936 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-02 | 검증됨 (reviews/2026-11-02-표본정의-수정.md) |
| N-010 | 완산·덕진 2026-01~10 전월세 공개 행 수 (부분 연도) | 15,217 | data/audit/counts.json (`year_2026.total`) | src/analyze_rentals.py | 2026-11-07 | 검증됨 (reviews/2026-11-07-2026데이터-대학가후보.md) |
| N-011 | 효자동2·3가 2026-01~10 소형 월세 유효 표본 (부분 연도) | 1,318 | data/audit/counts.json (`year_2026.analytic`) | src/analyze_rentals.py | 2026-11-07 | 검증됨 (reviews/2026-11-07-2026데이터-대학가후보.md) |
| N-012 | 유효 표본 연도별 계약구분 (신규 / 갱신 / 미기재, 2021→2026) | 231/3/687 · 452/19/652 · 509/20/515 · 1,035/60/124 · 1,343/60/89 · 1,173/52/93 | data/audit/counts.json (`contract_by_year`) | src/analyze_rentals.py | 2026-11-07 | 검증됨 (reviews/2026-11-07-2026데이터-대학가후보.md) |
| N-013 | 덕진구 아파트 2026-04 단지 집중 (전체 / 상위 단지 / 상위 두 단지) | 1,780 / 794 (44.6%) / 1,500 (84.3%) | data/audit/counts.json (`apartment_deokjin_2026_april`) | src/analyze_rentals.py | 2026-11-07 | 검증됨 (reviews/2026-11-07-2026데이터-대학가후보.md) |
| N-014 | 대학가 후보 법정동별 연도·주택유형별 유효 표본 | 각 행의 `유효_표본_수`·주택유형 열 참조 | outputs/campus_dong_candidates.csv | src/analyze_rentals.py | 2026-11-07 | 검증됨 (reviews/2026-11-07-2026데이터-대학가후보.md) |
| N-015 | 주택유형별 건축년도 열 보유 파일 수 / 전체 파일 수·결측 행 수 / 전체 행 수·결측률 (아파트 / 연립다세대 / 단독다가구 / 오피스텔, 2021~2026) | 12/12·0/63,951·0.00% / 12/12·0/3,050·0.00% / 12/12·5,151/47,401·10.87% / 12/12·0/4,959·0.00% | outputs/field_coverage.json | src/audit_field_coverage.py | 2026-11-07 | 검증됨 (reviews/2026-11-09-필요성근거-대학가추세.md) |
| N-016 | 전주 전체·효자동권·전북대권 연도별 월세 건수 / 전월세 건수 / 비중 (전주 전체는 N-013 상위 두 단지 포함·제외 병기) | 각 연도·범위·포함 여부의 `monthly_rows`·`total_rows`·`monthly_share_pct` 참조 | outputs/rationale/monthly_share.csv | src/analyze_rentals.py | 2026-11-09 | 검증됨 (제외는 2026-04 한정, reviews/2026-11-09-필요성근거-대학가추세.md) |
| N-017 | 효자동권·전북대권 소형 월세 유효 표본 연도별 건수·2021 대비 증감률, 전주 전체 공개 행 증감률 | 각 행의 `valid_small_monthly`·`change_from_2021_pct`·`city_change_from_2021_pct` 참조 | outputs/rationale/campus_trend.csv | src/analyze_rentals.py | 2026-11-09 | 검증됨 (2026 증감률은 10개월 대 12개월, reviews/2026-11-09-필요성근거-대학가추세.md) |
| N-018 | 전주시 20대 1인가구 (2021→2025, 20~24세와 25~29세 합계) | 23,511 / 22,249 / 22,723 / 21,739 / 21,781 | outputs/rationale/single_households.csv (`age_20s_total`), outputs/rationale/single_households_sources.json | src/build_single_households.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-필요성근거-대학가추세.md) |
| N-019 | 대학가별 D-011 유효 표본 연도·주택유형·상위 3개 원본 주소 조합 집중도 (2021~2026) | `campus_areas`의 대학가별 `by_year`·`by_type`·`address_concentration` 참조 | data/audit/counts.json | src/analyze_rentals.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-필요성근거-대학가추세.md) |

> N-001~N-007은 Codex 심층 검증 결과에서 옮긴 값이다. 저장소 이전 후 Claude Code가 스크립트를 재실행해 검증 상태를 갱신한다. 출처 파일·스크립트 경로는 저장소 정리 후 실제 경로로 수정한다.

## 외부 인용

> 공식 기관 통계를 그대로 인용하는 값. 계산·가공 금지. 가공이 필요하면 원자료를 받아 위 표에서 코드로 산출.

| ID | 수치 | 값 | 기관·자료명 | URL | 기준 시점 | 조회일 |
|---|---|---|---|---|---|---|
| E-001 | 전국 확정일자 기준 월세 비중 | 2020 40.7% → 2025(1~7월) 61.9% — **원자료 재확인 필요** | 대법원 등기정보광장(세계일보 2025-08-17 보도) | https://www.segye.com/newsView/20250817504692 | 2020 / 2025(1~7월) | 2026-11-09 |
| E-002 | 대학 기숙사 수용률 | 전체 22.2%, 비수도권 25.5% — **2019년 기준, 대학알리미 최신값(T12)으로 대체 예정** | 국회입법조사처 NARS현안분석(2019) | https://dhnews.co.kr/news/view/179520548913559 | 2019년 | 2026-11-09 |
