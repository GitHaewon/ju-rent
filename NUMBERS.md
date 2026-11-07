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
| N-010 | 완산·덕진 2026-01~10 전월세 공개 행 수 (부분 연도) | 15,217 | data/audit/counts.json (`year_2026.total`) | src/analyze_rentals.py | 2026-11-07 | 미검증 |
| N-011 | 효자동2·3가 2026-01~10 소형 월세 유효 표본 (부분 연도) | 1,318 | data/audit/counts.json (`year_2026.analytic`) | src/analyze_rentals.py | 2026-11-07 | 미검증 |
| N-012 | 유효 표본 연도별 계약구분 (신규 / 갱신 / 미기재, 2021→2026) | 231/3/687 · 452/19/652 · 509/20/515 · 1,035/60/124 · 1,343/60/89 · 1,173/52/93 | data/audit/counts.json (`contract_by_year`) | src/analyze_rentals.py | 2026-11-07 | 미검증 |
| N-013 | 덕진구 아파트 2026-04 단지 집중 (전체 / 상위 단지 / 상위 두 단지) | 1,780 / 794 (44.6%) / 1,500 (84.3%) | data/audit/counts.json (`apartment_deokjin_2026_april`) | src/analyze_rentals.py | 2026-11-07 | 미검증 |
| N-014 | 대학가 후보 법정동별 연도·주택유형별 유효 표본 | 각 행의 `유효_표본_수`·주택유형 열 참조 | outputs/campus_dong_candidates.csv | src/analyze_rentals.py | 2026-11-07 | 미검증 |

> N-001~N-007은 Codex 심층 검증 결과에서 옮긴 값이다. 저장소 이전 후 Claude Code가 스크립트를 재실행해 검증 상태를 갱신한다. 출처 파일·스크립트 경로는 저장소 정리 후 실제 경로로 수정한다.
