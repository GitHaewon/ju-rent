# 전주시 버스 API 조사 (SPEC-001 T6, Q-007)

조사일: 2026-11-07. API 호출이나 버스 자료 수집은 하지 않았다.

## 공식 명세에서 확인한 항목

| 목적 | 공식 명세 | 확인한 요청·응답 | 판단 |
|---|---|---|---|
| 정류장 좌표 | [전주시: 선택 좌표 인근 정류장](https://openapi.jeonju.go.kr/user/apimng/openapi/detail.jeonju?apiOfferSid=33&apiRegSid=17&menuCd=DOM_000000702000000000&offerInst=1000000000000&pageIndex=1&postSearch=&searchCondition=&searchOfferInst=&serviceGroup=L) | `authApiKey`, `arg1`(x), `arg2`(y), `arg3`(최대 정류장 수); 응답 `stopStandardid`, `stopx`(경도), `stopy`(위도), `stopKname` | 좌표 제공 확인. 좌표계와 검색 반경·완전 목록 제공 여부는 확인 불가(해당 명세에 없음). |
| 경유 노선 | [전주시: 노선별 정류장 기반정보](https://openapi.jeonju.go.kr/user/apimng/openapi/detail.jeonju?apiOfferSid=33&apiRegSid=22&menuCd=DOM_000000702000000000&offerInst=1000000000000&pageIndex=1&postSearch=&searchCondition=&searchOfferInst=&serviceGroup=L) | `authApiKey`, `min`, `max`; 응답 `BRT_STDID`(노선ID), `BNODE_ID`(지점ID), `BRS_SEQNO`(정류장순번) | 노선·정류장 관계 제공 확인. 정류장 표준ID와 지점ID의 안정적인 연결은 확인 불가(명세만으로 동일 키 여부 불명). |
| 노선 경유 정류장 | [전주시: 노선번호 검색 후 운행경로](https://openapi.jeonju.go.kr/user/apimng/openapi/detail.jeonju?apiOfferSid=33&apiRegSid=2&menuCd=DOM_000000702009000000&offerInst=1000000000000&pageIndex=1&postSearch=&searchCondition=&searchOfferInst=&serviceGroup=L) | 노선 ID·번호·확장번호·인증키 요청; 응답 `stopStandardid`, `bnodeId`, 정류장 이름·순번 | 두 정류장 식별자 연결 후보. 실제 응답 대조 전에는 연결 성공을 단정할 수 없다. |
| 도착 정보 | [전주시: 특정 노선·정류장 도착 정보](https://openapi.jeonju.go.kr/user/apimng/openapi/detail.jeonju?apiOfferSid=33&apiRegSid=18&menuCd=DOM_000000702009000000&offerInst=1000000000000&pageIndex=1&postSearch=&searchCondition=&searchOfferInst=&serviceGroup=L) | 정류장ID·노선번호·분선ID·인증키 요청; 응답 `rTime`(도착예정시간), `rStop`(남은 정류장), `viaStopname` | 실시간 **예정 도착** 정보 확인. 실제 도착 시각이나 연속 관측 기록은 이 명세에 없어 실측 배차 간격 산출은 확인 불가. |

[공공데이터포털 노선정보 서비스 공식 페이지](https://www.data.go.kr/data/15159001/openapi.do?recommendDataYn=Y)는 노선별 경유 정류장, 점두·비점두시 배차 간격과 시간표 제공을 설명한다. 이는 **게시된 운행 계획**이며 실제 관측 배차 간격과 구분해야 한다. 이 페이지의 이용 요금은 무료, 개발계정 신청 가능 트래픽은 **일일 1,000회**로 표시된다. 운영계정 한도는 활용사례 등록 후 증설 신청 방식이며 고정 무료 상한은 **확인 불가**다. 다른 전주시 API(좌표·도착정보)에 이 한도가 동일하게 적용되는지는 **확인 불가**다. 각각의 활용신청 명세에서 확인해야 한다.

## 법정동 중심점 기준 노선 수 산출 제안

1. 공식 법정동 경계와 좌표계가 확인된 뒤 법정동별 중심점을 만든다. 중심점은 도보권이나 실제 캠퍼스 입구를 뜻하지 않는다.
2. 팀이 정한 거리 기준으로 중심점 주변 정류장을 찾는다. 인근 정류장 API의 반환 상한 때문에 누락이 없는지 확인한 뒤 정류장 표준ID를 모은다.
3. 정류장별 경유 노선ID를 연결해 **중복을 제거한 노선ID 수**를 센다. 방향·분선을 같은 노선으로 합칠지는 팀이 정해야 한다. 실제 API 응답으로 `stopStandardid`와 `bnodeId`의 연결을 검증한다.
4. 화면에는 거리 기준, 기준 시점, 정류장 수·노선 수, 좌표와 식별자 매칭 검증 상태를 함께 표시한다. 배차 간격은 게시 시간표인지 실측인지 별도 표시한다.

API 호출·응답 검증과 중심점 거리 기준 결정 전에는 노선 수나 실측 배차 간격을 산출하지 않는다.
