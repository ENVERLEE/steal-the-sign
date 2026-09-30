"""실전모의고사 오답 분석 JSON → 교재 판독 뼈대 (AI가 이어서 채운다)

    python run.py mock --json 분석.json --id MK1 --title "실모 제1회"

입력 JSON: 틀린 문제 목록(최상위 리스트, 또는 `problems`·`wrong`·`questions`·`items` 배열)과
선택적으로 전체 패턴(`patterns`·`calc_patterns`·`summary`).
문항 필드 이름은 아래 별칭 중 아무거나 인식한다.

  번호 number|no|num|q|문항|번호   본문 question|text|body|문제   선지 choices|options|선지
  정답 answer|correct|정답        내 답 my_answer|mine|내답         이유 reason|why|cause|틀린이유
  패턴 tags|pattern|patterns|유형 계산실수 calc_error|calc|계산실수   과목 subject|과목

출력
  work/source/{ID}/pages.json   출처 표기(사용자 입력) — 쪽 없음
  work/mock/{ID}_draft.json     source 뼈대 (theme·first_judgment·solution·verify 등은 AI가 채워 work/source/{ID}.json 로)
  work/mock/{ID}_analysis.json  틀린 이유·패턴 원본 (REPLAY·DUGOUT NOTE·부록 유형 선정 자료)
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.common import Context, Log, read_json, write_json

ALIASES = {
    "number": ("number", "no", "num", "q", "문항", "번호"),
    "question": ("question", "text", "body", "문제", "본문"),
    "choices": ("choices", "options", "선지"),
    "answer": ("answer", "correct", "정답"),
    "my_answer": ("my_answer", "mine", "내답", "내 답"),
    "reason": ("reason", "why", "cause", "틀린이유", "틀린 이유"),
    "tags": ("tags", "pattern", "patterns", "유형"),
    "calc_error": ("calc_error", "calc", "계산실수"),
    "subject": ("subject", "과목"),
    "condition": ("condition", "조건"),
}
LIST_KEYS = ("problems", "wrong", "questions", "items", "wrong_problems", "오답")
PATTERN_KEYS = ("patterns", "calc_patterns", "summary", "패턴", "요약")
SUBJECTS = {"수학Ⅰ": "수학Ⅰ", "수학1": "수학Ⅰ", "수1": "수학Ⅰ", "수학Ⅱ": "수학Ⅱ", "수학2": "수학Ⅱ", "수2": "수학Ⅱ",
            "확률과 통계": "확률과 통계", "확통": "확률과 통계", "확률과통계": "확률과 통계"}


def pick(d: dict, field: str):
    for k in ALIASES[field]:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def split_input(data) -> tuple[list[dict], object]:
    if isinstance(data, list):
        return data, None
    items = next((data[k] for k in LIST_KEYS if isinstance(data.get(k), list)), None)
    if items is None:
        raise ValueError(f"틀린 문제 목록을 찾지 못함 (최상위 리스트 또는 {'/'.join(LIST_KEYS)} 배열)")
    patterns = {k: data[k] for k in PATTERN_KEYS if k in data}
    return items, patterns or None


def run(ctx: Context, json_path: str | None = None, book_id: str | None = None, title: str | None = None) -> Log:
    log = Log("mock_import")
    if not json_path or not book_id or not (title or "").strip():
        log.error("mock", 'python run.py mock --json 분석.json --id MK1 --title "출처 표기(사용자가 정한 이름)"')
        return log
    bid = book_id.upper()
    if not re.fullmatch(r"[A-Z0-9]{1,8}", bid):
        log.error("mock", f"--id는 영문 대문자·숫자 1~8자: {book_id}")
        return log
    src = Path(json_path)
    if not src.exists():
        log.error("mock", f"{src} 가 없음")
        return log
    items, patterns = split_input(read_json(src))

    problems, skipped = [], 0
    for i, it in enumerate(items, 1):
        q = pick(it, "question")
        num = pick(it, "number")
        if not q or num is None:
            log.warn(f"#{i}", "번호 또는 본문이 없어 건너뜀 — 본문은 사용자에게 다시 받아야 함")
            skipped += 1
            continue
        subj = pick(it, "subject")
        ch = pick(it, "choices")
        rec = {
            "id": f"T-{bid}-{len(problems) + 1:03d}",
            "number": str(num),
            "subject": SUBJECTS.get(str(subj).replace(" ", ""), subj) if subj else None,
            "question": q,
            "condition": pick(it, "condition"),
            "choices": ch if isinstance(ch, list) else None,
            "answer": str(pick(it, "answer") or ""),
            "answer_source": "교재 정답" if pick(it, "answer") else "AI 풀이",
            "points": 4,
            "mistake": {k: v for k, v in {
                "my_answer": pick(it, "my_answer"), "reason": pick(it, "reason"),
                "tags": pick(it, "tags"), "calc_error": pick(it, "calc_error"),
            }.items() if v not in (None, "")},
            "raw": it,
        }
        if not rec["subject"]:
            log.warn(rec["id"], "과목이 없음 — AI가 채움")
        if not rec["answer"]:
            log.warn(rec["id"], "정답이 없음 — AI 풀이로 정하고 verify standard()도 작성")
        problems.append(rec)

    mock_dir = ctx.source_dir.parent / "mock"
    write_json(ctx.source_dir / bid / "pages.json", {"book_id": bid, "title": title.strip(), "pages": []})
    write_json(mock_dir / f"{bid}_draft.json",
               {"book": {"id": bid, "title": title.strip(), "mock": True}, "problems": problems})
    write_json(mock_dir / f"{bid}_analysis.json", {"book_id": bid, "patterns": patterns, "problems": items})
    log.stats = {"book_id": bid, "problems": len(problems), "skipped": skipped, "draft": str(mock_dir / f"{bid}_draft.json")}
    print(f"   {len(problems)}문항 → {mock_dir / (bid + '_draft.json')}")
    return log
