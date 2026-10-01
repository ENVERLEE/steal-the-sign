---
globs:
  - "data/problems/**"
  - "data/themes.json"
  - "data/solutions/**"
  - "data/concepts.json"
  - "work/book*.json"
  - "schema/**"
---

# 스키마 참고 문서

## data/problems/{id}.json — 기출 데이터 (문항 하나 = 파일 하나)

- 파일명 = `id`. 아래 스키마 + `"home": "M1-01"`(홈 테마, 필수, 208문항이 한 번씩). `data/index.json`은 validate가 자동 생성하는 한 줄 요약이다. **문항을 고를 때는 index.json만 읽고, 고른 문항 파일만 연다.**

```json
{
  "id": "M1-230911",
  "subject": "수학Ⅰ",
  "source": {"code": "230911", "year": 2023, "exam": "9월 모의평가", "number": 11, "points": 4,
             "label": "2022년 9월 고3 11번"},
  "question": "LaTeX 본문",
  "condition": "(가)(나)·<보기>·빈칸 과정 | null",
  "choices": ["선지"] | null,
  "answer": "2",
  "answer_value": "선택지 값",
  "figure": {"description": "그림 설명", "source_page": 5} | null,
  "theme": {"primary": "수학Ⅰ-01", "primary_name": "거듭제곱근", "links": ["수학Ⅰ-02"]},
  "first_judgment": "한 문장",
  "behavior": "계산|이해|추론|문제해결",
  "reasoning": ["조건의 식 번역", ...],
  "strategy_ids": ["S01"],
  "solution_ref": "PDF 해설 요약",
  "check": {"answer_match": null, "excluded": false}
}
```

- `source.code`=`YYMMNN` 학년도 기준. `label`은 시행연도. `exam`은 6월·9월·수능.
- 범위: 2022~2027학년도(2021년 6월~2026년 6월) 평가원 기출, 전부 4점.
- 번호: 공통 1~22, 확통 23~30. 수학Ⅰ·Ⅱ code 충돌 검사 대상.
- 텍스트: `$…$` 수식, `\\`·`\n` 줄바꿈. **선지는 `$` 없이 LaTeX만**.
- 정답: 208문항 전부 검산 완료.
- `reasoning` 허용값(11): 조건의 식 번역, 경우 나누기, 그래프·도형 해석, 대칭성·주기성, 단순화·특수화, 나열·역추적, 치환·보조함수, 미지수 소거·연립, 정수 조건, 여사건·전체에서 빼기, 대응·모델링.

## themes.json — 교재 테마

원칙: 교과서 소단원이 아니라 **평가원 첫 판단**이 같은 문항끼리 묶음.

- 28개 = 수학Ⅰ 11(`M1-01`~`11`) + 수학Ⅱ 10(`M2-01`~`10`) + 확통 7(`PS-01`~`07`)
- 208문항이 홈 테마 하나에 한 번씩 배정(테마당 5~10, 문항 파일의 `home`)
- **교재 테마는 themes.json 기준.** 테마의 `problem_ids`는 문항 파일의 `home`에서 자동 집계(파일에 쓰지 않는다). `related_ids`만 themes.json에 둔다. 문항의 `theme.primary`는 기존 64분류(개념 id 출처로만 사용).
- **기출 중복 사용 허용**: 우선 `problem_ids`·`related_ids`에서. 그 밖은 `reason` 필수(경고).
- 같은 DAY 중복 금지, 책 전체 3회 이하 사용, 홈 테마 밖이면 `reuse_note` 필수.

## 해설 및 개념

- `data/concepts.json`: `themes[]` 54개 테마의 개념·의사결정 흐름. 기존 64분류 기준.
- `data/solutions/{id}.json`: 문항 하나의 `study_solution`(풀이).
- 풀이: `guide`(조건 번역) → `solutions`(풀이 1 스킬, 풀이 2 정석) → `supplement`(비교) → `skill_point`.
- 내부 개념 id `(수학Ⅰ-02-C1)`는 build가 지우거나 「개념 이름」으로 변환.

## book.json — 교재 구성

```json
{
  "week": 1,
  "total_weeks": 8,
  "year_label": "2027학년도",
  "subject_label": "수학Ⅰ",
  "figures": {"M2-231110": 그림명세, ...},
  "days": [{
    "day": 1,
    "theme": "M1-01",
    "title": "챕터 제목(24자)",
    "concept": {"sections": [...], "card": {...}, "banner": "", "example": {...}, "map": [...]},
    "strategy": {"structure": "", "tools": [...]},
    "first_pitch": {"signal": "", "ref": ""},
    "sign_reading": {"hint": "", "analysis": "", "points": [...], "verdict": "", "scouting": [...]},
    "practice": [{"ref": "ID", "difficulty": ""}],
    "replay": [{"no": 1, "wrong": "", "stuck": "", "fix": ""}],
    "sign_book": {"rows": [...], "next": ""},
    "notes": {"ID": {"shortcut": "", "verify": ""}}
  }]
}
```

- HTML 금지. 텍스트 + `$LaTeX$`만 (줄바꿈 `\n`).
- **문항은 id로만 참조**: 기출 db id, 창작 `C-…`, 교재 `T-…`. 본문·정답·해설은 build가 가져옴.
- **개념: 교과서형** = `sections`(제목·블록) + `card`(정리) + `banner`(요약) + `example`(교과서적 vs 실전 해법) + `map`(5행).
- 텍스트 강조: `**굵게**`, `__밑줄(형광)__`. 수식 뒤 조사($x$에)는 build가 묶음.
- **build 자동화**: 목차, 쪽번, 정답표, DUGOUT NOTE, 실전 개념 행, 해설지 (숏컷 = 조건번역+풀이1, 정석 = 풀이2).
- 샘플: `samples/book.sample.json` (M1-01, 2 DAY).

## figure 명세

```json
{
  "fns": [{"expr": "x**3-3*x", "domain": [-2, 2], "label": "y=f(x)", "style": "main"}],
  "x": [-3, 3],
  "y": [-3, 3],
  "equal": false,
  "points": [{"x": 1, "y": "-2", "label": "A", "pos": "ne", "guides": true}],
  "hlines": [{"y": 2, "label": "y=k"}],
  "caption": "한 줄"
}
```

- 식: sympy 문법 (`x**2`, `sqrt(3)`, `log(x, 2)`, `Abs`, `Piecewise`).
- 단축형: `{"fn": "x^3-3x", "domain": [-3, 3]}`.
- 라벨의 `^`·`_`는 위·아래첨자.

## source.json — 교재 판독

쪽 이미지 보고 AI가 작성. 문항마다 원문 그대로(수식은 `$…$`, 선지는 `$` 포함).

- `similar`: 판단 구조가 같은 기출(가까운 순). themes.json `problem_ids`·`related_ids`에서 우선.
- `answer_source`: "교재 정답" | "AI 풀이". AI 풀이면 `verify`의 `standard()`도 필수.
- 교재 문항은 테마당 최대 8개 (기출 5개 자리 확보).

## book.advice — 학습 조언 (표지 다음 첫 쪽)

`{title, assessment, patterns:[{name,text,fix}], methods:[{title,text}]}` — 실력 평가 + 폭주 패턴 처방 + 공부 방법. 한 쪽에 들어가야 함(넘치면 오류).

## book.appendix — 계산 연습 부록

```json
"appendix": {"title": "계산 연습", "intro": "", "types": [
  {"title": "유형 이름(24자)", "trap": "자주 하는 실수", "habit": "검산 습관", "refs": ["C-M1-01-101", ...]}]}
```
- refs는 `calc_type`이 있는 verified 창작만. 유형당 40개 이상 목표(미만 경고, `config.appendix`). 창작 출처는 비운다.

## created.json — 창작 문항

`work/created/{테마}/{id}.json`

- `origin`: `variant`면 `parent_id`·`variation` 필수. `original`은 테마당 1개까지.
- `target`: `concept_ids`·`strategy_ids`·`first_judgment` 필수.
- `choices`: 5지선다 또는 null (단답형). 선지 값 모두 다름.
- `answer`: 번호(객관식) 또는 값(단답형). `answer_value` 필수(객관식).
- `calc_type`: 계산 연습 부록 전용 문항 표시(유형 이름). 신작 1개 제한 면제, curate·DAY 연습 제외.
- `distractors`: 객관식이면 오답 4개 모두 기록.
- `verify`: sympy(sp)·numpy(np)·math·itertools·Fraction 사용 가능. 30초 제한. `skill()`·`standard()`·`unique()` 필수.
- **상태**: `draft`(미통과) → `verified`(통과). AI는 `status`·`review` 작성 금지.
- 검사 대기 문항이 4개 초과면 앞 4개만 검사.
