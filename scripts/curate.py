"""교재 문항 → 테마별 큐레이션 초안 (out/curation.md, out/plan.json)

테마마다 2~3 DAY. 교재 문항이 예제(DAY마다 1개)가 되고, 남는 교재 문항과
유사 기출(교재 문항의 similar → 테마 problem_ids → related_ids 순)·통과한 창작이 연습 문항이 된다.
테마당 8~13문항, 기출 5개 이상, 창작 50% 이하를 맞추고, 모자라면 '창작 N개 더 필요'로 알린다.
AI는 plan.json의 문항 배정을 book.json에 옮기고 글(개념·분석·REPLAY 등)을 채운다.
"""
from __future__ import annotations

from collections import defaultdict

from scripts.common import Context, Log, source_label, write_json


def _short(text: str, n: int = 60) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def plan_theme(th: str, tb: list[dict], ctx: Context) -> dict:
    cfg = ctx.config
    t = ctx.themes[th]
    lo, hi = cfg["theme_plan"]["problems"]
    dlo, dhi = cfg["theme_plan"]["days"]
    past_min = cfg["composition"]["past_min_per_theme"]
    share = cfg["composition"]["created_max_share_per_theme"]

    n_days = max(dlo, min(dhi, len(tb)))
    examples = [r["id"] for r in tb[:n_days]]
    tb_practice = [r["id"] for r in tb[n_days:]]

    # 유사 기출 후보(순서 유지, 중복 제거)
    pool, seen = [], set()
    for src in [x for r in tb for x in (r.get("similar") or [])] + t["problem_ids"] + (t.get("related_ids") or []):
        if src in ctx.db and src not in ctx.excluded and src not in seen and ctx.db[src]["subject"] == t["subject"]:
            seen.add(src)
            pool.append(src)
    while len(examples) < n_days and pool:  # 교재 문항이 모자라면 기출 예제
        examples.append(pool.pop(0))

    notes = []
    past_examples = sum(1 for e in examples if not e.startswith("T-"))
    max_tb = hi - past_min                      # 기출 5개 자리를 남긴 교재 문항 한도
    tb_used = len(examples) - past_examples + len(tb_practice)
    if tb_used > max_tb:
        cut = tb_used - max_tb
        dropped, tb_practice = tb_practice[-cut:], tb_practice[:-cut]
        notes.append(f"교재 문항이 많아 {len(dropped)}개는 이 테마에 못 넣음: {', '.join(dropped)} → 다른 권·테마로")
        tb_used = max_tb
    textbook_n = tb_used
    # 기출: 5개 이상, 합계 10개 안팎, 최대 13개
    past_goal = max(past_min, 10 - tb_used) - past_examples
    past_n = max(0, min(len(pool), past_goal, hi - tb_used - past_examples))
    past = pool[:past_n]
    past_total = past_n + past_examples

    created_pool = sorted(rid for rid, e in ctx.created.items()
                          if e["rec"].get("theme") == th and e["rec"].get("status") == "verified")
    total = tb_used + past_total
    want_created = max(0, lo - total)
    created = created_pool[:want_created]
    total += len(created)
    if total and len(created) / total > share:
        notes.append("창작 비중이 50%를 넘음 — 기출을 늘릴 것")
    if total < lo:
        notes.append(f"문항 {total}개 < {lo} — 창작 {lo - total}개 더 필요 (python run.py created)")
    if past_total < past_min:
        notes.append(f"기출 {past_total}개 < {past_min} — related_ids 밖 기출을 reason과 함께 추가")

    # DAY 배분: 예제 1개씩. 연습은 예제와 가까운 DAY로 (similar 3점 + 겹치는 개념 1점씩), DAY 사이 수는 고르게
    days = [{"first_pitch": ex, "practice": [], "scouting": []} for ex in examples]
    rest = tb_practice + past + created
    cap = -(-len(rest) // len(days)) if days else 0
    scored = []
    for ref in rest:
        sc = [affinity(d["first_pitch"], ref, ctx) for d in days]
        scored.append((max(sc), ref, sc))
    for _, ref, sc in sorted(scored, key=lambda x: -x[0]):
        order_ = sorted(range(len(days)), key=lambda i: (-sc[i], len(days[i]["practice"])))
        i = next((i for i in order_ if len(days[i]["practice"]) < cap), order_[0])
        days[i]["practice"].append(ref)
    for d in days:  # 연습 순서: 교재 → 기출(번호 순) → 창작
        d["practice"].sort(key=lambda r: (0 if r.startswith("T-") else 2 if r.startswith("C-") else 1,
                                          ctx.db[r]["source"]["number"] if r in ctx.db else 0))
        ex = d["first_pitch"]
        rec = ctx.source[ex]["rec"] if ex.startswith("T-") else None
        sim = [x for x in (rec or {}).get("similar") or [] if x != ex]
        cand = sim + [x for x in pool if x != ex and x not in d["practice"]]
        d["scouting"] = list(dict.fromkeys(cand))[:2]
    return {"theme": th, "name": t["name"], "days": days, "textbook": [r["id"] for r in tb],
            "counts": {"textbook": textbook_n, "past": past_total, "created": len(created), "total": total},
            "notes": notes}


def concepts_of(ref: str, ctx: Context) -> set:
    if ref.startswith("T-"):
        return set(ctx.source[ref]["rec"]["solution"].get("concept_refs") or [])
    if ref.startswith("C-"):
        return set(ctx.created[ref]["rec"]["target"]["concept_ids"])
    return set((ctx.study.get(ref) or {}).get("concept_refs") or [])


def affinity(example: str, ref: str, ctx: Context) -> int:
    score = 0
    if example.startswith("T-") and ref in (ctx.source[example]["rec"].get("similar") or []):
        score += 3
    return score + len(concepts_of(example, ctx) & concepts_of(ref, ctx))


def run(ctx: Context) -> Log:
    log = Log("curate")
    by_theme = defaultdict(list)
    for rid, e in ctx.source.items():
        rec = e["rec"]
        if rec.get("status") == "verified":
            by_theme[rec["theme"]].append(rec)
        else:
            log.warn(rid, "검사를 통과하지 않아 큐레이션에서 뺌")
    if not by_theme:
        log.warn("curate", "검사를 통과한 교재 문항이 없음 (python run.py source)")
    order = list(ctx.themes)
    plans = []
    for th in sorted(by_theme, key=order.index):
        tb = sorted(by_theme[th], key=lambda r: (r["page"], r["id"]))
        p = plan_theme(th, tb, ctx)
        plans.append(p)
        for n in p["notes"]:
            log.warn(th, n)
    write_json(ctx.out_dir / "plan.json", {"themes": plans})

    L = ["# 교재 큐레이션 초안", "",
         "테마 순서대로 DAY를 잡는다. 문항 배정은 `out/plan.json`을 book.json에 옮기고, 글은 AI가 쓴다.", ""]
    day_no = 1
    for p in plans:
        c = p["counts"]
        L += [f"## {p['theme']} {p['name']}", "",
              f"교재 {c['textbook']} · 기출 {c['past']} · 창작 {c['created']} = {c['total']}문항, DAY {len(p['days'])}개", ""]
        for n in p["notes"]:
            L.append(f"> ⚠ {n}")
        if p["notes"]:
            L.append("")
        for d in p["days"]:
            L.append(f"**DAY {day_no}** 예제 {describe(d['first_pitch'], ctx)}")
            for ref in d["practice"]:
                L.append(f"- 연습 {describe(ref, ctx)}")
            if d["scouting"]:
                L.append(f"- SCOUTING 후보: {', '.join(d['scouting'])}")
            L.append("")
            day_no += 1
    (ctx.out_dir / "curation.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log.stats = {"themes": len(plans), "days": day_no - 1,
                 "problems": sum(p["counts"]["total"] for p in plans)}
    return log


def describe(ref: str, ctx: Context) -> str:
    if ref.startswith("T-"):
        e = ctx.source[ref]
        r = e["rec"]
        return f"`{ref}` 교재 {r['page']}쪽 {r['number']}번 — {_short(r['first_judgment'])}"
    if ref.startswith("C-"):
        r = ctx.created[ref]["rec"]
        return f"`{ref}` 창작 — {_short(r['target']['first_judgment'])}"
    r = ctx.db[ref]
    return f"`{ref}` {source_label(r)} — {_short(r['first_judgment'])}"
