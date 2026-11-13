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
