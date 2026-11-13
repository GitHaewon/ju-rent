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
| N-020 | 2023-12·2024-02 법정동 코드별 API·CSV 건수 대조 | 각 `rows`의 `api_rows`·`csv_rows`·`difference` 참조 | outputs/audit/lawd_code_check.json | src/check_lawd_codes.py | 2026-11-09 | 검증됨 (API 재호출은 2024-02 연립다세대 4건, reviews/2026-11-09-근거보강-민감도.md) |
| N-021 | 3개 대학 본교 연도별 재학생·기숙사 수용가능 인원·기숙사 밖 재학생 수 (2021~2026) | 각 행의 `재학생수`·`수용가능인원`·`기숙사 밖 재학생 수` 참조 | outputs/rationale/dorm_capacity.csv; outputs/rationale/dorm_capacity_sources.json | src/build_dorm_capacity.py | 2026-11-09 | 검증됨 (전북대 2026 공시값 확인 필요, reviews/2026-11-09-근거보강-민감도.md) |
| N-022 | 대학가 유효 표본·전주 전체 공개 행의 1~10월 동기간 증감률 | `jan_oct_` 열 참조 | outputs/rationale/campus_trend.csv | src/analyze_rentals.py | 2026-11-09 | 검증됨 (2026-09·10 미완성 가능, reviews/2026-11-09-근거보강-민감도.md) |
| N-023 | 덕진구 아파트 상위 두 단지 전 기간 제외 민감도·연도별 제외 행 | `variant=두 단지 전 기간 제외` 행과 `apartment_deokjin_top_two_all_years` 참조 | outputs/rationale/monthly_share.csv; data/audit/counts.json | src/analyze_rentals.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-근거보강-민감도.md) |
| N-024 | NO만 다른 완전 중복 행의 유형·연도별 건수와 대학가 지표 민감도 | 각 행의 원본·중복 제거 시 열 참조 | outputs/rationale/duplicate_sensitivity.csv | src/analyze_rentals.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-근거보강-민감도.md) |
| N-025 | 대학가 유효 표본 반기별 신고 의무 기준 분포 | 각 행의 `rows` 참조 | outputs/rationale/report_obligation.csv | src/analyze_rentals.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-근거보강-민감도.md) |
| N-026 | 대학가 유효 표본·전주 전체 공개 행의 1~8월 동기간 증감률 | `jan_aug_` 열 참조 | outputs/rationale/campus_trend.csv | src/analyze_rentals.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-계약판단엔진.md) |
| N-027 | 1~10월 동기간 NO 차이 중복 제거 민감도 | `record_kind=범위·연도·1~10월` 행 참조 | outputs/rationale/duplicate_sensitivity.csv | src/analyze_rentals.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-계약판단엔진.md) |
| N-028 | 전주 전체 D-011 유효 표본 정제 행 수·계약연도보다 건축년도가 뒤인 행 수 | 26,738 / 320 | data/processed/valid_small_monthly_audit.json (`total_rows`·`negative_age_rows`) | src/jurent/data.py | 2026-11-09 | 검증됨 (음수 경과연수 처리는 D-031로 해결, reviews/2026-11-09-계약판단엔진.md) |
| N-029 | 계약연도보다 건축년도가 1년 뒤인 행의 주택유형별 건수 | 전체 320 (아파트 318 / 단독다가구 2 / 연립다세대 0 / 오피스텔 0) | data/processed/valid_small_monthly_audit.json (`negative_age_values`·`negative_age_by_type`) | src/jurent/data.py | 2026-11-09 | 검증됨 (reviews/2026-11-09-계약판단엔진.md 재검증) |
| N-030 | 대학가·면적 구간·단독다가구/연립다세대/합친 유형의 최근 24개월 갱신 제외 환산 월세(r 5%) 건수·사분위·중앙값 | 각 행의 `건수`·`p25_만원`·`중앙값_만원`·`p75_만원` 참조 | outputs/compare/oneroom_pool_check.csv | src/jurent/compare.py | 2026-11-10 | 검증됨 (reviews/2026-11-10-판단보류-아파트비교.md, 효자동권 빌라 1~4건 구간 주의) |
| N-031 | 대학가·아파트 면적 구간의 최근 24개월 갱신 제외 환산 월세(r 5%) 건수·사분위·중앙값 | 각 행의 `건수`·`p25_만원`·`중앙값_만원`·`p75_만원` 참조 | outputs/compare/apartment_check.csv | src/jurent/compare.py | 2026-11-10 | 검증됨 (reviews/2026-11-10-판단보류-아파트비교.md, 전북대권 90~132㎡ 2건) |
| N-032 | 아파트 전용 40~132㎡ 월세 정제 행 수·연도별 행 수 | 전체 24,965 / 2021~2026: 3,175 / 4,769 / 4,311 / 4,451 / 3,970 / 4,289 | data/processed/valid_apartment_monthly_audit.json (`total_rows`·`by_year`) | src/jurent/data.py | 2026-11-10 | 검증됨 (reviews/2026-11-10-판단보류-아파트비교.md) |
| N-033 | 2024-11 이후 두 대학가 15~45㎡ 아파트 월세 건수 / 최다 단지 건수 / 휴먼시아 4개 단지 합계 (갱신 포함·제외) | 갱신 포함 245 / 98 / 104 · 갱신 제외 178 / 96 / 41 | outputs/compare/small_apartment_concentration.json | src/jurent/compare.py | 2026-11-10 | 검증됨 (reviews/2026-11-10-판단보류-후속수정.md) |
| N-034 | 두 대학가·집 종류·면적 구간의 최근 24개월 갱신 제외 환산 월세 사분위·보통 보증금·월세·건수(r 5%) | `campus_compare.csv` 18행의 `n`·중앙값·p25·p75·보증금·월세 열 참조 (표본 부족 4행) | outputs/compare/campus_compare.csv | src/jurent/area.py | 2026-11-12 | 검증됨 (reviews/2026-11-12-예산추천-대학가비교.md) |
| N-035 | 두 대학가의 원룸·투룸·빌라 25~35㎡ 연도별 환산 월세 중앙값 추이(r 5%) | `campus_price_trend.csv` 12행의 `n`·중앙값 열 참조 (2026은 1~10월) | outputs/compare/campus_price_trend.csv | src/jurent/area.py | 2026-11-12 | 검증됨 (reviews/2026-11-12-예산추천-대학가비교.md) |
| N-036 | 예시 예산 500/35만 원·최소 15㎡·저렴함 순의 대학가별 추천·제외 조합 | 효자동권 전체 21·추천 6·제외 5/4/6, 전북대권 전체 21·추천 7·제외 11/1/2 (표본 부족/쏠림/예산 안 25% 미만) | outputs/compare/budget_example.json | src/jurent/area.py | 2026-11-12 | 검증됨 (reviews/2026-11-12-예산추천-대학가비교.md) |
| N-037 | 법정동 경계 정류소 판정·확정 캠퍼스 정류소 기반 동→캠퍼스 직행(20정류소 이하) | 정류소 2,585개 중 완산·덕진 매핑 1,379개·경계 밖 1,206개; 캠퍼스 확정 전주대/전주비전대/전북대 12/9/17개(제외 4/0/12개); 통학권 동(캠퍼스 주변 제외) 41/30/57개; 134개 캠퍼스·동 조합 중 배차 일부 결측 106개. 직행 탑승 정류소별 최솟값의 중앙값·정류소 수 추가: 효자동3가→전북대 최소 5·중앙값 13.5·40곳, 서신동→전북대 2·5·17곳, 덕진동2가→전주대 6·14.5·10곳 | outputs/bus/stops_by_dong_audit.json; outputs/bus/campus_stops_candidates.csv; outputs/bus/commute_access.csv; outputs/bus/commute_access_audit.json; data/audit/bus_boarding_stops.csv; data/audit/bus_commute_examples.json | src/build_bus_access.py | 2026-11-13 | 검증됨 (reviews/2026-11-13-통학권-버스데이터.md; TAGO 배차 일부 결측 106조합은 자료 한계) |
| N-038 | 예시 예산 500/35만 원·최소 15㎡·저렴함 순, 통학권 포함·학교별 기본 선택 | 효자동권(전주대학교) 전체 223·추천 44·제외 136/22/21, 전북대권(전북대학교) 전체 280·추천 52·제외 178/25/25 (표본 부족/쏠림/예산 안 25% 미만) | outputs/compare/budget_commute_example.json | src/jurent/area.py | 2026-11-13 | 검증됨 (reviews/2026-11-13-통학권-예산추천-계약판단.md) |

> N-001~N-007은 Codex 심층 검증 결과에서 옮긴 값이다. 저장소 이전 후 Claude Code가 스크립트를 재실행해 검증 상태를 갱신한다. 출처 파일·스크립트 경로는 저장소 정리 후 실제 경로로 수정한다.

## 외부 인용

> 공식 기관 통계를 그대로 인용하는 값. 계산·가공 금지. 가공이 필요하면 원자료를 받아 위 표에서 코드로 산출.

| ID | 수치 | 값 | 기관·자료명 | URL | 기준 시점 | 조회일 |
|---|---|---|---|---|---|---|
| E-001 | 전국 확정일자 기준 월세 비중 | 2020 40.7% → 2025(1~7월) 61.9% — **원자료 재확인 필요** | 대법원 등기정보광장(세계일보 2025-08-17 보도) | https://www.segye.com/newsView/20250817504692 | 2020 / 2025(1~7월) | 2026-11-09 |
| E-002 | 대학 기숙사 수용률 | 전체 22.2%, 비수도권 25.5% — **2019년 기준, 대학알리미 최신값(T12)으로 대체 예정** | 국회입법조사처 NARS현안분석(2019) | https://dhnews.co.kr/news/view/179520548913559 | 2019년 | 2026-11-09 |
