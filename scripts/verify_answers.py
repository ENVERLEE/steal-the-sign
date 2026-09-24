"""정답 검산

- 기출: DB 정답 = solutions.json 정답, 정답 선지 값 일치. db.check.needs_review가 있으면 경고.
- 기출에 새 숏컷(notes[ref].shortcut)을 달면 그 verify의 skill()이 정답 값과 같아야 한다.
- 창작·교재 문항: verify(skill·standard·unique)를 다시 실행해 정답과 맞춘다(교재는 skill만 필수).
"""
from __future__ import annotations

from scripts.check_book import day_refs
from scripts.common import Context, Log, has_choices, is_created_id, is_textbook_id
from scripts.mathval import run_verify, same_value


def target_value(rec: dict) -> str:
    return str(rec.get("answer_value") if has_choices(rec) else rec["answer"])


def run(ctx: Context) -> Log:
    log = Log("verify_answers")
    timeout = ctx.config["created"]["verify_timeout_sec"]
    checked = {"past": 0, "created": 0, "textbook": 0, "shortcut": 0}
    done = set()

    for d in ctx.book.get("days") or []:
        notes = d.get("notes") or {}
        for ref in day_refs(d):
            where = f"DAY {d['day']} {ref}"
            if is_created_id(ref) or is_textbook_id(ref):
                e = (ctx.created if is_created_id(ref) else ctx.source).get(ref)
                if not e or ref in done:
                    continue
                done.add(ref)
                rec = e["rec"]
                res = run_verify(rec.get("verify", ""), ["skill", "standard", "unique"], timeout)
                for k, m in res.get("errors", {}).items():
                    if is_textbook_id(ref) and k in ("standard", "unique") and m == "함수가 정의되지 않음":
                        continue  # 교재 문항은 skill()만 필수
                    log.error(where, f"verify {k}: {m}")
                r = res.get("results", {})
                tv = target_value(rec)
                for k in ("skill", "standard"):
                    if k in r and not same_value(r[k], tv):
                        log.error(where, f"{k}()={r[k]} ≠ 정답 {tv} → needs_review")
                u = r.get("unique")
                if u is not None and (len(u) != 1 or not same_value(u[0], tv)):
                    log.error(where, f"유일성 실패 unique()={u} → needs_review")
                checked["created" if is_created_id(ref) else "textbook"] += 1
            else:
                rec = ctx.db.get(ref)
                if not rec:
                    continue
                if ref not in done:
                    done.add(ref)
                    st = ctx.study.get(ref) or {}
                    if str(st.get("answer")) != str(rec["answer"]):
                        log.error(where, f"풀이 정답 {st.get('answer')} ≠ DB 정답 {rec['answer']}")
                    if has_choices(rec):
                        if not same_value(rec["answer_value"], rec["choices"][int(rec["answer"]) - 1]):
                            log.error(where, "answer_value가 정답 선지 값과 다름")
                    if (rec.get("check") or {}).get("needs_review"):
                        log.warn(where, f"needs_review: {rec['check']['needs_review']}")
                    checked["past"] += 1
                note = notes.get(ref) or {}
                if note.get("verify"):
                    res = run_verify(note["verify"], ["skill"], timeout)
                    for k, m in res.get("errors", {}).items():
                        log.error(where, f"숏컷 verify {k}: {m}")
                    v = res.get("results", {}).get("skill")
                    if v is not None and not same_value(v, target_value(rec)):
                        log.error(where, f"새 숏컷 skill()={v} ≠ 정답 {target_value(rec)} → needs_review")
                    checked["shortcut"] += 1
    log.stats = checked
    return log
