# 평가원 4점 기출 통합 DB (208문항)

| 파일 | 과목 | 문항 수 | 출처 PDF |
|---|---|---|---|
| `m1.json` | 수학Ⅰ | 81 | 수학I 평가원 기출모음 (고3 21년 6월 ~ 26년 6월) |
| `m2.json` | 수학Ⅱ | 79 | 수학II 평가원 4점 기출모음 |
| `prob.json` | 확률과 통계 | 48 | 확통 평가원 4점기출모음 |
| `all.json` | 전체 | 208 | 위 세 파일 합본 |

## 스키마

```json
{
  "id": "M1-230911",            // 과목접두(M1/M2/PS)-source.code
  "subject": "수학Ⅰ",
  "source": {"code": "230911", "year": 2023, "exam": "9월 모의평가", "number": 11, "points": 4,
             "label": "2022년 9월 고3 11번"},   // code/year = 학년도 기준, label = PDF 원표기(시행연도)
  "question": "LaTeX 본문",
  "condition": "(가)/(나) 조건·<보기>·빈칸 과정 (없으면 null)",
  "choices": ["...x5"] | null,  // 단답형은 null
  "answer": "2",                // 객관식은 번호, 단답형은 값
  "answer_value": "9",          // 객관식 번호가 가리키는 선택지 값
  "figure": {"description": "...", "source_page": 1} | null,
  "theme": {"primary": "수학Ⅰ-01", "primary_name": "거듭제곱근", "links": ["수학Ⅰ-02"]},
  "first_judgment": "한 문장",
  "behavior": "계산 | 이해 | 추론 | 문제해결",
  "reasoning": ["조건의 식 번역", ...],
  "strategy_ids": ["S01"],
  "solution_ref": "PDF 해설 요약 LaTeX (참고용)",
  "legacy": {"category": "PDF 소단원 분류", "book_no": 1, "question_page": 1, "solution_page": 42},
  "check": {"answer_match": null, "excluded": false, "needs_review": []}
}
```

### 분류 기준
- **theme**: 고정 테마 목록(수학Ⅰ 21 / 수학Ⅱ 21 / 확률과 통계 22) 번호. `primary`는 1개, `links`는 연결 테마.
- **behavior**: `계산`(절차 적용) · `이해`(빈칸 채우기형 과정 따라가기) · `추론`(조건 해석·경우 분류) · `문제해결`(여러 단계 결합·역추적).
- **reasoning** 허용값: 조건의 식 번역, 경우 나누기, 그래프·도형 해석, 대칭성·주기성 활용, 단순화·특수화로 규칙성 찾기, 나열·역추적, 치환·보조함수 도입, 미지수 소거·연립, 정수 조건으로 후보 좁히기, 여사건·전체에서 빼기, 대응·모델링.
- **strategy_ids**: `tools/strategy_notes.json`의 S01–S26. 부여한 id는 모두 해당 전략의 연결 테마와 문항 테마가 겹치도록 검사했다. 확률과 통계는 전략 노트가 없어 빈 배열.

### 검사 상태
- `answer`는 PDF 해설 페이지의 정답을 옮긴 값이다. 기존 DB JSON을 받지 못해 `check.answer_match`는 모두 `null`.
- `needs_review`가 있는 문항: `M1-260620`(원문 해설 표기 확인), `M1-270622`(해설 표 요약).
- 그림 문항은 `figure.description`에 텍스트 설명만 있다. 이미지는 `legacy.question_page`의 PDF 페이지에서 잘라 써야 한다.

## 재생성
`python3 tools/build.py data` — `tools/records/*.py`(문항별 원본 기록) + `tools/sources_*.txt`(출처표) + `tools/skeleton.json`(PDF 페이지·소단원)을 합쳐 JSON을 만들고, 선택지 수·정답 번호·분류 허용값·strategy id를 검증한다.
