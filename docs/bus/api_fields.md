# SPEC-005 PR-1 · T1 전주시 버스 API 확인

- 확인일: 2026-11-13
- 공식 서비스: [전주시 승강장 정보 서비스 GW](https://www.data.go.kr/data/15158979/openapi.do), [전주시 노선정보 서비스 GW](https://www.data.go.kr/data/15159001/openapi.do)
- 인증: `.env`의 `DATA_GO_KR_SERVICE_KEY`. 아래 원 응답과 호출 기록에는 키를 기록하지 않았다.
- 실제 데이터 API 호출: **6회**. 응답은 `data/raw/bus/`에 저장했으며 같은 파일이 있으면 재호출하지 않았다. 포털 문서 조회는 이 횟수에 넣지 않았다.

| 확인 항목 | 실제 응답 | 저장 파일 |
|---|---|---|
| 정류장 전체 목록 `bus_location2_stopnm_common` | `code=000`. `stopStandardid`, `stopId`, `stopKname`, `stopX`, `stopY`가 있다. 주소·법정동 필드는 없다. 학교명 검색에 필요한 다수의 한글 이름이 원 응답부터 `�`로 대체되어 있다. | `data/raw/bus/stops_all.xml` |
| 노선 전체 목록 `bus_location_all_common` | `code=000`. 목록의 `brtId`, `brtClass`만 채워지고 `brtStdid`, `brtDirection`, `brtMininterval`, `brtMaxinterval`, `brtNeedtime`, 첫차·막차는 빈 값이다. | `data/raw/bus/routes_all.xml` |
| 노선번호 조회 `bus_location1_common` | 2번과 119번을 확인했다. `brtStdid`, `brtDirection`, 첫차·막차는 채워지지만, 모든 조회 행의 `brtMininterval`, `brtMaxinterval`, `brtNeedtime`은 빈 값이다. | `data/raw/bus/route_2.xml`, `route_119.xml` |
| 노선별 정류장 `bus_location_busstop_list_common` | `brtStdid=305001153`의 `brsSeqno`, `stopStandardid`가 채워져 순서를 판별할 수 있다. 정류장 이름은 원 응답부터 깨져 있다. | `data/raw/bus/route_2_stops.xml` |
| 노선 상세 `bus_location_busstop_info_common` | 같은 노선에서 `brtMininTerval`, `brtMaxinTerval`은 빈 값, `brtNeedTime=0`이다. 유효한 게시 배차 간격·평균 소요시간으로 사용할 수 없다. 첫차·막차는 `brtFirstTime=550`, `brtLastTime=2250`으로 채워져 있다. | `data/raw/bus/route_2_info.xml` |

## 판정

T1의 필수 항목 중 **게시 배차 간격과 평균 소요시간을 실제 응답에서 얻을 수 없다.** 정류장 이름도 대체 문자로 손실되어 D-044의 학교명 기반 후보를 신뢰성 있게 추출할 수 없다. 명세의 중단 조건에 따라 T2(법정동 경계)·T3(캠퍼스 정류장 후보)·T4(직행 통학권 계산)는 시작하지 않았다. `docs/bus/campus_stops.md`의 후보 목록은 확인 불가다.

원 응답의 `code=000`은 API 요청 성공을 뜻할 뿐, 개별 필드의 유효성을 보장하지 않는다. `data/raw/bus/call_log.json`은 실제 호출 순서와 원 응답 파일명을 기록한다.

## TAGO 재확인 및 GW 정정 (2026-11-13)

- 공식 자료원: [국토교통부 TAGO 버스노선정보](https://www.data.go.kr/data/15098529/openapi.do), [버스정류소정보](https://www.data.go.kr/data/15098534/openapi.do). `data/raw/bus/tago/`의 XML은 HTTP `response.content` 바이트를 변환 없이 저장했다. 각 `.meta.json`에 Content-Type, XML 선언, SHA-256, 키를 제외한 요청 파라미터를 기록했다.
- **앞선 GW 기록 정정:** 위 표의 “한글 이름이 원 응답부터 손실” 및 그에 따른 후보 추출 불가 판단은 틀렸다. GW의 실제 헤더는 `text/xml; charset=utf-8`, XML 선언은 `encoding="UTF-8"`이며 원 바이트에 U+FFFD 대체 문자가 없다. 저장본을 XML로 파싱하면 한글 이름이 정상이다. 이전 `�` 표시는 Windows 콘솔의 `cp949` 출력과 도구의 UTF-8 해석 사이에서 생겼다. `data/raw/bus/tago/gw_stops_encoding_check.xml`과 같은 이름의 `.meta.json`으로 다시 확인했다. GW 배차 간격·평균 소요시간의 결측 판정은 그대로다.
- TAGO 도시코드 목록 `getCtyCodeList`: `전주시 → 35010`을 실제 응답에서 확인했다 (`city_codes.xml`).

| 오퍼레이션 | 실제 확인한 항목 | 저장본 |
|---|---|---|
| `BusSttnInfoInqireService/getSttnNoList` | 전주시 정류소의 `nodeid`, `nodenm`, `gpslati`, `gpslong`, `nodeno`가 채워진다. 주소·법정동 필드는 없다. 헤더 `application/xml`, XML 선언 UTF-8이며 한글 이름에 대체 문자 없이 정상 파싱된다. | `stops_city_35010.xml` |
| `BusRouteInfoInqireService/getRouteNoList` | `routeid`, `routeno`, `routetp`, `startnodenm`, `endnodenm`, 첫차·막차 필드가 채워진다. 같은 노선번호의 서로 다른 `routeid`는 기점·종점이 달라 방향별 운행을 구분할 수 있다. | `routes_city_35010.xml` |
| `BusRouteInfoInqireService/getRouteInfoIem` | 119번 `JUB305001618`에서 평일 `intervaltime=30`분, 첫차·막차를 확인했다. 101번 `JUB305000392`에서는 `intervaltime`이 응답에서 빠져 있다. 노선별 결측은 이후 계산에서 구분해야 한다. | `route_info_JUB305001618.xml`, `route_info_JUB305000392.xml` |
| `BusRouteInfoInqireService/getRouteAcctoThrghSttnList` | `routeid`, `nodeid`, `nodenm`, `nodeord`, 좌표가 채워지고 순서대로 나온다. 실제 응답에 선택 항목 `updowncd`는 없으므로 각 `routeid`의 기점·종점과 `nodeord` 순서로 학교 방향을 판정한다. | `route_stops_JUB305001618.xml` |
| `BusSttnInfoInqireService/getSttnThrghRouteList` | 정류소별 `routeid`, `routeno`, `startnodenm`, `endnodenm`이 채워진다. | `stop_routes_JUB305100650.xml` |

이 재확인에서 TAGO API **7회**, GW 인코딩 비교 **1회**를 호출했다. 이전 GW 조사 6회를 포함한 PR #14의 누적 데이터 API 호출은 **14회**다. 요청별 원 응답은 파일이 있으면 재호출하지 않으며 `data/raw/bus/tago/call_log.json`에 이번 호출을 기록했다. TAGO의 필수 좌표·이름·노선 순서·평일 배차 간격은 실제 응답에서 확인했으나 일부 노선은 간격이 없다.

### T2 진입 후 중단

TAGO 정류소 응답에는 법정동·지번 주소가 없다. 공식 [브이월드 행정구역 읍면동(법정동)](https://www.vworld.kr/dtmk/dtmk_ntads_s002.do?svcCde=MK&dsId=30603) 자료의 전북특별자치도 ZIP이 필요하다. 페이지의 해당 다운로드 버튼은 로그인 상태를 확인하므로 사람이 내려받아야 한다. 정확한 파일명과 배치 경로는 `docs/bus/boundary_source.md`에 기록했다. 명세에 따라 T2 산출과 T3·T4는 중단했다.
