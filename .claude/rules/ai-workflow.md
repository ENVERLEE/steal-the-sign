---
globs:
  - "work/source/**"
  - "work/created/**"
  - "work/book*.json"
  - "data/index.json"
  - "data/themes.json"
  - "data/concepts.json"
---

# AI 작업 순서 — 교재 PDF를 받았을 때

교재의 문제가 **예제**가 되고, 테마별로 유사 기출·창작을 붙여 드릴 교재를 만든다.

## 1단계: 쪽 변환
교재 출처 표기(교재에 `{표기} {쪽}쪽 {번호}번`으로 찍힐 이름)를 **사용자에게 물어** 그대로 받는다.

```bash
python run.py pages --pdf <올린파일> --id <교재id> --title "<사용자가 정한 표기>"
```

결과: `work/source/<교재id>/pages/p###.png` + 텍스트 층

**주의**: 표기를 AI가 줄이거나 바꾸지 않는다. 바꿀 때는 `run.py title`.

## 2단계: 판독·분류
쪽 이미지를 보고 모든 문제를 `work/source/<교재id>.json`에 적는다.

문항마다 기록:
- `theme`: 28개 테마 중 하나
- `first_judgment`: 첫 판단 한 문장
- `similar`: 유사 기출 id (판단 구조가 같은 기출, 가까운 순)
- `solution`: 새로 쓰는 해설 (풀이 1 = 스킬)
- `verify`: 정답 검산 코드 (`skill()` 필수)

**진행**: 한 번에 10~20문항씩 쓰고 `python run.py source`로 검사 → 오류만 고침

## 3단계: 큐레이션
`python run.py source`가 만든 `out/curation.md`·`out/plan.json`을 본다.

테마마다:
- 2~3 DAY
- 교재 문항 2~3개가 예제
- 나머지는 교재 문항·유사 기출·창작이 연습

**창작 필요**: '창작 N개 더 필요'가 나오면 그 테마 창작을 **4문항 이하**로 `work/created/{테마}/{id}.json`에 씀 → `python run.py created` → 통과할 때까지 → 다시 `python run.py source`

## 4단계: 교재 구성
plan.json의 문항 배정을 `work/book.json`에 옮기고 글을 **`WRITING.md`의 교과서형 규격**으로 씀.
(개념·실전 개념·분석·REPLAY·다음 챕터)

**새 형식·디자인**: DAY 1 시안을 먼저 보여 주고 확인받은 뒤 전체에 적용.

**파일명**: `work/book_{m1|m2|ps}_w{주}.json`  
**결과**: `STS_{과목}_WEEK{주}`

**기출**: 그림 있는 기출은 `figures` 명세 필수.

**한 권 기준**: 한 권 = 한 과목의 1주 분량(WEEK). 과목 섞지 않고, 권번·DAY번은 과목마다 1부터.

## 5단계: 빌드 및 검증
```bash
python run.py                   # 전체 파이프라인
```

`out/report.md`의 **'AI에게 전달할 수정 목록'**만 고침 → 오류 0 → `out/book.html`(+`out/book.pdf`) 사용자에게 제공

## 교재 PDF 없이 만들 때
3~5단계만 한다 (예제는 기출·창작에서 고름).

## 실모 오답 특강 (분석 JSON을 받았을 때)
1. 표기(`실모 제N회` 등)를 사용자에게 받아 `python run.py mock --json 분석.json --id MK1 --title "<표기>"`
2. `work/mock/MK1_draft.json`(뼈대)에 `theme`·`first_judgment`·`similar`·`solution`·`verify` 등을 채워 `work/source/MK1.json`로 저장(`book.mock: true`, `page` 없음 → 출처 `{표기} {번호}번`). `python run.py source`로 검사. `mistake`(틀린 이유·패턴)는 REPLAY·DUGOUT NOTE·부록 유형 선정에 쓴다.
3. 특강 모드(`book.special`) 책: 틀린 문제가 나온 테마만 챕터, 챕터당 약 20문항(`theme_plan.special_problems` [16,24]), 실모 문항이 예제.
4. 계산 연습 부록(`book.appendix`): 계산실수 패턴 3~4개를 유형으로 정리, 유형당 40문항 이상, 전부 창작(`calc_type` 필드, `work/created/{테마}/`에 저장, 검문 한도 `created.calc_batch_max`=10). DAY 연습에는 쓰지 않는다. 해설 뒤·뒤표지 앞에 CALC·CALC_SOL 쪽으로 조판.
