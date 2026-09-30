---
globs:
  - "run.py"
  - "scripts/**"
---

# 실행 명령어

## 기본 사용법

```bash
pip install -r requirements.txt
python -m playwright install chromium    # 처음 한 번만

python run.py pages --pdf 교재.pdf --id KB1 --title "교재 이름"   # PDF 판독용 변환
python run.py title --id KB1 --title "교재 이름"                   # 출처 표기 변경
python run.py source          # 교재 판독 검사 + 큐레이션
python run.py created         # 창작 문제은행 검문만
python run.py                 # 전체: validate → created → source → check → verify → figs → build → layout → pdf → report
python run.py check           # 검사만 (조판 없이)
python run.py build           # 조판만: figs → build → layout → pdf → report
python run.py <단계>          # validate | created | check | verify | figs | layout | pdf | report
python -m unittest discover tests       # 테스트
```

## 옵션

```bash
python run.py \
  --book PATH                 # 다른 book.json 경로
  --created DIR               # 다른 창작 문제은행 폴더
  --source DIR                # 다른 교재 판독 폴더
  --out DIR                   # 다른 출력 폴더
  --recheck                   # 창작·교재 전체 재검사
  --force                     # 검사 오류가 있어도 조판
```

## 결과

- `out/book.html`: 한 파일(KaTeX 글꼴 내장)
- `out/book.pdf`: A4 프린트(한 쪽씩)
- `out/report.md`: 검사 결과 및 AI 수정 목록
- `out/excluded.json`, `out/pages.json`, `out/logs/*.json`: 로그
- 검사 오류가 있으면 조판하지 않음 (`--force` 제외). 오류 시 종료 코드 1.

## 판면 측정

템플릿의 웹 글꼴(Google Fonts)을 불러와 쪽 계산. 글꼴 불러오기 실패 시 경고만 남기고 대체 글꼴 사용. 그 밖의 외부 요청(CDN 등)은 모두 차단.
