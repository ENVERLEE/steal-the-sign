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

import json
import re
from pathlib import Path

from scripts.common import Context, Log, read_json, write_json

ALIASES = {
    "name": ("name", "exam", "모의고사_이름", "모의고사"),
    "number": ("number", "no", "num", "q", "문항", "번호", "문항_번호"),
    "question": ("question", "text", "body", "문제", "본문", "문제_텍스트"),
    "choices": ("choices", "options", "선지"),
    "answer": ("answer", "correct", "정답"),
    "my_answer": ("my_answer", "mine", "내답", "내 답"),
    "reason": ("reason", "why", "cause", "틀린이유", "틀린 이유", "틀린_이유"),
    "tags": ("tags", "pattern", "patterns", "유형"),
    "calc_error": ("calc_error", "calc", "계산실수", "계산_폭주_및_시간낭비"),
    "concept": ("concept", "관련_단원_및_개념"),
    "missed": ("missed", "놓친_조건"),
    "best": ("best", "최적의_풀이_방향"),
    "intent": ("intent", "출제자_의도"),
    "subject": ("subject", "과목"),
    "condition": ("condition", "조건"),
}
LIST_KEYS = ("problems", "wrong", "questions", "items", "wrong_problems", "오답", "오답_노트")
PATTERN_KEYS = ("patterns", "calc_patterns", "summary", "패턴", "요약", "종합_분석")
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


INCOMPLETE_RE = re.compile(r"\.\.\.|…|문제$|문항$|(?:구하는|관련|추론)\s*(?:문제|문항)")


def parse_number(raw, subj):
    """'확률과 통계 27번' → ('27', '확률과 통계'), '21번, 22번' → '21, 22'"""
    text = str(raw)
    for k, v in SUBJECTS.items():
        if text.replace(" ", "").startswith(k):
            subj = subj or v
            text = text.replace(" ", "")[len(k):]
            break
    return re.sub(r"번", "", text).strip(), subj


def incomplete(q: str) -> bool:
    return bool(INCOMPLETE_RE.search(q.strip())) or len(q.strip()) < 25


def run(ctx: Context, json_path: str | None = None, book_id: str | None = None, title: str | None = None) -> Log:
    """--id·--title을 주면 한 권으로, 안 주면 모의고사_이름마다 한 권(MK1, MK2, …; 표기 = 모의고사_이름)"""
    log = Log("mock_import")
    if not json_path:
        log.error("mock", 'python run.py mock --json 분석.json [--id MK1 --title "출처 표기"]')
        return log
    src = Path(json_path)
    if not src.exists():
        log.error("mock", f"{src} 가 없음")
        return log
    single = bool(book_id or (title or "").strip())
    if single and (not book_id or not (title or "").strip()):
        log.error("mock", "--id와 --title은 함께 준다 (생략하면 모의고사_이름별로 나눔)")
        return log
    if book_id and not re.fullmatch(r"[A-Za-z0-9]{1,8}", book_id):
        log.error("mock", f"--id는 영문·숫자 1~8자: {book_id}")
        return log
    text = src.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # LaTeX 역슬래시(\\pi, \\theta)를 한 개만 쓴 JSON: 이미 짝지은 \\\\·\\"는 두고 나머지를 문자 그대로 살린다
        fixed = re.sub(r'\\\\|\\(?!["/])', lambda m: m.group(0) if m.group(0) == "\\\\" else "\\\\", text)
        data = json.loads(fixed)
        log.warn("JSON", "역슬래시 하나짜리 LaTeX(\\pi 등)가 있어 문자 그대로 살려 읽음 — 원본 JSON은 \\\\pi로 써야 함")
    items, patterns = split_input(data)

    books: dict[str, dict] = {}   # 표기 -> {id, problems, items}
    for i, it in enumerate(items, 1):
        name = (title.strip() if single else pick(it, "name")) or None
        if not name:
            log.warn(f"#{i}", "모의고사 이름이 없어 건너뜀")
            continue
        if name not in books:
            bid = book_id.upper() if single else f"MK{len(books) + 1}"
            books[name] = {"id": bid, "problems": [], "items": []}
        b = books[name]
        b["items"].append(it)
        q = pick(it, "question")
        raw_num = pick(it, "number")
        if not q or raw_num is None:
            log.warn(f"#{i}", "번호 또는 본문이 없어 문항으로 만들지 않음 — 본문은 사용자에게 다시 받아야 함")
            continue
        num, subj = parse_number(raw_num, pick(it, "subject"))
        subj = SUBJECTS.get(str(subj).replace(" ", ""), subj) if subj else None
        ch = pick(it, "choices")
        rid = f"T-{b['id']}-{len(b['problems']) + 1:03d}"
        rec = {
            "id": rid, "number": num, "subject": subj, "question": q,
            "condition": pick(it, "condition"),
            "choices": ch if isinstance(ch, list) else None,
            "answer": str(pick(it, "answer") or ""),
            "answer_source": "교재 정답" if pick(it, "answer") else "AI 풀이",
            "points": 4,
            "mistake": {k: v for k, v in {
                "my_answer": pick(it, "my_answer"), "reason": pick(it, "reason"), "concept": pick(it, "concept"),
                "missed": pick(it, "missed"), "best": pick(it, "best"), "intent": pick(it, "intent"),
                "tags": pick(it, "tags"), "calc_error": pick(it, "calc_error"),
            }.items() if v not in (None, "")},
            "text_complete": not incomplete(q),
        }
        if not rec["text_complete"]:
            log.warn(rid, f"{name} {num}번: 본문이 요약·생략된 것으로 보임 — 예제로 쓰려면 원문이 필요 (진단 자료로만 사용)")
        if not subj:
            log.warn(rid, "과목이 없음 — AI가 채움")
        b["problems"].append(rec)

    mock_dir = ctx.source_dir.parent / "mock"
    for name, b in books.items():
        write_json(ctx.source_dir / b["id"] / "pages.json", {"book_id": b["id"], "title": name, "pages": []})
        write_json(mock_dir / f"{b['id']}_draft.json",
                   {"book": {"id": b["id"], "title": name, "mock": True}, "problems": b["problems"]})
        write_json(mock_dir / f"{b['id']}_analysis.json", {"book_id": b["id"], "title": name, "problems": b["items"]})
    write_json(mock_dir / "patterns.json", patterns)
    total = sum(len(b["problems"]) for b in books.values())
    full = sum(1 for b in books.values() for p in b["problems"] if p["text_complete"])
    log.stats = {"books": {b["id"]: n for n, b in books.items()}, "problems": total, "complete_text": full}
    for name, b in books.items():
        print(f"   {b['id']} {name}: {len(b['problems'])}문항")
    print(f"   본문이 온전한 문항 {full}/{total} → {mock_dir}")
    return log
