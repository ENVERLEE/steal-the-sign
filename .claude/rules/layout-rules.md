---
globs:
  - "out/book.html"
  - "data/STS_template.html"
  - "data/STS_ext.html"
---

# 판면 규칙

## 템플릿

- STS_template.html의 head (글꼴·CSS·스크립트) 그대로 복사
- CSS 수정 금지
- 추가 스타일(교과서형 페이지, 본문 명조 Noto Serif KR, 낱말 단위 `word-break: keep-all`)은 `data/STS_ext.html`의 HEAD 블록에만 추가
- build가 head 끝에 덧붙임
- 해설지(11px)는 고딕 그대로
- 결과물 body에는 `data-template` 속성 없음 (화면 점검 켜짐)

## 페이지 크기

- 한 페이지 = A4 794×1123px
- 목차(5 DAY까지)·REPLAY(3개까지)·정답표·해설은 build가 재면서 자동 나눔

## 연습 문항 배치

- 기본은 한 쪽에 3~4문항(고난도는 2문항, 난도 순서 유지). 한 쪽에 한 문항씩 두려면 book에 `"practice_layout": "single"`

## 남는 공간

- STRATEGY(교과서형)·REPLAY·SIGN BOOK 아래 남는 공간은 직접 쓰는 메모 칸(점선 상자)으로 채움. 150px보다 좁으면 숨김
- 배점 `[N점]`은 본문 마지막 낱말과 묶여 혼자 줄바꿈되지 않음

## 넘침 처리

페이지 초과(CONCEPT·STRATEGY·FIRST_PITCH·SIGN_READING·PRACTICE·SIGN_BOOK):
- **글자를 줄이지 말고 내용을 줄임** (보고서 오류로 온다)
- STRATEGY는 넘치면 먼저 '떠올릴 때' 줄을 자동 제거

## 책 순서

```
COVER → [ADVICE: 학습 조언 한 쪽, book.advice가 있을 때] → CONTENTS
[DAY마다:
  CONCEPT
  STRATEGY
  FIRST_PITCH
  SIGN_READING
  PRACTICE×N
  REPLAY
  DUGOUT_NOTE
  SIGN_BOOK
]
QUICK_ANSWER
SOLUTION×N
[부록이 있으면: CALC×N (유형마다) → CALC_SOL×N]
BACK_COVER
```

## 쪽 번호

- 표지 001부터 3자리
- `out/book.pdf` 쪽 수 = HTML `.page` 수, A4 크기 확인
