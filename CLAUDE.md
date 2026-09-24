# STEAL THE SIGN : KICE — 교재 제작 파이프라인

## 목표
수능 수학 교재(HTML) 제작 파이프라인 중 **AI가 필요 없는 부분을 CLI 스크립트로 만든다.**
거창한 앱·서버·GUI 금지. 단순한 Python 스크립트 + `run.py`. Windows·macOS·Linux 모두에서 같은 명령으로 실행되어야 한다.

교재의 목적: 테마별 **실전개념(스킬)을 드릴링**해서 그 테마는 무조건 맞히게 하는 자습용 교재. 해설은 과외받듯 이해되고 개념 보충이 되는 수준이어야 하며, 비효율적 단순계산 풀이를 지양한다.

## 역할 분담
- **AI(채팅)가 계속 맡음**: 입력 판독, 테마 분류, 유사·중복 판정, 선별, 창작문항, 해설 집필 → 결과를 `book.json`(내용만)으로 출력
- **스크립트가 맡음**: source 검증, book.json 규칙 검사, 정답 검산, 그림 렌더링, 수식 조판, 템플릿 채우기, 판면 점검, 최종 보고
- **AI API 호출 금지**: 스크립트는 Claude API 등 어떤 AI API도 호출하지 않는다(API 키·SDK 의존성 추가 금지). AI 작업은 모두 채팅 세션에서 사람이 진행하고, 스크립트는 그 결과(book.json)를 검사·조판만 한다.

## 폴더 구조
```
data/
  db.json              통합 기출 DB 208문항 (수학Ⅰ 81·수학Ⅱ 79·확통 48) ← 이미 준비됨
  solutions.json       자습용 풀이 + 테마 개념정리 ← 이미 준비됨
  themes.json          교재 테마 체계 28개와 기출 배정 ← 확정
  strategy_notes.json  실전 개념 (S01~S26, S12 없음, 수학Ⅰ·Ⅱ만)
  STS_template.html    판면 템플릿 (PAGE/REPEAT/OPTION 마커, [[슬롯]], data-slot 가짜 번호)
  config.json          고난도 번호 목록 등 설정
  pages/               원본 PDF 페이지 이미지 (그림 원본 참조용, 선택)
work/book.json         AI가 작성하는 교재 내용
out/                   결과물 (book.html, report.md, excluded.json 등)
schema/                book.schema.json 등
scripts/
vendor/katex/          로컬 KaTeX
```

### 기존 자산 (steal-the-sign 저장소 `claude/pdf-problem-db-merge-98r9as` 브랜치에서 가져옴)
| 새 경로 | 원본 | 비고 |
|---|---|---|
| `data/db.json` | `data/all.json` | 과목별 분할본 `m1.json`·`m2.json`·`prob.json`도 있음 |
| `data/solutions.json` | `data/solutions_all.json` | `{"themes": [...54], "problems": [...208]}` |
| `data/strategy_notes.json` | `tools/strategy_notes.json` | |
| 참고 | `data/README.md`, `solutions/SPEC.md`, `pilot/pilot_v2.json` | DB 스키마·해설 작성 규격·해설 모범 예시 |

## db.json 스키마 (확정)
```json
{
  "id": "M1-230911",                // 과목접두(M1=수학Ⅰ, M2=수학Ⅱ, PS=확통)-source.code
  "subject": "수학Ⅰ",
  "source": {"code": "230911", "year": 2023, "exam": "9월 모의평가", "number": 11, "points": 4,
             "label": "2022년 9월 고3 11번"},
  "question": "LaTeX 본문", "condition": "(가)(나)·<보기>·빈칸 과정 | null",
  "choices": ["5개"] | null, "answer": "2", "answer_value": "선택지 값",
  "figure": {"description": "그림 설명", "source_page": 5} | null,
  "theme": {"primary": "수학Ⅰ-01", "primary_name": "거듭제곱근", "links": ["수학Ⅰ-02"]},
  "first_judgment": "한 문장", "behavior": "계산|이해|추론|문제해결",
  "reasoning": ["조건의 식 번역", ...], "strategy_ids": ["S01"],
  "solution_ref": "PDF 해설 요약 (참고용, 교재 출력 금지)",
  "legacy": {"category": "원 PDF 소단원", "book_no": 1, "question_page": 1, "solution_page": 42},
  "check": {"answer_match": null, "excluded": false, "needs_review": []}
}
```
- `source.code`=`YYMMNN`, **학년도 기준**(2022년 11월 시행 = 2023학년도 수능 = `2311NN`). `label`은 원 PDF의 시행연도 표기.
- 수록 범위: 2022~2027학년도(시행 2021년 6월~2026년 6월) 평가원 6·9월·수능, 전부 4점. 21학년도 이하 없음.
- 번호 범위: 공통(수학Ⅰ·Ⅱ) 1~22, 확통 23~30. 수학Ⅰ·Ⅱ는 같은 시험의 번호 공간을 공유하므로 **code 충돌 검사 대상**.
- 정답: PDF 해설 페이지 정답을 옮긴 뒤 208문항 전부 재풀이로 검산 완료(불일치 0). `answer_match`는 기존 외부 DB가 없어 `null`.
- 그림: 텍스트 설명만 있음. 이미지는 `source_page` 페이지에서 잘라 쓰거나 `render_figs` 명세로 새로 그린다.
- `reasoning` 허용값(11): 조건의 식 번역, 경우 나누기, 그래프·도형 해석, 대칭성·주기성 활용, 단순화·특수화로 규칙성 찾기, 나열·역추적, 치환·보조함수 도입, 미지수 소거·연립, 정수 조건으로 후보 좁히기, 여사건·전체에서 빼기, 대응·모델링.

## themes.json — 교재 테마 체계 (확정)
- 원칙: 교과서 소단원이 아니라 **평가원이 요구하는 첫 판단**이 같은 문항끼리 묶는다. 첫 판단이 다르면 같은 단원이라도 나눈다.
- 28개 테마 = 수학Ⅰ 11(`M1-01`~`11`) · 수학Ⅱ 10(`M2-01`~`10`) · 확통 7(`PS-01`~`07`). 테마당 기출 5~10문항, 208문항이 정확히 한 테마에 한 번씩 배정됨.
- 필드: `id`, `subject`, `name`, `kice_intent`(평가원 의도), `signals`(문제에서 보이는 신호), `old_themes`(기존 64분류 id), `strategy_ids`, `problem_ids`(홈 테마 배정), `related_ids`(중복 사용 후보), `stats`.
- **기출 중복 사용 허용.** 한 문항을 여러 테마에서 쓸 수 있다. 우선 `problem_ids`와 `related_ids`에서 고르고, 그 밖의 문항은 이유를 적으면 쓸 수 있다(check_book 경고). 같은 테마 안에서는 중복 금지, 책 전체 사용 횟수는 `config.json` `reuse.max_uses` 이하.
- 다른 테마에서 다시 쓸 때는 해설은 solutions.json 것을 그대로 쓰고, book.json에 그 테마 관점의 한 줄(`reuse_note`: 이 테마에서 읽을 신호)을 붙인다.
- **교재의 테마는 themes.json 기준.** db.json·solutions.json의 `theme.primary`(`수학Ⅰ-01` 등)는 기존 64분류로, 개념정리·개념 id 출처로만 쓴다.
- 테마 도입부 개념정리는 `old_themes`에 속한 solutions.json 테마들의 `overview`·`core_concepts`·`decision_flow`를 합쳐 만든다. 개념 id(`{기존테마}-C{n}`)는 그대로 쓴다.
- 창작은 테마당 기출 수에 맞춰 채운다. 중복 사용으로 기출이 늘면 창작 부담이 줄어든다. 기출:창작 비율은 등장 횟수 기준.

## solutions.json 스키마 (확정)
- `themes[]`: `theme`, `theme_name`, `overview`, `core_concepts[{id, name, statement, why, when, strategy_ids, example?}]`, `decision_flow[]`, `problem_ids[]`. 54개 테마, 실전개념 177개. 개념 id = `{테마id}-C{n}` (예: `수학Ⅱ-08-C2`).
- `problems[]`: db 레코드 + `study_solution{concept_refs, guide, solutions[{title, steps[{label, body}]}], supplement, skill_point, answer}`.
- 풀이 구성: `guide`(조건 번역·꺼낼 개념) → `solutions`(풀이 1 = 스킬 풀이, 있으면 풀이 2 = 정석 비교용) → `supplement`(비효율 풀이 비교·일반화·흔한 실수) → `skill_point`(드릴 포인트 한 줄).
- 확통은 strategy notes가 없어 개념의 `strategy_ids`가 빈 배열.

## 흐름
```
validate_sources → excluded.json
[AI] book.json 작성
check_book → verify_answers → (오류 목록을 AI에 전달, 해당 항목만 수정) → 반복
render_figs → build → check_layout → report
```

## 스크립트
| 파일 | 역할 |
|---|---|
| validate_sources.py | 중복 id, 수학Ⅰ·Ⅱ 같은 code 충돌, 월 코드(06·09·11 외), 번호 범위(공통 1~22, 확통 23~30) 밖, strategy_notes `db_code_candidate`와 충돌, solutions.json 누락·정답 불일치·끊긴 `concept_refs`, themes.json 미배정·중복 배정 → `excluded.json` |
| check_book.py | book.json 규칙 검사(아래) |
| verify_answers.py | 문항별 `verify` 코드(SymPy 등) 실행 → 정답·숏컷·정석 답 일치 확인 |
| render_figs.py | 그림 명세 JSON → SVG (실제 함수로 그림) |
| tex.py | KaTeX 일괄 렌더링. Playwright 헤드리스 브라우저에 `vendor/katex/`의 로컬 KaTeX를 올려 처리 (Node 불필요, CDN 금지) |
| build.py | Jinja2 또는 마커 파싱으로 템플릿 채움. 쪽 번호·목차·정답표 자동 생성. 기출 본문·해설·테마 개념정리는 db.json·solutions.json에서 가져옴 |
| check_layout.py | Playwright로 A4(794×1123px) 넘침, `[[`·`]]` 잔존, 가짜 번호 잔존 검사. SOLUTION 넘치면 자동 분할 |
| report.py | 로그 집계 → report.md |
| run.py | 전체 실행. `python run.py` / `python run.py check` / `python run.py build` 처럼 단계 선택 |

## check_book 검사 항목
- 기출 id가 db.json에 존재하고 excluded.json에 없음
- 기출 정답 = DB 정답
- 테마마다 2~3 DAY 할애, 테마당 총 8~13문항(예제 포함, 기출+창작) / 기출:창작은 책 전체 기준 ≈ 7:3
- 창작: [3점], 객관식 5지선다, 단답형은 3자리 이하 자연수
- 기출: [4점], 22~27학년도
- 테마 id가 themes.json의 28개 안. 기출이 그 테마의 `problem_ids`·`related_ids` 밖이면 경고, 같은 테마 안 중복은 오류, 책 전체 사용 횟수 초과는 오류
- strategy id가 strategy_notes.json에 존재, 개념 참조(`{테마}-C{n}`)가 solutions.json에 존재
- 야구 용어 금지어 검사(코너 이름 제외): 초구, 타석, 구종, 안타, 삼진, 덕아웃, 배터리, 스트라이크 등
- 행동 영역(계산/이해/추론/문제해결) 분포 집계

## 해설 규칙
- **기출 해설**: solutions.json의 `study_solution`을 사용. 208문항 모두 작성·검산 완료.
  - 풀이 1이 스킬(숏컷) 풀이, 풀이 2가 있으면 정석 비교 풀이다.
  - 테마 도입부에는 themes.json `old_themes`에 해당하는 solutions.json 테마의 `overview`·`core_concepts`·`decision_flow`를 합쳐 싣고, `kice_intent`·`signals`를 출제 구조(STRATEGY)에 쓴다.
- **PDF 원문 해설은 교재에 싣지 않는다** (출판사 해설, 저작권). `solution_ref`는 참고·검산용.
- 새로 쓰는 해설은 `solutions/SPEC.md` 규격과 `pilot/pilot_v2.json` 수준을 따른다: 단순 계산 대신 스킬, 모든 단계에 근거, 개념 번호 참조.
- 고난도 번호(수학Ⅰ·Ⅱ: 14, 15, 21, 22 / 확통: 28, 30, `config.json`에서 수정)는 해설 분량·강조를 우선 배정한다.
- 창작문항 해설과 새로 추가하는 숏컷에는 `verify` 코드 필수. 기존 208문항은 재풀이 검산을 마쳐 `verify` 코드가 없으므로, verify_answers는 코드가 있는 항목만 실행하고 나머지는 DB 정답 일치만 확인한다.
- 숏컷·정석 답 불일치 시 `needs_review` 표시

## AI 출력 규칙 (book.json)
- HTML을 쓰지 않는다. 내용 + LaTeX만.
- 기출은 db.json id로만 참조 (본문·해설 복사 금지, build가 DB·solutions에서 가져옴)
- 그림은 SVG 대신 명세: `{"fn":"x^3-3x","domain":[-3,3],"points":[...],"shade":...}`
- 창작·숏컷에는 `verify` 코드 첨부

## 작업 방식
- 먼저 `data/`의 실제 파일(특히 db.json·solutions.json 필드, STS_template.html 마커 구조)을 읽고 확인한 뒤 구현. db·solutions 스키마는 위에서 확정됨.
- book.json 스키마를 가장 먼저 확정해 `schema/book.schema.json`으로 저장
- 구현 순서: validate_sources → book 스키마 + check_book → verify_answers → tex + build → render_figs → check_layout + report + run.py
- 각 스크립트는 샘플 book.json으로 바로 테스트
- 의존성: Python 3.10+, jinja2, sympy, numpy, playwright (`requirements.txt`로 관리). KaTeX는 `vendor/katex/`에 파일로 동봉
- 크로스플랫폼 규칙: 경로는 `pathlib`, 외부 명령은 `subprocess`에 리스트로 전달(셸 문법 금지), 파일 입출력은 `encoding="utf-8"` 명시, 셸 스크립트(.sh/.bat) 만들지 않음
- 사용자 응답은 간결하게
