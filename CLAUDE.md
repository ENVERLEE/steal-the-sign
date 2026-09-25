# STEAL THE SIGN : KICE — 교재 제작 파이프라인

## 목표
수능 수학 교재(HTML) 제작 파이프라인 중 **AI가 필요 없는 부분을 CLI 스크립트로 만든다.**
거창한 앱·서버·GUI 금지. 단순한 Python 스크립트 + `run.py`. Windows·macOS·Linux 모두에서 같은 명령으로 실행된다.

교재의 목적: 테마별 **실전개념(스킬)을 드릴링**해서 그 테마는 무조건 맞히게 하는 자습용 교재. 해설은 과외받듯 이해되고 개념 보충이 되는 수준이어야 하며, 비효율적 단순계산 풀이를 지양한다.

## 역할 분담
- **AI(채팅)**: 올린 교재 PDF 판독(OCR)·테마 분류·유사 기출 선정·해설, 창작문항, 교재 글(개념·비유·분석·오답 진단), 그림 명세 → `work/source/`(교재 판독), `work/created/`(창작 문제은행), `work/book.json`(교재 구성)
- **스크립트**: 원천 검증, 창작 검문, book.json 규칙 검사, 정답 검산, 그림 렌더링, 수식 조판, 템플릿 채우기, 판면 점검, 보고서
- **사람 승인 단계 없음.** 스크립트 검문을 통과한 창작(`verified`)은 바로 교재에 쓸 수 있다.
- **AI API 호출 금지**: 스크립트는 Claude API 등 어떤 AI API도 호출하지 않는다(API 키·SDK 의존성 추가 금지). AI 작업은 모두 채팅 세션에서 하고, 스크립트는 그 결과를 검사·조판만 한다.

## 실행
```
pip install -r requirements.txt
python -m playwright install chromium        # 처음 한 번 (브라우저가 이미 있으면 생략 가능)

python run.py pages --pdf 교재.pdf --id KB1   # 교재 PDF → work/source/KB1/pages/p001.png·p001.txt (판독용)
python run.py source          # 교재 판독 검사 + 큐레이션 초안 → out/curation.md, out/plan.json
python run.py created         # 창작 문제은행 검문만
python run.py                 # 전체: validate → created → source → check → verify → figs → build → layout → pdf → report
python run.py check           # 검사만 (조판 없이)
python run.py build           # 조판만: figs → build → layout → pdf → report
python run.py <단계>          # validate | created | check | verify | figs | layout | pdf | report
  --book PATH --created DIR --source DIR --out DIR   다른 책·문제은행·교재 판독·출력 폴더
  --recheck                             창작·교재 전체 재검사
  --force                               검사 오류가 있어도 조판
python -m unittest discover tests       # 테스트
```
- 결과: `out/book.html`(한 파일, KaTeX 글꼴 내장), `out/book.pdf`(A4, 쪽마다 한 장), `out/report.md`, `out/excluded.json`, `out/pages.json`, `out/logs/*.json`
- 검사 단계(validate·created·source·check·verify)에 오류가 있으면 조판하지 않는다(`--force` 제외). 오류가 하나라도 있으면 종료 코드 1.
- 판면 측정은 템플릿의 웹 글꼴(Google Fonts)을 불러와 잰다. 글꼴을 못 불러오면 경고를 남기고 대체 글꼴로 잰다. 그 밖의 외부 요청(스크립트 CDN 등)은 모두 막는다.

## AI 작업 순서 (채팅) — 교재 PDF를 받았을 때
교재의 문제가 **예제**가 되고, 테마별로 유사 기출·창작을 붙여 드릴 교재를 만든다.
1. **쪽 변환**: `python run.py pages --pdf <올린 파일> --id <교재id>` → `work/source/<교재id>/pages/p###.png`(+텍스트 층).
2. **판독·분류**: 쪽 이미지를 보고 모든 문제를 `work/source/<교재id>.json`에 적는다(아래 '교재 판독 파일'). 문항마다 테마(28개 중 하나), 첫 판단, 유사 기출(`similar`), 해설(새로 씀), `verify`. 한 번에 10~20문항씩 쓰고 `python run.py source`로 검사 → 오류만 고친다.
3. **큐레이션**: `python run.py source`가 만든 `out/curation.md`·`out/plan.json`을 본다. 테마마다 2~3 DAY, 교재 문항 2~3개가 예제, 나머지 교재 문항·유사 기출·창작이 연습. '창작 N개 더 필요'가 뜨면 그 테마 창작을 **4문항 이하**로 `work/created/{테마}/{id}.json`에 쓰고 `python run.py created` → 통과할 때까지 → 다시 `python run.py source`.
4. **교재 구성**: plan.json의 문항 배정을 `work/book.json`에 옮기고 글(개념·비유·THE SIGN·분석·REPLAY·다음 챕터)을 쓴다. 한 권(WEEK)에 담을 테마를 정해 권을 나눈다. 그림 있는 기출은 `figures` 명세.
5. `python run.py` → `out/report.md`의 **'AI에게 전달할 수정 목록'**만 고친다 → 오류 0이면 `out/book.html`(과 `out/book.pdf`)을 사용자에게 보낸다.

교재 PDF 없이 만들 때는 3~5만 한다(예제도 기출·창작에서 고른다).

## 폴더 구조
```
run.py                 파이프라인 실행
requirements.txt
data/
  db.json              통합 기출 DB 208문항 (수학Ⅰ 81·수학Ⅱ 79·확통 48). m1/m2/prob.json은 과목별 분할본
  solutions.json       자습용 풀이 + 기존 64분류 테마 개념정리 (실전개념 177개)
  themes.json          교재 테마 체계 28개와 기출 배정 (확정)
  strategy_notes.json  실전 개념 (S01~S26, S12 없음, 수학Ⅰ·Ⅱ만)
  STS_template.html    판면 템플릿 (PAGE/REPEAT/OPTION 마커, [[슬롯]], data-slot 가짜 번호) — 수정하지 않는다
  config.json          설정 (고난도 번호, 테마 구성, 창작 검문 기준, 금지어, 경로)
work/
  book.json            AI가 쓰는 교재 한 권(WEEK) 구성
  created/{테마}/      창작 문제은행 (문항당 JSON 1개)
  source/{교재id}.json 올린 교재의 판독·분류 결과 (문항 id T-{교재id}-NNN)
  source/{교재id}/pages/  PDF 쪽 이미지·텍스트 (git 제외)
schema/                book · created · source · figure 스키마 (JSON Schema 2020-12)
scripts/               단계별 모듈 (아래 표)
samples/               샘플 book.sample.json + 창작 2문항 + 가상 교재(SMP) 3문항 (테스트용)
tests/                 unittest
vendor/katex/          로컬 KaTeX 0.18.9 (CDN 금지)
out/                   결과물 (git 제외)
참고: data/README.md(DB 스키마), solutions/SPEC.md(해설 작성 규격), pilot/pilot_v2.json(해설 모범)
```

## 스크립트
| 파일 | 역할 |
|---|---|
| `validate_sources.py` | id·code·월(06·09·11)·번호 범위(공통 1~22, 확통 23~30)·학년도(22~27)·배점, 수학Ⅰ·Ⅱ 같은 code 충돌, 선지·정답 형식, strategy_notes 예시(`db_code_candidate`) 대조, solutions.json 누락·정답 불일치·끊긴 `concept_refs`, themes.json 미배정·중복·끊긴 참조, **제어문자(깨진 LaTeX 이스케이프)**, **전체 수식 KaTeX 조판 오류** → `out/excluded.json` |
| `pdf_pages.py` | 교재 PDF → 쪽 PNG·텍스트 층 (pypdfium2). 판독은 AI가 이미지를 보고 한다 |
| `check_source.py` | 교재 판독 파일 검사: 스키마, id·쪽, 테마·과목, 개념·유사 기출 참조, `$` 짝, 제어문자(깨진 LaTeX), 그림 명세, `verify` 검산 → 문항별 `status: verified` |
| `curate.py` | 교재 문항 → 테마별 DAY·예제·연습·SCOUTING 배정 초안 → `out/curation.md`, `out/plan.json` |
| `check_created.py` | 창작 문제은행 검문(아래) → 통과 시 `status: verified`, 결과는 레코드 `review`에 기록 |
| `check_book.py` | book.json 규칙 검사(아래) |
| `verify_answers.py` | 기출: DB 정답 = 풀이 정답 = 정답 선지 값. 새 숏컷(`notes[ref].verify`)의 `skill()` 검산. 창작: `skill`·`standard`·`unique` 재실행 |
| `render_figs.py` | 그림 명세 → SVG (sympy·numpy로 실제 함수를 계산해 그림). `out/figs/`에 캐시 |
| `tex.py` | KaTeX 일괄 조판 (Playwright에 `vendor/katex` 로드, 결과 캐시 `out/.cache/tex.json`). 글꼴은 woff2 base64로 CSS에 내장 |
| `template.py` | STS_template.html → 페이지별 Jinja2 템플릿. 슬롯 매핑이 빠지면 오류(템플릿이 바뀌면 `SLOTS`·`REPEATS`·`OPTIONS` 수정) |
| `build.py` | 모델 구성 → 수식 조판 → **실제 A4 판면을 재면서** 목차·REPLAY·정답표·해설을 페이지로 나눔(해설은 한 장에 `config.json` `solution.per_page_max`문항까지) → 쪽 번호(표지 001)·목차 쪽수·정답표 자동 → `out/book.html` |
| `export_pdf.py` | 결과 HTML을 템플릿 인쇄 CSS 그대로 Chromium으로 인쇄 → `out/book.pdf`. 쪽 수 = HTML `.page` 수, A4 크기 확인 |
| `check_layout.py` | 결과 HTML을 열어 페이지마다 794×1123 크기, 넘침, `[[`·`]]`, 가짜 번호, KaTeX 오류, 수식 기호 노출(`\frac`·`$`), 순서·쪽 번호 연속 검사 |
| `report.py` | 로그 → `out/report.md` (요약, AI 수정 목록, 교재 구성·비율·행동 영역·난도, 문제은행 현황, 판면) |
| `mathval.py` · `verify_runner.py` | LaTeX 정답 → sympy 비교, verify 코드를 별도 프로세스에서 시간 제한 실행 |
| `common.py` · `schemas.py` | 설정·경로·로그·브라우저 실행, 스키마 검증 |

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
- `source.code`=`YYMMNN`, **학년도 기준**(2022년 11월 시행 = 2023학년도 수능 = `2311NN`). `label`은 원 PDF의 시행연도 표기. `exam`은 `6월 모의평가`·`9월 모의평가`·`대학수학능력시험`.
- 수록 범위: 2022~2027학년도(시행 2021년 6월~2026년 6월) 평가원 6·9월·수능, 전부 4점.
- 번호 범위: 공통(수학Ⅰ·Ⅱ) 1~22, 확통 23~30. 수학Ⅰ·Ⅱ는 같은 시험의 번호 공간을 공유하므로 code 충돌 검사 대상.
- 텍스트는 `$…$` 수식, `\\`·`\n` 줄바꿈. **선지(`choices`)는 `$` 없이 LaTeX만** 적혀 있다(`\frac{5}{3}`) — build가 수식으로 조판. ㄱ·ㄴ·ㄷ 선지는 글자.
- 정답: 208문항 전부 재풀이 검산 완료(불일치 0).
- 그림: 텍스트 설명만 있다(46문항). 그 기출을 쓰면 book.json `figures`에 그림 명세를 반드시 쓴다.
- `reasoning` 허용값(11): 조건의 식 번역, 경우 나누기, 그래프·도형 해석, 대칭성·주기성 활용, 단순화·특수화로 규칙성 찾기, 나열·역추적, 치환·보조함수 도입, 미지수 소거·연립, 정수 조건으로 후보 좁히기, 여사건·전체에서 빼기, 대응·모델링.

## themes.json — 교재 테마 체계 (확정)
- 원칙: 교과서 소단원이 아니라 **평가원이 요구하는 첫 판단**이 같은 문항끼리 묶는다. 첫 판단이 다르면 같은 단원이라도 나눈다.
- 28개 = 수학Ⅰ 11(`M1-01`~`11`) · 수학Ⅱ 10(`M2-01`~`10`) · 확통 7(`PS-01`~`07`). 208문항이 홈 테마 하나에 한 번씩 배정(테마당 5~10).
- 필드: `id`, `subject`, `name`, `kice_intent`(평가원 의도), `signals`(문제에서 보이는 신호), `old_themes`(기존 64분류 id), `strategy_ids`, `problem_ids`(홈 배정), `related_ids`(중복 사용 후보), `stats`.
- **교재의 테마는 themes.json 기준.** db·solutions의 `theme.primary`(`수학Ⅰ-01` 등)는 기존 64분류로 개념정리·개념 id 출처로만 쓴다. 개념 id `{기존테마}-C{n}`은 그대로 쓴다.
- **기출 중복 사용 허용.** 우선 `problem_ids`·`related_ids`에서 고른다. 그 밖의 기출은 `practice[].reason`을 적으면 쓸 수 있다(경고). 같은 DAY 안 중복 금지, 책 전체 사용 `reuse.max_uses`(3)회 이하. 홈 테마가 아닌 곳에서 쓰면 `reuse_note`(이 테마에서 읽을 신호 한 줄) 필수.

## solutions.json 스키마 (확정)
- `themes[]`: `theme`, `theme_name`, `overview`, `core_concepts[{id, name, statement, why, when, strategy_ids, example?}]`, `decision_flow[]`, `problem_ids[]`. 기존 64분류 중 54개 테마.
- `problems[]`: db 레코드 + `study_solution{concept_refs, guide, solutions[{title, steps[{label, body}]}], supplement, skill_point, answer}`.
- 풀이 구성: `guide`(조건 번역·꺼낼 개념) → `solutions`(풀이 1 = 스킬 풀이, 있으면 풀이 2 = 정석 비교용) → `supplement`(비효율 풀이 비교·일반화·흔한 실수) → `skill_point`(드릴 포인트 한 줄).
- 해설 본문의 `(수학Ⅰ-02-C1)` 같은 내부 개념 id는 build가 지우거나 「개념 이름」으로 바꿔 싣는다.

## 창작 문항 — 문제은행과 품질 검문
창작 비율은 고정하지 않는다. **검문을 통과한 창작만** 교재에 들어가며, 비율은 그 결과로 정해진다(report에 표시).
테마 구성 제약: 테마당 기출 등장 5개 이상, 창작 비중 50% 이하(`config.json` `composition`).

1. **기출 변형이 기본**: `origin.type`=`variant`면 `parent_id`(db id)와 `variation`(수치 변형·조건 변형·역방향·일반화·결합) 필수. 원본의 문체·조건 구조·테마 의도를 유지. `original`(신작)은 테마당 1개까지.
2. **스크립트 검문** (`check_created.py`)
   - 스키마, [3점], 객관식 5지선다(`choice_values`·`answer_value` 필수, 선지 값 서로 다름) 또는 단답형 1~999 자연수, 금지어, `$` 짝, 개념·strategy id 존재, 파일 위치 `work/created/{테마}/{id}.json`
   - 정답 검산: `verify`의 `skill()`과 `standard()`가 둘 다 정답 값
   - 유일성: `unique()`가 조건을 만족하는 답을 전수·기호 계산으로 모두 구해 정답 하나만 돌려줘야 한다
   - 오답 선지: 객관식이면 오답 4개 모두 `distractors[{choice, error_path}]`
   - 스킬 적중: `target.concept_ids`(테마의 기존 개념을 하나 이상 겨냥) · `target.first_judgment` 필수, 풀이 1(스킬)·풀이 2(정석) 둘 다 필수, 풀이 1 분량 ≤ 풀이 2의 70%
   - 원본 대비 본문 유사도 90% 이상이면 경고(수치만 바꾼 복제 의심), 그림 명세 렌더링 오류
3. **상태**: `draft`(작성·미통과) → `verified`(통과). **AI는 `status`·`review`를 쓰지 않는다.** 내용 해시를 `review.hash`에 저장하고, 통과 후 내용이 바뀌면 다시 검사한다.
4. **천천히 쌓기**: 테마당 검사 대기(미통과) 문항이 4개를 넘으면 id 순으로 앞의 4개만 검사하고 나머지는 막는다. 통과한 창작은 다른 권·테마에서도 재사용(기출과 같은 `reuse` 규칙).

### 창작 레코드 (`schema/created.schema.json`)
```json
{
  "id": "C-M1-01-001", "theme": "M1-01",
  "origin": {"type": "variant", "parent_id": "M1-220621", "variation": "조건 변형"},
  "target": {"concept_ids": ["수학Ⅰ-01-C1"], "strategy_ids": ["S01"], "first_judgment": "한 문장"},
  "difficulty": "기본 적용|조건 변형|복합 사고|고난도", "behavior": "계산|이해|추론|문제해결",
  "question": "$LaTeX$ 본문", "condition": null,
  "choices": ["$3$", "$4$", "$5$", "$6$", "$7$"] | null,
  "choice_values": ["3", "4", "5", "6", "7"],           // 객관식: 선지의 sympy 값
  "answer": "2", "answer_value": "4",                  // 객관식: 번호 + 값 / 단답형: 같은 수
  "distractors": [{"choice": 1, "error_path": "이 값이 나오는 오답 경로"}],
  "figure": null,                                      // 그림 명세
  "solution": {"concept_refs": [], "guide": "",
               "solutions": [{"title": "풀이 1 · 스킬", "steps": [{"label": "", "body": ""}]},
                             {"title": "풀이 2 · 정석", "steps": []}],
               "supplement": "", "skill_point": ""},
  "verify": "def skill(): ...\ndef standard(): ...\ndef unique(): return [...]"
}
```
- `verify`: sympy(이름 그대로, `sp`)·numpy(`np`)·`math`·`itertools`·`Fraction` 사용 가능, `print` 금지, 30초 제한. 값은 sympy 식(`Rational(9,7)*pi`)이나 정수로 돌려준다.
- 창작 문항은 교재에 `STEAL THE SIGN 창작` [3점]으로 찍힌다. 샘플: `samples/created/M1-01/`.

## 교재 판독 파일 — `work/source/{교재id}.json` (`schema/source.schema.json`)
```json
{"book": {"id": "KB1", "title": "교재 이름", "pdf": "원본.pdf"},
 "problems": [{
   "id": "T-KB1-001", "page": 12, "number": "3", "subject": "수학Ⅰ", "theme": "M1-01",
   "question": "$LaTeX$ 본문 (교재 원문 그대로)", "condition": null,
   "choices": ["$-5$", "$-1$", "$1$", "$5$", "$7$"] | null,
   "answer": "2", "answer_value": "-1", "answer_source": "교재 정답|AI 풀이", "points": 3,
   "figure": 그림 명세 | null, "figure_note": "그림 명세를 못 쓸 때 메모",
   "first_judgment": "한 문장", "behavior": "계산|이해|추론|문제해결", "difficulty": "기본 적용|…",
   "similar": ["M1-230911", ...],                       // 판단 구조가 같은 기출, 가까운 순
   "solution": {"concept_refs": [], "guide": "", "solutions": [{"title": "풀이 1 · 스킬", "steps": []}], "supplement": "", "skill_point": ""},
   "verify": "def skill(): ...  (standard()·unique()는 선택)"
 }]}
```
- 판독은 원문 그대로(수식은 `$…$`, 선지는 `$` 포함). 교재 번호·쪽을 그대로 적는다. 교재 출처는 `{교재 이름} {쪽}쪽 {번호}번`으로 찍힌다.
- **교재 해설은 옮기지 않는다.** 해설은 AI가 새로 쓴다(풀이 1 = 스킬, 있으면 풀이 2 = 정석). `verify`의 `skill()`은 필수, 정답지가 없어 `answer_source: AI 풀이`면 `standard()`도 쓴다.
- 테마는 themes.json의 `kice_intent`·`signals` 기준으로, `concept_refs`는 그 테마 `old_themes`의 개념에서 고른다. `similar`는 그 테마 `problem_ids`·`related_ids`에서 우선.
- 교재 문항은 테마당 최대 8개(기출 5개 자리 확보)까지 한 테마에 넣는다. 넘치면 큐레이션이 다음 권·다른 테마로 돌리라고 알린다.
- 저작권: 교재 원문을 실은 결과물은 수업·개인용으로 쓴다.

## book.json — 교재 한 권 (`schema/book.schema.json`)
HTML을 쓰지 않는다. 텍스트 + `$LaTeX$`만(줄바꿈 `\n`). 문항은 **id로만** 참조한다(기출 db id, 창작 `C-…`, 교재 `T-…`). 본문·정답·해설은 build가 가져온다.
```
{ "week", "total_weeks", "year_label": "2027학년도", "subject_label": "수학Ⅰ",
  "figures": {"M2-231110": 그림 명세, ...},          // 그림 있는 기출을 쓰면 필수
  "days": [{
    "day": 1, "theme": "M1-01", "title": "챕터 제목(24자 이하)",
    "concept":  {"core", "figures": [그림 명세+caption, 최대 2], "analogy", "analogy_limit", "map": [{"k", "v"}]},
    "strategy": {"structure"?, "figure"?, "concept_ids": ["수학Ⅰ-01-C1", ...], "tools"?: [{"name", "body"}]},
    "first_pitch": {"signal", "ref", "type", "reuse_note"?},
    "sign_reading": {"hint", "analysis", "points": [2~4], "verdict", "scouting": [{"ref", "note"}] (1~2)},
    "practice": [{"ref", "difficulty", "reuse_note"?, "reason"?}],
    "replay": [{"no", "wrong", "stuck", "fix"}],
    "sign_book": {"rows"?: [{"no", "signal", "method"}], "next"},
    "notes"?: {"<ref>": {"tip"?, "error"?, "shortcut"?, "verify"?}}
  }]}
```
- 문항 번호는 DAY마다 예제 1, 연습 2부터. `replay.no`·`sign_book.rows.no`는 이 번호.
- **build가 자동으로 채우는 것**: 목차, 쪽 번호, 정답표, DUGOUT NOTE, STRATEGY 출제 구조(비우면 `kice_intent`+`signals`)·실전 개념 행(`concept_ids` → 이름·내용·쓰는 때), SIGN BOOK 행(없는 번호는 `first_judgment`·개념 이름), 해설지(숏컷 = 조건 번역 + 풀이 1, 정석 = 풀이 2, 실전 개념 = 개념 이름 — skill_point, 오답 첨삭 = supplement). `notes`로 덮어쓴다(`shortcut`은 `verify` 필수).
- 샘플: `samples/book.sample.json` (M1-01, 2 DAY, 10문항).

## 그림 명세 (`schema/figure.schema.json`)
```json
{"fns": [{"expr": "x**3-3*x", "domain": [-2, 2], "label": "y=f(x)", "style": "main|sub|dash|red|red-dash"}],
 "x": [-3, 3], "y": [-3, 3], "equal": false,
 "points": [{"x": 1, "y": "-2", "label": "A", "pos": "ne", "guides": true, "style": "dot|open|red"}],
 "hlines": [{"y": 2, "label": "y=k"}], "vlines": [], "segments": [{"from": [0, 0], "to": [1, 1]}],
 "polygons": [{"pts": [[0,0],[4,0],[1,3]], "style": "fill"}], "circles": [{"c": [0, 0], "r": 2}],
 "param": [{"x": "cos(t)", "y": "sin(t)", "t": [0, "2*pi"]}],
 "shade": [{"upper": "x**3-3*x", "lower": "0", "from": -1, "to": 0}],
 "ticks": {"x": [{"at": 1}], "y": []}, "labels": [{"at": [1, 2], "text": "S"}], "caption": "한 줄"}
```
- 식은 sympy 문법(`x**2`, `sqrt(3)`, `log(x, 2)`, `Abs`, `Piecewise`), 숫자 자리에도 식 문자열 가능. 단축형 `{"fn": "x^3-3x", "domain": [-3, 3]}`도 된다. 라벨의 `^`·`_`는 위·아래첨자.

## check_book 검사 항목
- 스키마, week ≤ total_weeks, DAY 번호 오름차순·중복 없음, 같은 테마 DAY는 연속
- 기출: db에 있고 excluded 아님, 22~27학년도·4점, 과목 = 테마 과목, 후보 밖이면 `reason`(없으면 오류), 홈 테마 밖이면 `reuse_note`, 그림 있는 기출은 `figures` 명세
- 창작: 문제은행에 있고 `verified`(통과 후 수정되지 않음), 다른 테마 창작은 `reuse_note`
- 교재 문항: 판독 파일에 있고 `verified`, 과목 = 테마 과목, 다른 테마로 분류된 문항은 `reuse_note`, `figure_note`만 있으면 오류(그림 명세 필요). 이 책의 테마로 분류된 교재 문항을 다 쓰지 않았거나 예제가 교재 문항이 아니면 경고
- 같은 DAY 안 중복 금지, 책 전체 사용 3회 이하, SCOUTING은 db 기출(예제 자신 제외), REPLAY·SIGN BOOK 번호 범위, `notes` 대상·`shortcut`+`verify`, `concept_ids` 존재
- 테마마다 2~3 DAY, 8~13문항(예제 포함), 기출 5개 이상, 창작 50% 이하. 기출:창작 비율·행동 영역·난도 분포는 report에 표시만
- 텍스트: `$` 짝, HTML 태그 금지, 야구 용어 금지(코너 이름 THE SIGN·FIRST PITCH·SIGN READING·SCOUTING REPORT·REPLAY·DUGOUT NOTE·SIGN BOOK 제외; 목록은 `config.json` `banned_terms`)

## 해설 규칙
- 기출 해설은 solutions.json `study_solution`(208문항 작성·검산 완료). 풀이 1 = 스킬, 풀이 2 = 정석 비교.
- **PDF 원문 해설은 교재에 싣지 않는다** (출판사 해설, 저작권). `solution_ref`는 참고·검산용.
- 새로 쓰는 해설(창작·새 숏컷)은 `solutions/SPEC.md` 규격과 `pilot/pilot_v2.json` 수준: 단순 계산 대신 스킬, 모든 단계에 근거, 개념 참조. `verify` 필수.
- 고난도 번호(수학Ⅰ·Ⅱ 14·15·21·22, 확통 28·30, `config.json`)는 해설 분량·강조를 우선한다.

## 판면 규칙
- 템플릿의 head(글꼴 링크·CSS·스크립트)는 그대로 복사한다. CSS 수정 금지. 결과물 body에는 `data-template` 속성이 없다(화면 점검 켜짐).
- 한 페이지 = A4 794×1123px. 목차(5 DAY까지)·REPLAY(3개까지)·정답표·해설은 build가 재면서 나눈다. 그 밖의 페이지(CONCEPT·STRATEGY·FIRST_PITCH·SIGN_READING·PRACTICE·SIGN_BOOK)가 넘치면 **글자를 줄이지 말고 내용을 줄인다**(보고서 오류로 온다). STRATEGY는 넘치면 먼저 '떠올릴 때' 줄을 자동으로 뺀다.
- 책 순서: COVER → CONTENTS → [DAY: CONCEPT → STRATEGY → FIRST_PITCH → SIGN_READING → PRACTICE×N → REPLAY → DUGOUT_NOTE → SIGN_BOOK] → QUICK_ANSWER → SOLUTION×N → BACK_COVER. 쪽 번호는 표지 001부터 3자리.

## 개발 규칙
- 의존성: Python 3.10+, jinja2, sympy, numpy, jsonschema, playwright (`requirements.txt`). KaTeX는 `vendor/katex/`에 동봉.
- 크로스플랫폼: 경로는 `pathlib`, 외부 명령은 `subprocess`에 리스트로(셸 문법 금지), 파일은 `encoding="utf-8"`, 셸 스크립트(.sh/.bat) 금지. 브라우저는 `common.launch_chromium`(기본 → 설치된 Chromium 탐색 → 환경변수 `STS_CHROMIUM`).
- 원천 JSON의 LaTeX는 이스케이프에 주의: `"\\frac"`. `"\frac"`는 폼피드+`rac`로 깨진다(validate가 제어문자로 잡는다).
- 스크립트를 고치면 `python -m unittest discover tests`와 샘플 전체 실행(`python run.py --book samples/book.sample.json --created <샘플 복사본> --out <임시>`)으로 확인한다.
- 사용자 응답은 간결하게.
