---
globs:
  - "work/book*.json"
  - "scripts/check_book.py"
---

# book.json 검사 항목 (check_book)

## 기본 구조
- 스키마 검증
- `week` ≤ `total_weeks`
- DAY 번호 오름차순·중복 없음
- 같은 테마 DAY는 연속
- 모든 테마가 `subject_label` 과목 (한 권 = 한 과목)

## 기출 검사
- db에 있고 `excluded` 아님
- 22~27학년도·4점
- 과목 = 테마 과목
- 후보(테마 `problem_ids`·`related_ids`) 밖이면 `reason` 필수 (없으면 오류)
- 홈 테마 밖이면 `reuse_note` 필수
- 그림 있는 기출은 `figures` 명세 필수

## 창작 검사
- 문제은행에 있고 `verified` 상태
- 통과 후 수정되지 않음 (내용 해시 확인)
- 다른 테마 창작은 `reuse_note` 필수

## 교재 문항 검사
- 판독 파일에 있고 `verified` 상태
- 과목 = 테마 과목
- 다른 테마로 분류된 문항은 `reuse_note` 필수
- `figure_note`만 있으면 오류 (그림 명세 필수)
- 경고: 이 책 테마 교재 문항을 다 못 씀 또는 예제가 교재 문항 아님

## 중복·재사용 검사
- 같은 DAY 안 중복 금지
- 책 전체 사용 3회 이하
- SCOUTING: db 기출만 (예제 자신 제외)
- REPLAY·SIGN BOOK 번호 범위 검증

## 부록 검사 (appendix)
- refs가 문제은행의 verified·해시 일치 창작이고 `calc_type` 있음, 부록 안 중복 금지
- 유형당 4~20문항(오류), 전체 30~50(경고)
- DAY 연습에 `calc_type` 창작을 쓰면 오류

## 노트 검사
- `notes` 대상이 존재하는 문항 id
- `shortcut` 있으면 `verify` 필수
- `concept_ids` 존재 여부

## 테마 구성 검사
- 테마마다 2~3 DAY
- 테마마다 8~13문항 (예제 포함)
- 테마마다 기출 5개 이상
- 창작 비중 50% 이하
- **기출:창작 비율·행동 영역·난도 분포는 report에만 표시** (error 아님)

## 글 규격 검사 (경고)
- 기존형 개념(비유) 사용 여부
- 개념 소제목 2개·정리·요약·예제·지도 5행(f 포함)
- 실전 개념 3개 (eq·when)
- 문항 분석 요점 3개 ({title, text})

## 텍스트 검사
- `$` 짝 맞음
- HTML 태그 금지
- 야구 용어 금지 (The Sign·First Pitch·Sign Reading·Scouting·Replay·Dugout·Sign Book 제외, `config.json` `banned_terms`)
