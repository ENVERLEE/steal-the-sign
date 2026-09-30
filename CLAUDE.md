# STEAL THE SIGN : KICE — 교재 제작 파이프라인

## 목표
수능 수학 교재(HTML) 제작 파이프라인 중 **AI가 필요 없는 부분을 CLI 스크립트로 만든다.**
거창한 앱·서버·GUI 금지. 단순한 Python 스크립트 + `run.py`. Windows·macOS·Linux 모두에서 같은 명령으로 실행된다.

교재의 목적: 테마별 **실전개념(스킬)을 드릴링**해서 그 테마는 무조건 맞히게 하는 자습용 교재. 해설은 과외받듯 이해되고 개념 보충이 되는 수준이어야 하며, 비효율적 단순계산 풀이를 지양한다.

## 역할 분담
- **AI(채팅)**: 올린 교재 PDF 판독(OCR)·테마 분류·유사 기출 선정·해설, 창작문항, 교재 글(개념·실전 개념·분석·오답 진단 — `WRITING.md` 규격), 그림 명세 → `work/source/`(교재 판독), `work/created/`(창작 문제은행), `work/book.json`(교재 구성)
- **스크립트**: 원천 검증, 창작 검문, book.json 규칙 검사, 정답 검산, 그림 렌더링, 수식 조판, 템플릿 채우기, 판면 점검, 보고서
- **사람 승인 단계 없음.** 스크립트 검문을 통과한 창작(`verified`)은 바로 교재에 쓸 수 있다.
- **AI API 호출 금지**: 스크립트는 Claude API 등 어떤 AI API도 호출하지 않는다(API 키·SDK 의존성 추가 금지). AI 작업은 모두 채팅 세션에서 하고, 스크립트는 그 결과를 검사·조판만 한다.

## 빠른 시작
```
python run.py pages --pdf 교재.pdf --id KB1 --title "교재 이름"   # PDF → 판독용 이미지·텍스트
python run.py source          # 교재 판독 검사 + 큐레이션 초안
python run.py created         # 창작 문제은행 검문
python run.py                 # 전체 파이프라인
python run.py check           # 검사만 (조판 제외)
python run.py build           # 조판만
python -m unittest discover tests       # 테스트
```

상세 문서:
- [cli.md](.claude/rules/cli.md): 전체 실행 명령 및 옵션
- [ai-workflow.md](.claude/rules/ai-workflow.md): AI 작업 순서 (일반 교재·특강)
- [schema-reference.md](.claude/rules/schema-reference.md): db·themes·solutions·book·figure 스키마
- [created-problems.md](.claude/rules/created-problems.md): 창작 문항 규칙
- [source-reading.md](.claude/rules/source-reading.md): 교재 판독 파일
- [book-validation.md](.claude/rules/book-validation.md): book.json 검사 항목
- [solution-writing.md](.claude/rules/solution-writing.md): 해설 규칙
- [layout-rules.md](.claude/rules/layout-rules.md): 판면 규칙
- [development.md](.claude/rules/development.md): 개발 규칙 및 스크립트 목록

## 폴더 구조 (참고)
```
run.py, requirements.txt, WRITING.md
data/: db.json, themes.json, solutions.json, strategy_notes.json, config.json, STS_template.html, STS_ext.html
work/: book.json, created/{테마}/, source/{교재id}.json, source/{교재id}/pages/
schema/, scripts/, samples/, tests/, vendor/katex/, out/
```
참고: data/README.md(DB 스키마), solutions/SPEC.md(해설 작성), pilot/pilot_v2.json(해설 모범)
