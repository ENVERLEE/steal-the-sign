---
globs:
  - "data/solutions.json"
  - "solutions/**"
  - "work/book*.json"
---

# 해설 규칙

## 기출 해설

기출 해설은 `solutions.json` `study_solution`에 이미 작성·검산 완료 (208문항).

- 풀이 1 = 스킬 풀이
- 풀이 2 = 정석 비교 (있으면)

**PDF 원문 해설은 교재에 싣지 않음** (출판사 해설, 저작권). `solution_ref`는 참고·검산용만.

## 새로 쓰는 해설

창작·새 숏컷 해설은 `solutions/SPEC.md` 규격과 `pilot/pilot_v2.json` 수준으로 작성.

### 원칙
- 단순 계산 대신 스킬 강조
- 모든 단계에 근거 제시
- 개념 참조 포함
- **`verify` 필수**

### 구조

```json
{
  "concept_refs": ["수학Ⅰ-01-C1"],
  "guide": "조건 번역 및 꺼낼 개념",
  "solutions": [
    {
      "title": "풀이 1 · 스킬",
      "steps": [
        {"label": "1단계", "body": "..."},
        {"label": "2단계", "body": "..."}
      ]
    },
    {
      "title": "풀이 2 · 정석",
      "steps": [...]
    }
  ],
  "supplement": "비효율 풀이 비교·일반화·흔한 실수",
  "skill_point": "드릴 포인트 한 줄"
}
```

## 고난도 우대

고난도 번호 (수학Ⅰ·Ⅱ 14·15·21·22, 확통 28·30, `config.json`):
- 해설 분량 우선
- 강조 표현 우선

## 개념 id 변환

해설 본문의 `(수학Ⅰ-02-C1)` 같은 내부 개념 id는 build가:
- 지우거나
- 「개념 이름」으로 변환

하여 교재에 싣기 좋게 정리.
