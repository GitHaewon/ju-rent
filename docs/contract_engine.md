# 계약 판단 엔진 (SPEC-002 PR-1)

## 재현

`data/raw/`의 국토교통부 전월세 CSV와 `data/audit/manifest.json`을 준비한 뒤 Windows 작업 폴더에서 `uv pip install --python .venv/Scripts/python.exe -r requirements.txt`, `.venv/Scripts/python.exe -m src.jurent.data`를 실행한다. 정제본은 `data/processed/valid_small_monthly.csv`, 행 수·해시·음수 경과연수 건수는 `data/processed/valid_small_monthly_audit.json`에 기록된다. 원본 CSV는 계속 커밋에서 제외한다.

`src.jurent.engine.judge(campus, housing_type, area, deposit, monthly, construction_year=None, rate_pct=None)`가 화면에서 사용할 JSON 형태의 dict를 반환한다. `campus`는 `효자동권` 또는 `전북대권`, `housing_type`은 `apartment`, `multifamily`, `detached_multiunit`, `officetel` 중 하나다. 면적은 ㎡, 보증금·월세는 만 원 단위다. 미리 만든 정제본이 필요하다.

## 판단 기준

- `src/analyze_rentals.py`의 D-011 유효 표본 필터와 D-017 대학가 매핑을 재사용한다. NO만 다른 완전 중복은 원본 그대로 두고 정제본의 `완전중복여부`는 같은 원본 조합에 속한 **모든 행**에 표시한다.
- 갱신 계약을 제외하고 신규·미기재를 포함한다. 같은 대학가·주택유형에서 최근 24개월, 면적 ±5㎡를 우선 적용한다. 30건 미만이면 ±10㎡, 이어서 기간 전체로 넓힌다. 끝까지 30건 미만이면 수치 판단 없이 `표본 부족`을 반환한다.
- 비교에는 같은 환산율을 입력 매물과 모든 거래에 적용한다. 기본 5.0%는 [한국은행 2026-10-22 통화정책방향](https://www.bok.or.kr/portal/bbs/P0000559/view.do?nttId=11065823)과 [주택임대차보호법 제7조의2](https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1031475571), [시행령 제9조](https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lspttninfSeq=130111)를 반영한 설정값이다. 법정 상한을 **비교 기준**으로 사용하며 시장 전환율이라고 해석하지 않는다.
- 백분위는 같은 환산 월세와 동점인 거래를 절반으로 센다. 25 정확히는 `보통`, 75 정확히도 `보통`, 90 정확히는 `비싼 편`으로 표시한다. 분위수는 NumPy `method="linear"`이다.
- 선택한 건축년도는 데이터 기준연도 2026에서 빼서 D-018 경과연수구간을 정한다. 각 과거 거래의 구간은 그 계약연도와 건축년도의 차이로 정한다. 해당 구간이 30건 미만이면 별도로 `표본 부족`이다. 원본에서 건축년도가 계약연도보다 뒤인 행은 D-018 산식에 따라 현재 `5년 미만`이며 처리 방식은 Q-010에서 결정해야 한다.
- 결과에는 관리비 미포함, 대학가 법정동의 대리범위, 과거 계약 기준, 최근 신고 미반영 가능성을 항상 경고한다. 정제본은 현재 매물·호가가 아니다.

## 범위

이 PR은 데이터 레이어와 판단 엔진까지만 제공한다. Streamlit 화면과 규칙 기반·OpenAI 설명은 PR-2 범위다.
