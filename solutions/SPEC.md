> 참고 문서: `claude/pdf-problem-db-merge-98r9as` 브랜치에서 가져옴. 이 저장소에서는 `all.json` → `data/db.json`, `solutions_all.json` → `data/solutions.json`, `tools/strategy_notes.json` → `data/strategy_notes.json`. 언급된 `tools/*.py`는 원 브랜치에만 있다. 프로젝트 목적·규칙은 루트 `CLAUDE.md` 기준.

# 자습용 풀이집 작성 규격

## 목적
과외받듯 이해되는 **자습용 풀이집**. 진짜 목적은 테마별 **실전개념(스킬)을 드릴링**해서 그 테마는 무조건 맞히게 하는 것.
- 비효율적 단순계산 풀이를 지양하고, 계산을 줄이는 스킬·판단을 드러낸다.
- 풀이 길이를 줄이라는 뜻이 아니다. 개념 보충·판단 근거는 충분히 쓴다.
- 반드시 `pilot/pilot_v2.json`을 먼저 읽고 **그 깊이·문체·구조를 기준**으로 삼는다.

## 입력
- 문항 DB: `data/m1.json`(수학Ⅰ), `data/m2.json`(수학Ⅱ), `data/prob.json`(확률과 통계). 각 문항의 `question`, `condition`, `choices`, `answer`, `answer_value`, `theme`, `first_judgment`, `strategy_ids`, `solution_ref`(PDF 해설 요약, 참고용), `figure`.
- 전략 노트: `tools/strategy_notes.json` (S01~S26).
- 그림이 필요한 문항: `figure.source_page`의 페이지 이미지
  `/tmp/claude-0/-home-user-steal-the-sign/5fc4cc41-d01e-516a-8f36-535f54b30021/scratchpad/pages/{m1|m2|prob}_{page:03d}.png` (Read 도구로 보기). 해설 페이지는 `legacy.solution_page`.

## 출력
담당 테마마다 파일 하나: `solutions/{m1|m2|prob}/{theme_id}.json` (예: `solutions/m2/수학Ⅱ-08.json`)
```json
{
 "theme": "수학Ⅱ-08",
 "theme_name": "접선의 활용",
 "overview": "이 테마에서 반복되는 판단의 핵심 (3~5문장)",
 "core_concepts": [
  {"id": "수학Ⅱ-08-C1", "name": "...", "statement": "LaTeX", "why": "유도·근거", "when": "언제 꺼내는가",
   "strategy_ids": ["S.."], "example": "(선택) 짧은 EX 예제와 풀이"}
 ],
 "decision_flow": ["판단 1 → ...", "판단 2 → ..."],
 "solutions": [
  {"id": "문항 id", "concept_refs": ["수학Ⅱ-08-C1", "다른 테마 개념 id도 가능"],
   "guide": "조건 번역·어떤 개념을 꺼낼지 (풀이 전 나침반)",
   "solutions": [{"title": "풀이 1 · 핵심 아이디어", "steps": [{"label": "단계 이름", "body": "LaTeX, 근거(∵)를 붙인다"}]}],
   "supplement": "보충설명: 비효율 풀이와의 비교, 일반화할 성질, 흔한 실수",
   "skill_point": "이 테마 드릴 포인트 한 줄",
   "answer": "DB의 answer와 동일한 값(객관식은 번호)"}
 ]
}
```

## 규칙
1. **정답**: 직접 풀어서 얻은 답이 DB `answer`와 반드시 같아야 한다. 다르면 다시 풀고, 그래도 다르면 해당 문항에 `"needs_review": "사유"`를 넣는다.
2. **원문 금지**: PDF 해설(`solution_ref`, 해설 페이지)은 정답 확인·참고용. 문장을 옮기지 말고 새로 쓴다.
3. **core_concepts**: 테마당 2~5개. 담당 문항들에서 실제로 쓰인 스킬만. 교과서 정의 나열 금지 — '실전개념'(조건→행동) 중심. 관련 S-id가 있으면 연결.
4. **복수 풀이**: 더 빠른 스킬 풀이가 있으면 풀이 1로, 정석 풀이는 비교용 풀이 2로. 억지로 늘리지 않는다.
5. **LaTeX**: 수식은 `$...$`/`$$...$$`. JSON 문자열이므로 백슬래시는 `\\`로 이스케이프. `$` 개수는 짝수.
6. 담당 테마의 문항은 `theme.primary`가 그 테마인 문항 전부. 하나도 빠뜨리지 않는다.
7. 파일을 쓴 뒤 `python3 -c "import json;json.load(open(경로))"`로 유효성 확인.
8. git commit/push 하지 않는다(메인이 취합).
