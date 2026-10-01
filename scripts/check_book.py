"""book.json 규칙 검사"""
from __future__ import annotations

from collections import Counter, defaultdict

from scripts import check_source
from scripts.check_created import CTRL_RE, LITERAL_NL_MSG, LITERAL_NL_RE, banned_hits, body_hash, ctrl_msg
from scripts.common import Context, Log, is_created_id, is_textbook_id
from scripts.schemas import validate

SKIP_KEYS = {"ref", "theme", "verify", "concept_ids", "difficulty"}


def iter_texts(node, where=""):
    """book.json 안의 AI 작성 텍스트 (그림 명세는 caption·라벨만)"""
    if isinstance(node, dict):
        is_fig = "x" in node and "y" in node and any(k in node for k in ("fns", "fn", "points", "polygons", "param", "shade"))
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            if is_fig and k not in ("caption",):
                continue
            yield from iter_texts(v, f"{where}/{k}" if where else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from iter_texts(v, f"{where}/{i}")
    elif isinstance(node, str):
        yield where, node


def writing_warnings(d: dict) -> list[str]:
    """WRITING.md(교과서형) 분량 규격 — 어기면 경고"""
    c, st, sr = d["concept"], d["strategy"], d["sign_reading"]
    if not c.get("sections"):
        return ["기존형 개념(비유) — 새 교재는 교과서형(concept.sections)으로 쓴다 (WRITING.md)"]
    out = []
    if len(c["sections"]) != 2:
        out.append(f"개념 소제목 {len(c['sections'])}개 (규격 2개)")
    for k, name in (("card", "개념 정리"), ("banner", "한 줄 요약"), ("example", "확인 예제")):
        if not c.get(k):
            out.append(f"{name}({k}) 없음")
    if len(c.get("map") or []) != 5 or any(not x.get("f") for x in c.get("map") or []):
        out.append("개념 지도는 5행, 행마다 '식으로 쓰면'(f)까지")
    tools = st.get("tools") or []
    if len(tools) != 3 or any(not (t.get("eq") and t.get("when")) for t in tools):
        out.append("실전 개념은 3개, 개념마다 eq·when까지")
    pts = sr["points"]
    if len(pts) != 3 or any(not isinstance(x, dict) or not x.get("title") for x in pts):
        out.append("문항 분석 요점은 3개, {title, text}로")
    return out


def day_refs(d: dict) -> list[str]:
    return [d["first_pitch"]["ref"]] + [p["ref"] for p in d["practice"]]


def check_appendix(app: dict | None, ctx: Context, log: Log) -> None:
    """계산 연습 부록: 검문 통과(verified·해시 일치)한 calc_type 창작만, 부록 안 중복 금지"""
    if not app:
        return
    seen = Counter()
    lo, hi = ctx.config.get("appendix", {}).get("per_type", [1, 99])
    rec_n = ctx.config.get("appendix", {}).get("per_type_recommended", 0)
    for ti, ty in enumerate(app["types"], 1):
        w = f"부록 유형 {ti} {ty['title']}"
        if not lo <= len(ty["refs"]) <= hi:
            log.error(w, f"문항 {len(ty['refs'])}개 (유형당 {lo}~{hi})")
        elif len(ty["refs"]) < rec_n:
            log.warn(w, f"문항 {len(ty['refs'])}개 — 유형당 {rec_n}개 이상이 목표")
        for ref in ty["refs"]:
            seen[ref] += 1
            e = ctx.created.get(ref)
            if not e:
                log.error(f"{w} {ref}", "문제은행(work/created)에 없는 창작 id")
                continue
            rec = e["rec"]
            rv = rec.get("review") or {}
            if rec.get("status") != "verified" or rv.get("hash") != body_hash(rec):
                log.error(f"{w} {ref}", "검문을 통과하지 않은 창작 (python run.py created)")
            if not rec.get("calc_type"):
                log.error(f"{w} {ref}", "부록에는 calc_type이 있는 계산 연습 창작만 쓴다")
            elif rec["calc_type"] != ty["title"]:
                log.warn(f"{w} {ref}", f"calc_type '{rec['calc_type']}'과 유형 이름이 다름")
            if rec.get("figure"):
                log.warn(f"{w} {ref}", "부록 쪽은 짧은 계산 위주 — 그림 문항은 피할 것")
    for ref, n in seen.items():
        if n > 1:
            log.error(f"부록 {ref}", f"부록 안에서 {n}번 중복")


def run(ctx: Context) -> Log:
    log = Log("check_book")
    cfg = ctx.config
    book = ctx.book

    errs = validate("book", book)
    for m in errs:
        log.error("스키마", m)
    if errs:
        return log

    if book["week"] > book["total_weeks"]:
        log.error("week", f"week {book['week']} > total_weeks {book['total_weeks']}")

    # ---- DAY 순서·테마 연속
    days = book["days"]
    nums = [d["day"] for d in days]
    if len(set(nums)) != len(nums) or nums != sorted(nums):
        log.error("days", f"DAY 번호는 겹치지 않고 오름차순이어야 함: {nums}")
    seen_theme_end = {}
    prev = None
    for d in days:
        th = d["theme"]
        if th != prev and th in seen_theme_end:
            log.error(f"DAY {d['day']}", f"테마 {th}의 DAY가 연속되지 않음")
        seen_theme_end[th] = d["day"]
        prev = th

    # ---- 한 권 = 한 과목의 1주 분량 (특강은 여러 과목)
    special = bool(book.get("special"))
    for d in days if not special else []:
        t = ctx.themes.get(d["theme"])
        if t and t["subject"] != book["subject_label"]:
            log.error(f"DAY {d['day']}", f"테마 {d['theme']}({t['subject']})가 이 권의 과목 {book['subject_label']}과 다름 — 한 권에는 한 과목만")
    for d in days:
        for msg in writing_warnings(d):
            log.warn(f"DAY {d['day']}", msg)

    uses = Counter()
    theme_stats = defaultdict(lambda: {"days": 0, "problems": 0, "past": 0, "created": 0, "textbook": 0})
    tb_examples = defaultdict(int)
    behaviors = Counter()
    difficulties = Counter()
    hard = 0
    figures = book.get("figures") or {}

    for d in days:
        w = f"DAY {d['day']}"
        th = d["theme"]
        t = ctx.themes.get(th)
        if not t:
            log.error(w, f"테마 {th}가 themes.json에 없음")
            continue
        if len(d["title"]) > 24:
            log.warn(w, f"챕터 제목 {len(d['title'])}자 — 헤더에서 잘릴 수 있음(24자 이하 권장)")
        cands = set(t["problem_ids"]) | set(t.get("related_ids") or [])
        refs = day_refs(d)
        reasons = {p["ref"]: p.get("reason") for p in d["practice"]}
        reuse_notes = {p["ref"]: p.get("reuse_note") for p in d["practice"]}
        reuse_notes[d["first_pitch"]["ref"]] = d["first_pitch"].get("reuse_note")
        ts = theme_stats[th]
        ts["days"] += 1

        for i, ref in enumerate(refs, 1):
            where = f"{w} #{i} {ref}"
            uses[ref] += 1
            ts["problems"] += 1
            if is_created_id(ref):
                ts["created"] += 1
                e = ctx.created.get(ref)
                if not e:
                    log.error(where, "문제은행(work/created)에 없는 창작 id")
                    continue
                rec = e["rec"]
                rv = rec.get("review") or {}
                if rec.get("status") != "verified" or rv.get("hash") != body_hash(rec):
                    log.error(where, "검문을 통과하지 않은 창작 (python run.py created)")
                if rec.get("calc_type"):
                    log.error(where, f"계산 연습 부록 전용 창작(calc_type={rec['calc_type']}) — DAY 연습에는 쓰지 않는다")
                if rec.get("theme") != th and not reuse_notes.get(ref):
                    log.error(where, f"다른 테마({rec.get('theme')}) 창작을 쓰려면 reuse_note 필요")
                behaviors[rec.get("behavior")] += 1
            elif is_textbook_id(ref):
                ts["textbook"] += 1
                e = ctx.source.get(ref)
                if not e:
                    log.error(where, "교재 판독 파일(work/source)에 없는 교재 id")
                    continue
                rec = e["rec"]
                rv = rec.get("review") or {}
                if rec.get("status") != "verified" or rv.get("hash") != check_source.body_hash(rec):
                    log.error(where, "검사를 통과하지 않은 교재 문항 (python run.py source)")
                if rec.get("subject") != t["subject"]:
                    log.error(where, f"과목 {rec.get('subject')}이 테마 과목 {t['subject']}과 다름")
                if rec.get("theme") != th and not reuse_notes.get(ref):
                    log.error(where, f"다른 테마({rec.get('theme')})로 분류된 교재 문항을 쓰려면 reuse_note 필요")
                if rec.get("figure_note") and not rec.get("figure"):
                    log.error(where, "그림이 있는 교재 문항 — 판독 파일에 figure 명세 필요")
                if i == 1:
                    tb_examples[th] += 1
                behaviors[rec.get("behavior")] += 1
            else:
                ts["past"] += 1
                r = ctx.db.get(ref)
                if not r:
                    log.error(where, "data/problems에 없는 기출 id")
                    continue
                if ref in ctx.excluded:
                    log.error(where, "excluded.json에 있는 기출")
                y0, y1 = cfg["sources"]["years"]
                if not (y0 <= r["source"]["year"] <= y1) or r["source"]["points"] != cfg["points"]["past"]:
                    log.error(where, "기출 범위(22~27학년도, 4점) 밖")
                if r["subject"] != t["subject"]:
                    log.error(where, f"과목 {r['subject']}이 테마 과목 {t['subject']}과 다름")
                if ref not in cands:
                    if i > 1 and not reasons.get(ref):
                        log.error(where, f"테마 {th} 후보(problem_ids·related_ids) 밖 — practice.reason 필요")
                    else:
                        log.warn(where, f"테마 {th} 후보 밖 기출: {reasons.get(ref) or '(예제)'}")
                if ref not in t["problem_ids"] and not reuse_notes.get(ref):
                    log.error(where, "다른 테마의 기출을 쓰려면 reuse_note 필요")
                if r.get("figure") and ref not in figures:
                    log.error(where, f"그림이 있는 기출 — book.figures[{ref}] 그림 명세 필요 ({r['figure'].get('description', '')[:40]})")
                behaviors[r["behavior"]] += 1
                if r["source"]["number"] in cfg["hard_numbers"][r["subject"]]:
                    hard += 1
        for p in d["practice"]:
            difficulties[p["difficulty"]] += 1

        dup = [r for r, n in Counter(refs).items() if n > 1]
        if dup:
            log.error(w, f"같은 DAY 안 중복 문항 {dup}")

        # 유사 기출(SCOUTING)
        for s in d["sign_reading"]["scouting"]:
            if s["ref"] not in ctx.db:
                log.error(w, f"SCOUTING {s['ref']}가 data/problems에 없음")
            elif s["ref"] == d["first_pitch"]["ref"]:
                log.error(w, "SCOUTING에 예제 자신을 넣음")
            elif s["ref"] in ctx.excluded:
                log.error(w, f"SCOUTING {s['ref']}는 excluded")

        n = len(refs)
        for rp in d["replay"]:
            if not 1 <= rp["no"] <= n:
                log.error(w, f"REPLAY 번호 {rp['no']}가 1~{n} 밖")
        rows = [r["no"] for r in d["sign_book"].get("rows") or []]
        if any(not 1 <= x <= n for x in rows) or len(rows) != len(set(rows)):
            log.error(w, f"SIGN BOOK 행 번호 {rows} 오류(1~{n}, 중복 금지)")
        for ref, note in (d.get("notes") or {}).items():
            if ref not in refs:
                log.error(w, f"notes의 {ref}는 이 DAY 문항이 아님")
            if note.get("shortcut") and not note.get("verify"):
                log.error(w, f"notes[{ref}].shortcut에는 verify 필수")
        for cid in d["strategy"].get("concept_ids") or []:
            if cid not in ctx.concepts:
                log.error(w, f"개념 id {cid}가 concepts.json에 없음")
            elif cid.rsplit("-C", 1)[0] not in t["old_themes"]:
                log.warn(w, f"개념 {cid}는 테마 {th}의 기존 테마({', '.join(t['old_themes'])}) 밖")
        if not (d["strategy"].get("concept_ids") or d["strategy"].get("tools")):
            log.error(w, "STRATEGY 실전 개념이 비어 있음(concept_ids 또는 tools)")

    # ---- 교재 문항: 이 책의 테마로 분류된 교재 문항은 빠짐없이, 예제 자리는 교재 문항 우선
    lo, hi = cfg["textbook"]["examples_per_theme"]
    for th, s in theme_stats.items():
        tb_all = [rid for rid, e in ctx.source.items()
                  if e["rec"].get("theme") == th and e["rec"].get("status") == "verified"]
        if not tb_all:
            continue
        unused = [rid for rid in tb_all if uses[rid] == 0]
        if unused:
            log.warn(th, f"테마 {th}로 분류된 교재 문항 중 이 책에 안 쓴 것: {', '.join(unused)}")
        need = min(len(tb_all), s["days"], hi)
        if tb_examples[th] < need:
            log.warn(th, f"교재 문항 예제 {tb_examples[th]}개 — 교재 문항을 예제로 {need}개 쓰는 것이 원칙")

    # ---- 부록(계산 연습): 창작 문항만
    check_appendix(book.get("appendix"), ctx, log)

    # ---- 사용 횟수
    mx = cfg["reuse"]["max_uses"]
    for ref, n in uses.items():
        if n > mx:
            log.error(ref, f"책 전체 사용 {n}회 > {mx}회")

    # ---- 테마 구성
    plan, comp = cfg["theme_plan"], cfg["composition"]
    dlo, dhi = plan["special_days"] if special else plan["days"]
    plo, phi = plan["special_problems"] if special else plan["problems"]
    for th, s in theme_stats.items():
        if not dlo <= s["days"] <= dhi:
            log.error(th, f"DAY {s['days']}개 (테마당 {dlo}~{dhi})")
        if not plo <= s["problems"] <= phi:
            log.error(th, f"문항 {s['problems']}개 (테마당 {plo}~{phi}, 예제 포함)")
        if s["past"] < comp["past_min_per_theme"]:
            log.error(th, f"기출 {s['past']}개 (테마당 {comp['past_min_per_theme']}개 이상)")
        if s["problems"] and s["created"] / s["problems"] > comp["created_max_share_per_theme"]:
            log.error(th, f"창작 비중 {s['created'] / s['problems']:.0%} (테마당 {comp['created_max_share_per_theme']:.0%} 이하)")

    # ---- 텍스트
    for where, text in iter_texts(book):
        if text.count("$") % 2:
            log.error(where, "$ 짝이 맞지 않음")
        if LITERAL_NL_RE.search(text):
            log.error(where, LITERAL_NL_MSG)
        if CTRL_RE.search(text):
            log.error(where, ctrl_msg(text))
        hits = banned_hits(text, cfg)
        if hits:
            log.error(where, f"야구 용어 {hits} (코너 이름 외 금지)")
        if "<" in text and ">" in text and any(tag in text for tag in ("<div", "<span", "<p", "<br", "<b>")):
            log.error(where, "HTML 태그 금지 (내용 + LaTeX만)")

    past = sum(s["past"] for s in theme_stats.values())
    created = sum(s["created"] for s in theme_stats.values())
    textbook = sum(s["textbook"] for s in theme_stats.values())
    log.stats = {
        "days": len(days), "themes": len(theme_stats), "problems": past + created + textbook,
        "past": past, "created": created, "textbook": textbook,
        "past_ratio": round(past / (past + created + textbook), 3) if past + created + textbook else None,
        "hard_numbers": hard, "behavior": dict(behaviors), "difficulty": dict(difficulties),
        "theme_stats": {k: dict(v) for k, v in theme_stats.items()},
        "reused": {r: n for r, n in uses.items() if n > 1},
    }
    return log
