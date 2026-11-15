# JU RENT API

`POST /api/budget`의 `scope` 기본값은 `"commute"`다. 대학가 동과 선택한 학교의 직행 통학권 동을 함께 추천한다. 학교를 생략하면 효자동권은 전주대학교, 전북대권은 전북대학교가 기본이다. 기존 대학가 동만 비교하려면 `"scope": "campus"`를 보낸다.

```json
{"campus":"효자동권","deposit":500,"monthly":35,"min_area":15,"scope":"commute","school":"전주대학교"}
```

`GET /api/meta`의 `commute_deal_counts_by_school`은 학교·집 종류·동별 최근 24개월(2024-11~2026-10) 새 계약·미기재 계약 건수다. 동네 선택 화면은 해당 집 종류 거래가 없으면 숨기고 30건 미만이면 거래가 적다고 표시한다. `POST /api/judge`에서 `dong`과 `school`을 주면 선택한 통학권 법정동 거래끼리 비교한다.

예산 카드의 캠퍼스 주변 대비 가격 차이는 같은 집 종류와 경과연수구간의 캠퍼스 주변 거래를 기준으로 계산한다. 기준 거래가 30건 미만이면 차이는 `null`이다.
