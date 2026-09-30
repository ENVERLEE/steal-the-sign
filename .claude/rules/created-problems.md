---
globs:
  - "work/created/**"
  - "scripts/check_created.py"
---

# 창작 문항 규칙

창작 비율은 고정하지 않는다. **검문을 통과한 창작만** 교재에 들어가며, 비율은 그 결과로 정해짐 (report 표시).

테마 구성 제약: 테마당 기출 등장 5개 이상, 창작 비중 50% 이하(`config.json` `composition`).

## 1. 기출 변형이 기본

- `origin.type`=`variant`: `parent_id`(db id)·`variation`(수치·조건·역방향·일반화·결합) 필수
- 원본의 문체·조건 구조·테마 의도 유지
- `original`(신작): 테마당 1개까지

## 2. 스크립트 검문 (check_created.py)

### 형식
- 스키마, [3점], 객관식 5지선다 또는 단답형 1~999 자연수
- `choice_values`·`answer_value` 필수 (객관식), 선지 값 서로 다름
- 금지어 없음, `$` 짝 맞음, 개념·strategy id 존재
- 파일 위치: `work/created/{테마}/{id}.json`

### 정답 검산
- `verify`의 `skill()`과 `standard()` 둘 다 정답 값
- `unique()`: 조건을 만족하는 답을 전수·기호 계산으로 모두 구해 정답 1개만

### 오답 선지
- 객관식: 오답 4개 모두 `distractors[{choice, error_path}]`

### 스킬 적중
- `target.concept_ids`: 테마 기존 개념 1개 이상 겨냥 (필수)
- `target.first_judgment`: 필수
- 풀이 1(스킬)·풀이 2(정석) 둘 다 필수
- 풀이 1 분량 ≤ 풀이 2의 70%
- 원본 대비 본문 유사도 90% 이상: 경고 (수치만 바꾼 복제 의심)
- 그림 명세 렌더링 오류 검사

## 3. 상태 관리

- `draft`(작성·미통과) → `verified`(통과)
- **AI는 `status`·`review` 작성 금지**
- 내용 해시를 `review.hash`에 저장
- 통과 후 내용 변경 시 재검사

## 4. 천천히 쌓기

- 테마당 검사 대기 문항(미통과) 4개 초과 시 id 순 앞 4개만 검사, 나머지 차단
- 통과한 창작은 다른 권·테마에서 재사용 (기출과 같은 규칙)

## verify 코드 작성

- 사용 가능: `sympy`(이름 그대로, `sp`), `numpy`(`np`), `math`, `itertools`, `Fraction`
- `print` 금지, 30초 제한
- 반환값: sympy 식(`Rational(9,7)*pi`) 또는 정수

### 필수 함수

```python
def skill():
    # 스킬을 사용한 풀이
    return ...

def standard():
    # 정석적 풀이 (또는 검증용)
    return ...

def unique():
    # 조건을 만족하는 모든 답을 리스트로
    # 정답이 유일한지 검증
    return [...]
```

## 생성 파일

- 샘플: `samples/created/M1-01/`
- 교재 표기: `STEAL THE SIGN 창작` [3점]
