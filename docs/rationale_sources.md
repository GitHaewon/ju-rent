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
- **확인 불가**: 공식 다운로드 사유 등록 단계에서 페이지 오류가 발생하여 파일을 확보하지 못했다. 재학생 수와 기숙사 수용 인원을 읽거나 대학별·연도별로 대조할 원본이 없으므로 `outputs/rationale/dorm_capacity.csv`를 만들지 않았다. 다른 경로로 우회 수집하지 않았다.
