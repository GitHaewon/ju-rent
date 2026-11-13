# SPEC-005 PR-1 · T2 법정동 경계 자료와 판정

- 공식 출처: [브이월드 오픈마켓 · 행정구역 읍면동(법정동)](https://www.vworld.kr/dtmk/dtmk_ntads_s002.do?svcCde=MK&dsId=30603) (`dsId=30603`). 법정 읍면동 경계 SHP 자료다.
- 사람이 제공한 **파일명**: `LSMD_ADM_SECT_UMD_전북특별자치도.zip` (2026-11 기준 자료).
- 저장 **경로**: `data/raw/boundary/LSMD_ADM_SECT_UMD_전북특별자치도.zip` (원본은 Git 제외).
- 근거: 공식 페이지의 해당 파일 다운로드 버튼은 로그인 여부(`menuFnc.loginYn`)를 확인하고, 로그인하지 않은 경우 로그인 안내를 띄운다. 현재 작업 환경에는 이 서비스의 인증 세션이 없다.
- SHA-256: `2ab22ba1ac558dc07e1308441122b2cc9d182c7bedd664fb9df7986b2d48e448` (`data/audit/manifest.json`).
- ZIP의 `.cpg`는 EUC-KR, `.prj`는 Korea 2000 / Central Belt 2010 (EPSG:5186)이다. DBF의 `EMD_CD`, `EMD_NM`을 읽고 **`EMD_CD` 앞 5자리가 52111·52113인 경계만** 선택했다. 같은 이름의 다른 시군 동은 코드로 제외한다.
- TAGO 정류소의 WGS84 경도·위도를 `.prj`의 투영 좌표계로 변환하고, 각 정류소 점을 포함하거나 경계선에 닿는 단일 법정동 다각형에 매핑했다. 일치하지 않으면 `outside_jeonju_boundary`, 둘 이상 일치하면 `ambiguous_boundary_overlap`으로 기록한다. 유효하지 않은 경계 다각형 1개는 보정했다.
- 결과: 정류소 2,585개 가운데 완산·덕진 법정동 매핑 1,379개, 경계 밖 1,206개, 중복 판정 0개. 판정 방법과 원자료 해시는 `outputs/bus/stops_by_dong_audit.json`, 개별 결과는 `outputs/bus/stops_by_dong.csv`에 있다. 이 수치는 `NUMBERS.md` N-037 **미검증**이다.

TAGO 정류소 목록에는 법정동 또는 지번 주소가 없어 이 경계를 사용했다. 캠퍼스 정류장과 통학권 동은 사람이 지도에서 확인하기 전까지 후보로 둔다.
