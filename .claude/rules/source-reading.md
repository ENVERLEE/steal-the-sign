---
globs:
  - "work/source/**"
  - "scripts/check_source.py"
---

# 교재 판독 파일

`work/source/{교재id}.json` — AI가 교재 이미지를 보고 작성하는 파일.

## 구조

```json
{
  "book": {"id": "KB1", "title": "교재 이름", "pdf": "원본.pdf"},
  "problems": [{
    "id": "T-KB1-001",
    "page": 12,
    "number": "3",
    "subject": "수학Ⅰ",
    "theme": "M1-01",
    "question": "$LaTeX$ 본문",
    "condition": null,
    "choices": ["$-5$", ...] | null,
    "answer": "2",
    "answer_value": "-1",
    "answer_source": "교재 정답|AI 풀이",
    "points": 3,
    "figure": 그림명세 | null,
    "figure_note": "그림 명세 메모",
    "first_judgment": "한 문장",
    "behavior": "계산|이해|추론|문제해결",
    "difficulty": "기본 적용|…",
    "similar": ["M1-230911", ...],
    "solution": {"concept_refs": [], "guide": "", "solutions": [...], "supplement": "", "skill_point": ""},
    "verify": "def skill(): ..."
  }]
}
```

## 규칙

### 기본
- 판독은 원문 그대로 (수식 `$…$`, 선지는 `$` 포함)
- 교재 번호·쪽 그대로
- 교재 출처: `{book.title} {쪽}쪽 {번호}번`으로 찍힘
- `book.title`은 사용자가 입력한 표기(`pages.json`의 `title`)와 같아야 함

### 해설
- **교재 원문 해설은 옮기지 않음** (출판사 해설, 저작권)
- AI가 새로 씀 (풀이 1 = 스킬, 있으면 풀이 2 = 정석)
- `verify`의 `skill()` 필수
- 정답지 없어서 `answer_source: AI 풀이`면 `standard()` 필수

### 테마·개념
- 테마: themes.json의 `kice_intent`·`signals` 기준
- `concept_refs`: 그 테마 `old_themes`의 개념에서 고름
- `similar`: 같은 테마의 `problem_ids`·`related_ids`에서 우선. 판단 구조가 같은 기출, 가까운 순.

### 개수 제약
- 테마당 최대 8개 (기출 5개 자리 확보)
- 넘치면 큐레이션이 다음 권·다른 테마로 돌림

### 저작권
교재 원문을 실은 결과물은 수업·개인용으로만 사용.

## 작성 흐름

1. 한 번에 10~20문항씩 작성
2. `python run.py source`로 검사
3. 오류만 고침
4. 반복

## verify 코드

필수 함수:

```python
def skill():
    # 스킬을 사용한 풀이
    return ...

def standard():  # 선택 (교재 정답이 있으면)
    # 정석적 풀이 또는 검증
    return ...

def unique():    # 선택
    # 조건을 만족하는 모든 답
    return [...]
```
