"""교재 판독 파일 검사 (work/source/{교재id}.json)

문항마다 형식·테마·유사 기출·정답 검산(verify)을 확인해 status=verified|draft를 기록한다.
내용 해시가 그대로고 이미 verified면 다시 실행하지 않는다.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from scripts.check_created import banned_hits
from scripts.common import Context, Log, content_hash, has_choices, now, read_json, write_json
from scripts.mathval import run_verify, same_value
from scripts.schemas import validate


def body_hash(rec: dict) -> str:
    return content_hash({k: v for k, v in rec.items() if k not in ("status", "review")})


def ai_texts(rec: dict):
    """AI가 쓴 글(금지어 검사 대상). 교재 본문은 원문이라 제외"""
    yield "first_judgment", rec.get("first_judgment") or ""
    sol = rec.get("solution") or {}
    for f in ("guide", "supplement", "skill_point"):
        yield f"solution/{f}", sol.get(f) or ""
    for i, s in enumerate(sol.get("solutions") or []):
        for j, st in enumerate(s.get("steps") or []):
            yield f"solution/solutions/{i}/steps/{j}", st.get("body", "")


def all_texts(rec: dict):
    yield "question", rec.get("question") or ""
    yield "condition", rec.get("condition") or ""
    for i, c in enumerate(rec.get("choices") or []):
        yield f"choices/{i}", c
    yield from ai_texts(rec)


def check_problem(rec: dict, book: dict, pages: int | None, ctx: Context) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    rid = rec["id"]
    if not rid.startswith(f"T-{book.get('id')}-"):
        errs.append(f"id는 T-{book.get('id')}-NNN 형식")
    if pages and rec["page"] > pages:
        errs.append(f"page {rec['page']} > PDF {pages}쪽")
    t = ctx.themes.get(rec["theme"])
    if not t:
        errs.append(f"테마 {rec['theme']}가 themes.json에 없음")
        return errs, warns
    if t["subject"] != rec["subject"]:
        errs.append(f"과목 {rec['subject']} ≠ 테마 {rec['theme']} 과목 {t['subject']}")

    # ---- 개념·유사 기출
    refs = (rec["solution"].get("concept_refs") or [])
    for cid in refs:
        if cid not in ctx.concepts:
            errs.append(f"개념 id {cid}가 solutions.json에 없음")
    if refs and not any(c.rsplit("-C", 1)[0] in t["old_themes"] for c in refs):
        warns.append(f"concept_refs가 테마 {rec['theme']}의 개념을 하나도 가리키지 않음 — 테마 분류 재확인")
    cands = set(t["problem_ids"]) | set(t.get("related_ids") or [])
    for pid in rec.get("similar") or []:
        if pid not in ctx.db:
            errs.append(f"similar {pid}가 db.json에 없음")
        elif pid in ctx.excluded:
            errs.append(f"similar {pid}는 excluded")
        elif ctx.db[pid]["subject"] != rec["subject"]:
            errs.append(f"similar {pid} 과목이 다름")
        elif pid not in cands:
            warns.append(f"similar {pid}는 테마 {rec['theme']} 후보 밖 (book에서 쓰려면 reason 필요)")
    if not rec.get("similar"):
        warns.append("similar(유사 기출)가 비어 있음 — 큐레이션이 테마 후보로만 채워진다")

    # ---- 정답 형식
    ans = rec["answer"]
    if has_choices(rec):
        if not 1 <= int(ans) <= 5:
            errs.append(f"객관식 정답 {ans}은 1~5")
        if not rec.get("answer_value"):
            errs.append("객관식은 answer_value 필수")
    elif rec.get("answer_value") and not same_value(rec["answer_value"], ans):
        errs.append("단답형 answer_value가 answer와 다름")
    if rec.get("answer_source") == "AI 풀이":
        warns.append("교재 정답지 없이 AI 풀이로 정한 정답 — verify 두 경로(skill·standard) 권장")

    # ---- 텍스트
    for where, text in all_texts(rec):
        if text.count("$") % 2:
            errs.append(f"{where}: $ 짝이 맞지 않음")
    for where, text in ai_texts(rec):
        hits = banned_hits(text, ctx.config)
        if hits:
            errs.append(f"{where}: 야구 용어 {hits}")

    # ---- 그림
    if rec.get("figure"):
        from scripts.render_figs import render_svg
        try:
            render_svg(rec["figure"])
        except Exception as e:  # noqa: BLE001
            errs.append(f"그림 명세 오류: {e}")
    elif rec.get("figure_note"):
        warns.append("그림 명세가 없음(figure_note만) — 교재에 쓰면 그림 대신 메모가 찍힌다")

    # ---- verify
    target = rec.get("answer_value") if has_choices(rec) else ans
    res = run_verify(rec["verify"], ["skill", "standard", "unique"], ctx.config["created"]["verify_timeout_sec"])
    errors = res.get("errors", {})
    for k, m in errors.items():
        if k in ("standard", "unique") and m == "함수가 정의되지 않음":
            continue  # 선택 함수
        errs.append(f"verify {k}: {m}")
    r = res.get("results", {})
    for k in ("skill", "standard"):
        if k in r and not same_value(r[k], target):
            errs.append(f"verify {k}()={r[k]} ≠ 정답 {target}")
    if "unique" in r:
        u = r["unique"] if isinstance(r["unique"], list) else [r["unique"]]
        if len(u) != 1 or not same_value(u[0], target):
            errs.append(f"unique()={u} — 답이 정답 하나가 아님")
    if rec.get("answer_source") == "AI 풀이" and "standard" not in r:
        warns.append("AI 풀이 정답인데 standard()가 없음")
    return errs, warns


def run(ctx: Context, recheck: bool = False) -> Log:
    log = Log("check_source")
    files = sorted(ctx.source_dir.glob("*.json")) if ctx.source_dir.exists() else []
    ids = Counter()
    status = Counter()
    by_theme = defaultdict(list)
    books = []
    for f in files:
        data = read_json(f)
        errs = validate("source", data)
        if errs:
            for m in errs:
                log.error(f.name, f"스키마 {m}")
            continue
        book = data["book"]
        if f.stem != book["id"]:
            log.error(f.name, f"파일 이름은 {book['id']}.json 이어야 함")
        pages_json = ctx.source_dir / book["id"] / "pages.json"
        pages = len(read_json(pages_json)["pages"]) if pages_json.exists() else None
        changed = False
        for rec in data["problems"]:
            ids[rec["id"]] += 1
            h = body_hash(rec)
            rv = rec.get("review") or {}
            if not recheck and rec.get("status") == "verified" and rv.get("hash") == h and not rv.get("errors"):
                status["verified"] += 1
                by_theme[rec["theme"]].append(rec["id"])
                continue
            e, w = check_problem(rec, book, pages, ctx)
            rec["status"] = "draft" if e else "verified"
            rec["review"] = {"checked_at": now(), "hash": h, "errors": e, "warnings": w}
            changed = True
            status[rec["status"]] += 1
            if not e:
                by_theme[rec["theme"]].append(rec["id"])
            for m in e:
                log.error(rec["id"], m)
            for m in w:
                log.warn(rec["id"], m)
        if changed:
            write_json(f, data)
        books.append({"id": book["id"], "title": book["title"], "problems": len(data["problems"]), "pages": pages})
    for rid, n in ids.items():
        if n > 1:
            log.error(rid, f"같은 id가 {n}번")
    log.stats = {"books": books, "problems": sum(ids.values()), "verified": status["verified"],
                 "draft": status["draft"], "by_theme": {k: v for k, v in sorted(by_theme.items())}}
    return log
