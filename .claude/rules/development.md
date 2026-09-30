---
globs:
  - "scripts/**"
  - "tests/**"
  - "run.py"
---

# 개발 규칙

## 의존성

- Python 3.10+
- 라이브러리: jinja2, sympy, numpy, jsonschema, playwright (`requirements.txt`)
- KaTeX: `vendor/katex/` 동봉 (0.18.9)

## 크로스플랫폼

- 경로: `pathlib` 사용
- 외부 명령: `subprocess`에 리스트로 (셸 문법 금지)
- 파일: `encoding="utf-8"`
- 셸 스크립트(.sh/.bat) 금지
- 브라우저: `common.launch_chromium` (기본 → 설치된 탐색 → 환경변수 `STS_CHROMIUM`)

## JSON LaTeX 이스케이프

주의:
- `"\\frac"` ✓ (올바름)
- `"\frac"` ✗ (폼피드+`rac`로 깨짐 — validate가 제어문자로 잡음)

## 테스트

```bash
python -m unittest discover tests
python run.py --book samples/book.sample.json --created <복사본> --out <임시>
```

## 스크립트 목록

| 파일 | 역할 |
|---|---|
| `validate_sources.py` | id·code·번호·학년도·배점·충돌, 선지·정답 형식, strategy_notes 대조, solutions·themes 누락·불일치·참조, **제어문자**·**KaTeX 오류** → `out/excluded.json` |
| `pdf_pages.py` | PDF → 쪽 PNG·텍스트 (pypdfium2). `--title` 필수. `title` 단계로 변경. |
| `check_source.py` | 교재 판독 파일: 스키마, id·쪽, 테마·과목, 참조, `$` 짝, 제어문자, 그림명세, `verify` 검산 → `status: verified` |
| `curate.py` | 교재 문항 → DAY·예제·연습·SCOUTING 배정 초안 → `out/curation.md`, `out/plan.json` |
| `check_created.py` | 창작 문제은행: 스키마·형식·정답·유일성·오답·스킬·유사도·렌더링 검사 → `status: verified` |
| `check_book.py` | book.json 규칙 검사 |
| `verify_answers.py` | DB 정답 검산, `notes[ref].verify` `skill()` 검산, 창작 `skill`·`standard`·`unique` 재실행 |
| `render_figs.py` | 그림 명세 → SVG (sympy·numpy 계산). `out/figs/` 캐시 |
| `tex.py` | KaTeX 일괄 조판 (Playwright + `vendor/katex`). `out/.cache/tex.json` 캐시. 글꼴 woff2 base64로 CSS 내장 |
| `template.py` | STS_template.html → 페이지별 Jinja2 템플릿. 슬롯 누락 시 오류. `load_ext`: STS_ext.html의 HEAD·XPAGE. |
| `build.py` | 모델 구성(교과서형 DAY는 STS_ext.html, 개념은 블록 단위로 흐름) → 조판 → **A4 판면 재면서** 목차·REPLAY·정답표·해설 페이지 분할 (해설은 한 장에 `config.json` `solution.per_page_max`문항) → `out/book.html` |
| `export_pdf.py` | HTML을 템플릿 인쇄 CSS로 Chromium 인쇄 → `out/book.pdf`. 쪽 수·A4 크기 확인 |
| `check_layout.py` | 결과 HTML: 794×1123 크기, 넘침, `[[`·`]]`, 가짜 번호, KaTeX 오류, 수식 기호(`\frac`·`$`), 순서·쪽 번호 연속 검사 |
| `report.py` | 로그 → `out/report.md` (요약, AI 수정 목록, 구성·비율·행동 영역·난도, 문제은행, 판면) |
| `mathval.py` | LaTeX 정답 → sympy 비교 |
| `verify_runner.py` | verify 코드 별도 프로세스 실행 (30초 제한) |
| `common.py` | 설정·경로·로그·브라우저 실행 |
| `schemas.py` | 스키마 검증 |

## 사용자 응답

간결하게 작성.
