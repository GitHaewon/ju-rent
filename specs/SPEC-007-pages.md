# SPEC-007 · 공개 사이트 (GitHub Pages) + README 정리

- 참조: D-005, D-026~D-031, D-032, D-033, D-045, D-051~D-054
- 목적: 누구나 링크 하나로 쓰는 공개 사이트를 GitHub Pages에 올린다. 주소는 **https://githaewon.github.io/ju-rent/**
- 제약: Pages는 정적 파일만 올릴 수 있어 FastAPI 서버와 OpenAI 키를 쓸 수 없다. 그래서 **검증된 Python 엔진을 브라우저(Pyodide)에서 그대로 실행**한다. 엔진을 TypeScript로 옮기지 않는다(검증된 결과가 갈라질 위험)
- 규칙: AGENTS.md 그대로. 엔진의 계산 로직, N-001~N-041, 기존 API 응답은 바꾸지 않는다. 계산을 바꿔야 할 일이 생기면 **멈추고 보고**

| PR | 브랜치 | 내용 | 고위험 |
|---|---|---|---|
| PR-1 | `feat/static-site` | 서비스 층 분리, 브라우저 실행, 결과 일치 검사, Pages 배포, README | **예** (판단 결과를 내는 실행 환경이 바뀜) |

## 결정 (DECISIONS.md 확정에 그대로 추가)
- `D-055 | 2026-11-21 | 공개 사이트는 GitHub Pages 정적 사이트(https://githaewon.github.io/ju-rent/). 서버가 없으므로 기존 Python 엔진을 브라우저의 Pyodide(Web Worker)에서 그대로 실행한다. 정적 결과는 같은 입력의 로컬 API 결과와 JSON이 완전히 같아야 배포한다 | 무료 공개, 검증된 엔진을 다시 짜지 않음 | 확정`
- `D-056 | 2026-11-21 | 공개 사이트에서는 AI 설명을 끄고 규칙 기반 설명(source=rule)만 보여준다. API 키는 정적 파일·빌드 산출물·Actions 로그에 넣지 않는다. 로컬 실행(API 모드)의 AI 설명은 그대로 | 정적 사이트는 키를 숨길 수 없음 | 확정`
- `D-057 | 2026-11-21 | 공개 사이트 데이터는 저장소에 커밋된 data/processed/current, outputs/bus, config/settings.toml만 쓴다. 갱신은 지금처럼 로컬에서 refresh_rentals 실행 → 커밋·머지하면 Actions가 다시 배포한다. data/raw는 배포하지 않는다 | 원본 재배포 금지(D-003 계열), 갱신 절차 하나로 유지 | 확정`

## 작업

| # | 작업 | 완료 기준 |
|---|---|---|
| T1 | 배차 간격 고정 파일 | `commute.planned_intervals_by_route()`가 지금 `data/raw/bus/`(커밋 제외)를 읽어서 배포 환경에서는 배차 간격이 사라진다. raw에서 `outputs/bus/route_intervals.csv`(노선 ID, 평일 배차 간격 분, 출처, 기준일)를 만드는 명령을 추가하고, `commute`는 이 파일만 읽는다. raw가 있는 지금 환경에서 `/api/meta`·`/api/budget`·`/api/compare` 결과가 main과 완전히 같아야 함 |
| T2 | 서비스 층 | `src/jurent/service.py`(웹 프레임워크 없음): `meta()`, `judge(dict)`, `explain_rule(dict)`, `budget(dict)`, `compare(rate_pct, school)`. 입력 검증 모델(pydantic)과 한국어 오류 메시지도 여기로 옮긴다(Pyodide는 pydantic 제공). `api/main.py`는 이 함수를 감싸기만 한다. 응답 필드·값·422 메시지 불변 |
| T3 | 무거운 import 정리 | `explanation.py`의 `openai`·`dotenv`를 AI 호출 함수 안으로 옮겨 `rule_explanation`은 표준 라이브러리만으로 import 가능. 서비스 층 import에 fastapi·uvicorn·openai·dotenv·pandas가 없어야 함(테스트로 확인) |
| T4 | 브라우저 묶음 | `python -m src.build_static` → `web/public/py/jurent_bundle.zip`(커밋 제외) + `bundle_manifest.json`(파일 목록·sha256). 서비스 실행에 필요한 `src/` 파이썬 파일, D-057의 데이터·설정만 같은 상대 경로로 담는다. `.env`, `data/raw/`, `outputs/` 중 bus 외 파일, `reviews/`가 들어가면 실패 |
| T5 | Web Worker | `web/src/backend.ts` 한 곳에서 호출. `VITE_JU_RENT_MODE=static`이면 Worker로, 아니면 지금처럼 `/api` fetch. Worker는 고정 버전 Pyodide(jsDelivr, 버전은 이 PR에서 최신 안정판으로 정해 D-055 근거 칸에 적기)를 읽고 numpy·pydantic을 불러 묶음을 풀고 `service`를 호출. 화면 컴포넌트는 `backend.ts`만 쓴다 |
| T6 | 정적 모드 화면 | ① 첫 방문 준비 중: 조건 패널은 바로 보이고 판단 카드 자리에 "계산 준비 중이에요. 처음 한 번만 10초쯤 걸려요" + 진행 표시. 준비되면 기존 첫 진입 모션 ② Pyodide를 못 받으면 "계산 도구를 불러오지 못했어요. 인터넷 연결을 확인하고 새로 고침해 주세요" ③ "AI 설명 듣기" 버튼 대신 규칙 설명을 바로 표시하고 아래 작게 "공개 사이트에서는 기본 설명을 보여드려요" ④ 나머지 화면·문구·모션은 API 모드와 같음 |
| T7 | 결과 일치 검사 (D-055) | `python -m src.static_parity`가 고정 입력 목록의 CPython `service` 결과를 `outputs/static/parity_expected.json`으로 저장. `web/scripts/static-parity.mjs`가 같은 묶음을 Node에서 같은 버전 `pyodide` npm 패키지로 돌려 **JSON 완전 일치** 비교(소수 반올림 허용 없음). 입력: meta, judge(대학가 2 × 집 종류 4, 통학권 동 2, 표본 부족 1, 판단 보류 1, 건축년도 있음 1, 환산율 3%·8% 각 1), explain_rule 2, budget(효자동권·전북대권 500/35 scope commute·campus, priority 4종 중 2), compare(학교 3), 422 입력 3 |
| T8 | 배포 | `.github/workflows/pages.yml`: main push·수동 실행. ① Python 3.12 `pip install -r requirements.txt`, `pytest -q`, `ruff check src tests app api` ② Node 24 `npm ci`, `npm test` ③ build_static → static_parity → `npm run build`(정적 모드, base `/ju-rent/`) ④ `actions/upload-pages-artifact` + `actions/deploy-pages`. 하나라도 실패하면 배포 안 함. `vite.config.ts`의 base는 환경 변수로(로컬 기본 `/`) |
| T9 | README | 아래 "README 고칠 내용" 그대로 |

### PR-1 테스트
- [ ] T1: raw 있는 환경에서 route_intervals.csv로 바꾼 뒤 meta·budget·compare가 main과 같음, raw 폴더를 숨겨도 같음
- [ ] T2: TestClient 응답 == `service` 함수 결과(T7 입력 전체), 422 메시지 동일
- [ ] T3: 서비스 층 import 목록 검사
- [ ] T4: 묶음에 금지 경로 없음, 키 문자열(`OPENAI_API_KEY=`, `serviceKey=` 등) 없음
- [ ] T7: static-parity 통과(로컬과 Actions 둘 다)
- [ ] Playwright: `vite preview`(정적 모드)로 기본 입력 판단·예산 탭·대학가 비교 탭 표시, 준비 중 화면, Pyodide 실패 화면 스크린샷(데스크톱·iPhone 14) `docs/design/screens/static_*`
- [ ] 기존 N-001~N-041·`outputs/` 불변, vitest, `npm run build`(API 모드·정적 모드 둘 다)

## README 고칠 내용

1. 제목 바로 아래에 추가:
```markdown
**▶ 바로 써 보기: https://githaewon.github.io/ju-rent/**
(설치 없이 브라우저에서 동작해요. 공개 사이트에서는 AI 설명 대신 기본 설명을 보여줍니다.)
```
2. "시작하기 > 계약 판단 화면 실행" 끝의 오래된 번호 목록 3줄(`.env.example`을 복사해… / `data/raw/`에 원본… / 분석 스크립트를…)은 삭제(위 문단과 중복·옛 내용)
3. "시작하기"에 "### 공개 사이트 배포" 짧은 절: main에 머지되면 Actions가 테스트·결과 일치 검사 후 자동 배포, 데이터 갱신은 refresh → 커밋·머지, 결과는 Actions 탭에서 확인
4. 파일 **맨 아래**에 그대로 추가(Pyodide 버전 칸만 T5에서 정한 값으로):

````markdown
## 개발 환경과 실행 방법

### 개발 환경
| 항목 | 버전 |
|---|---|
| 운영체제 | Windows |
| Python | 3.12.14 (uv로 만든 `.venv`) |
| Node.js / npm | 26.13.0 / 11.20.0 |
| 웹 | React 19, Vite 7, TypeScript 5.9, motion 12, Pretendard |
| API | FastAPI, uvicorn |
| 공개 사이트 | GitHub Pages + Pyodide ○○○ (브라우저에서 같은 Python 엔진 실행) |

### 필요한 것
- Python 3.12 이상 (3.12.14에서 개발·검증)
- Node.js 22.12 이상 (26.13.0에서 개발)
- Python 라이브러리 목록은 `requirements.txt`, 웹 라이브러리 목록은 `web/package.json`

### 설치 (저장소 폴더에서 한 줄)
```bash
pip install -r requirements.txt && npm --prefix web install
```
Windows PowerShell 5에서는 `&&` 대신 `;`를 쓰고, `npm`이 막히면 `npm.cmd`로 바꿔 실행한다.
```powershell
pip install -r requirements.txt; npm.cmd --prefix web install
```
가상환경을 쓰려면 먼저 `python -m venv .venv` 후 활성화한다(Windows `.venv\Scripts\activate`, macOS·Linux `source .venv/bin/activate`).

### 실행
| 터미널 | 명령 | 설명 |
|---|---|---|
| 1 | `python -m uvicorn api.main:app --port 8000` | 계산 API |
| 2 | `npm --prefix web run dev` | 웹 화면 → http://127.0.0.1:5173 |

AI 설명(선택): `.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`, `OPENAI_MODEL`을 채운다. 키가 없어도 계약 판단은 동작한다.

### 검사
```bash
pytest -q
ruff check src tests app api
npm --prefix web test
npm --prefix web run build
```
````

## 사람이 할 일 (J)
1. 저장소 공개 여부 결정(아래 Claude 안내 참고) → 공개 사이트를 쓰려면 public이거나 GitHub Pro(학생 팩 무료)
2. Settings → Pages → Build and deployment → Source를 **GitHub Actions**로
3. 머지 후 Actions 탭에서 배포 성공 확인 → 주소 열어 보기

## 범위 밖
- 사용자 의견 받기(다음 명세, 사이트 공개 후), 데이터 자동 갱신 예약 실행, 사용자 지정 도메인, 공개 사이트의 AI 설명(서버 필요)
