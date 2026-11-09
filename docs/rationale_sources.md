# PR-3 필요성 근거 자료와 확보 상태

조회일: 2026-11-09.

## T9·T10·T14: 국토교통부 실거래가 공개시스템

- 입력: `data/raw/`의 완산·덕진 전월세 CSV(2021~2025 전년, 2026년 1~10월). 원본 파일명·행 수·SHA-256은 `data/audit/manifest.json`에 있다.
- 산출: `src/analyze_rentals.py` → `outputs/rationale/monthly_share.csv`, `outputs/rationale/campus_trend.csv`, `data/audit/counts.json`의 `campus_areas`.
- 대학가 법정동은 D-017의 **대리범위**다. T9의 월세 비중은 공개된 계약 행 중 월세 행의 비중이며 대학생 인구나 현재 매물 비중이 아니다. 2026년은 부분 연도다.
- T9의 전주 전체 `상위 두 단지 제외`는 2026년 4월 덕진구 아파트 N-013 상위 두 단지의 행만 제외한 민감도 비교다. 원본 행을 삭제하거나 기존 N-001~N-014를 바꾸지 않는다.
- T14의 상위 주소는 **법정동+원본 도로명+원본 번지 문자열** 조합이다. 마스킹된 지번 문자열에 여러 건물이 합쳐질 수 있으므로 개별 건물 집중도로 해석할 수 없다.
- 실거래가 공개시스템 원본은 계약일 기준이고 신고·해제에 따라 수치가 달라질 수 있다. 외부 공개 시 신고일 기준 공식 통계를 사용하라는 원본 주의문도 함께 고려해야 한다.

## T11: KOSIS 20대 1인가구

- 공식 표: [국가데이터처 KOSIS 인구총조사 「성 및 연령별 1인가구 - 시군구」](https://kosis.kr/statisticsList/mass/mass_list.jsp?org_id=101&process=statHtml&tbl_id=DT_1PL1502&vw_cd=MT_ZTITLE), 표 ID `DT_1PL1502`.
- 공식 페이지의 연도별 CSV ZIP을 2026-11-09에 내려받아 `data/raw/kosis/`에 보존했다(커밋 제외). `src/build_single_households.py`가 전주시 코드 `35010`의 20~24세·25~29세를 합산했다. ZIP별 SHA-256·조회일은 `outputs/rationale/single_households_sources.json`, 결과는 `outputs/rationale/single_households.csv`다.
- 이 통계는 **20대 1인가구**이며 대학생·자취생 수로 대체할 수 없다. 제공된 최신 연도까지만 산출했다.

## T12: 대학알리미 재학생·기숙사 수용 인원

- 공식 [대학알리미 공시데이터 추이 다운로드](https://www.academyinfo.go.kr/main/main0830/main0830.do)에서 `14-마-1. 기숙사 수용 현황_대학_기숙사 수용률`과 전문대학 대응 파일을 확인했다. [대학알리미 지표 정의](https://m.academyinfo.go.kr/empty/search/keyIndicator.do)는 수용 가능 인원과 재학생 수의 기준을 설명한다.
- 사람이 공식 페이지에서 내려받아 `data/raw/academyinfo/`에 둔 대학·전문대학 XLSX를 `src/build_dorm_capacity.py`가 읽었다. 원본 파일명·SHA-256·처리일은 `outputs/rationale/dorm_capacity_sources.json`, 본교 3개 대학의 2021~2026 공시 값과 산출 차이는 `outputs/rationale/dorm_capacity.csv`에 있다. 다운로드 날짜는 원본에서 확인 불가하다.
- `재학생수`가 캠퍼스별인지 학교 전체인지 원본에서 구별할 수 없어 **학교 전체 기준일 수 있음**. `기숙사 밖 재학생 수`는 재학생 수에서 수용가능인원을 뺀 산술 차이이며, 자취생 수가 아니다.

## PR-4: 코드·동기간·민감도·신고 기준

- [국토교통부 아파트 전월세 API](https://www.data.go.kr/data/15126474/openapi.do)와 같은 실거래가 전월세 API의 `LAWD_CD`·`DEAL_YMD`로 2023-12·2024-02를 조회했다. `src/check_lawd_codes.py`의 코드별 API 건수와 보존 CSV 건수는 `outputs/audit/lawd_code_check.json`에 있다. 현재 API의 과거 코드 반환만으로 당시 법정동 코드 전환 시점은 확정할 수 없다.
- D-021의 1~10월 동기간 열은 `outputs/rationale/campus_trend.csv`에 추가했다. N-017의 기존 2026 연간 대비 열은 회귀 보존용이며, 부분 연도 증감 설명에는 새 동기간 열을 사용한다.
- D-022의 전 기간 두 단지 제외 행은 `outputs/rationale/monthly_share.csv`, 단지명+지번 및 연도별 제외 행 수는 `data/audit/counts.json`에 있다. 기존 2026년 4월 한정 제외 행도 N-016 보존을 위해 남겼다.
- D-023의 NO만 다른 완전 중복 행은 원본에서 제거하지 않았다. 민감도는 `outputs/rationale/duplicate_sensitivity.csv`에 유형·연도별 초과 행과 대학가별 유효 표본·월세 비중 원본/제거 시 값을 나란히 기록한다.
- 신고 기준 표는 `outputs/rationale/report_obligation.csv`에 있다. 금액 경계는 보증금 6,000만 원 초과 또는 월세 30만 원 초과, 제도 시행 전은 별도 구분했다. 근거: [국토교통부 2025-04-29 보도자료](https://www.molit.go.kr/USR/NEWS/dtl.jsp?id=95090898), [뉴시스 2025-04-28 기사](https://www.newsis.com/view/NISX20250428_0003155781). 금액 기준만 적용한 표이며 금액 변동 없는 갱신계약의 예외 여부는 원본으로 확인할 수 없다.
