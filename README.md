# steal-the-sign

STEAL THE SIGN : KICE — 수능 수학 자습용 교재(HTML) 제작 파이프라인.
AI가 필요 없는 단계(검증·검산·그림·조판·판면 점검)를 크로스플랫폼 Python CLI로 처리한다.

```
pip install -r requirements.txt
python -m playwright install chromium
python run.py            # work/book.json → out/book.html, out/report.md
python -m unittest discover tests
```

프로젝트 목적·데이터 형식·규칙은 [`CLAUDE.md`](CLAUDE.md) 참고.
