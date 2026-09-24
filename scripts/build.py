"""book.json + db.json + solutions.json + 문제은행 → out/book.html

1) 모델: DAY별 페이지 데이터(텍스트는 Math.rich로 HTML화, 수식은 자리표시)
2) KaTeX 일괄 조판 → 자리표시 채움
3) Playwright로 A4 판면을 실제로 재면서 흐르는 페이지(목차·REPLAY·정답표·해설)를 나눈다
4) 쪽 번호(표지=001)·목차 쪽수 확정 → 템플릿 채움 → 한 파일 HTML
"""
from __future__ import annotations

import html as H
import re

from scripts import render_figs
from scripts.check_book import day_refs
from scripts.common import (CIRCLED, Context, Log, answer_display, choice_text, has_choices, is_created_id,
                            launch_chromium, route_network, source_label, strip_tex, write_json)
from scripts.template import WEEK_TOKEN, load
from scripts.tex import Math, katex_css

CORNERS = ("THE SIGN", "FIRST PITCH", "PRACTICE", "DUGOUT NOTE", "SIGN BOOK")
STRUT = '<span style="display:inline-block;width:0;height:0;vertical-align:-24px"></span>'


def two(n: int) -> str:
    return f"{n:02d}"


CID = r"(?:수학Ⅰ|수학Ⅱ|확률과 통계)-\d{2}-C\d+"
PAREN_IDS = re.compile(r"\s?\((?:\s*(?:" + CID + r")\s*[,·]?)+\)")
IN_PAREN = re.compile(r"(\([^()]*?)\s*[,;]\s*(?:" + CID + r")(?:\s*[,·]\s*(?:" + CID + r"))*\s*\)")
BARE = re.compile(CID)


def clean_refs(text, concepts: dict):
    """해설 속 내부 개념 id 정리: (id)·(…, id)는 지우고, 문장 속 id는 「개념 이름」으로"""
    if not text or "-C" not in text:
        return text
    text = PAREN_IDS.sub("", text)
    text = IN_PAREN.sub(r"\1)", text)
    return BARE.sub(lambda m: f"「{concepts[m.group(0)]['name']}」" if m.group(0) in concepts else "", text)


# ---------------------------------------------------------------- 모델

class Model:
    def __init__(self, ctx: Context, math: Math, log: Log):
        self.ctx, self.m, self.log = ctx, math, log
        b = ctx.book
        self.book = {
            "week2": two(b["week"]), "total2": two(b["total_weeks"]),
            "year_label": H.escape(b["year_label"]), "subject_label": H.escape(b["subject_label"]),
            "weeks": [{"label": two(i), "now": i == b["week"]} for i in range(1, b["total_weeks"] + 1)],
        }
        self.days = [self.day(d) for d in b["days"]]

    # ---- 공통
    def r(self, text):
        return self.m.rich(clean_refs(text, self.ctx.concepts))

    def svg(self, spec, where):
        try:
            return render_figs.svg_for(spec, self.ctx)
        except Exception as e:  # noqa: BLE001
            self.log.error(where, f"그림 오류: {e}")
            return f'<div style="border:1px dashed #999;padding:8px;font-size:12px">그림 오류: {H.escape(str(e))}</div>'

    def concept_names(self, ids):
        return " · ".join(self.ctx.concepts[c]["name"] for c in ids if c in self.ctx.concepts)

    def source_of(self, ref, rec):
        return "STEAL THE SIGN 창작" if is_created_id(ref) else source_label(rec)

    def record(self, ref):
        if is_created_id(ref):
            return self.ctx.created[ref]["rec"]
        return self.ctx.db[ref]

    # ---- 문항
    def question(self, ref, no, difficulty, where):
        rec = self.record(ref)
        fig = None
        if is_created_id(ref):
            if rec.get("figure"):
                fig = self.svg(rec["figure"], where)
        else:
            spec = (self.ctx.book.get("figures") or {}).get(ref)
            if spec:
                fig = self.svg(spec, where)
            elif rec.get("figure"):
                self.log.error(where, "그림 명세(book.figures)가 없어 그림 설명으로 대신함")
                fig = ('<div style="border:1px dashed #111;padding:10px 14px;font-size:12.5px;max-width:420px">그림: '
                       + self.r(rec["figure"].get("description", "")) + "</div>")
        choices, cls = None, ""
        if has_choices(rec):
            # 분수 선지의 글자 상자가 .pad(아래 여백 0) 밖으로 3px쯤 나가 넘침으로 잡히므로 4px 여유를 준다
            choices = [{"label": CIRCLED[i],
                        "html": f'<span style="display:inline-block;padding-bottom:4px">{self.r(choice_text(c))}</span>'}
                       for i, c in enumerate(rec["choices"])]
            longest = max(len(strip_tex(c)) for c in rec["choices"])
            cls = "" if longest <= 9 else (" two" if longest <= 18 else " stack")
        return {
            # 마지막 줄의 큰 수식(Σ·분수)이 .pad 아래로 몇 px 나가지 않도록 줄 상자를 아래로 조금 늘리는 받침
            "no2": two(no), "text": self.r(rec["question"]) + STRUT, "cond": self.r(rec.get("condition")) or None,
            "fig": fig, "choices": choices, "choices_class": cls,
            "points": self.ctx.config["points"]["created" if is_created_id(ref) else "past"],
            "source": H.escape(self.source_of(ref, rec)), "kind": "창작" if is_created_id(ref) else "기출",
            "difficulty": H.escape(difficulty or ""),
        }

    def solution_item(self, ref, no, notes, reuse_note):
        rec = self.record(ref)
        sol = rec["solution"] if is_created_id(ref) else self.ctx.study[ref]
        note = notes.get(ref) or {}
        sols = sol.get("solutions") or []

        def steps(s):
            return "<br>".join(f"<b>{self.r(st['label'])}</b> {self.r(st['body'])}" for st in s.get("steps") or [])
        guide = f"<b>조건 번역</b> {self.r(sol['guide'])}<br>" if sol.get("guide") else ""
        if note.get("shortcut"):
            shortcut = self.r(note["shortcut"])
            standard = steps(sols[1]) if len(sols) > 1 else (steps(sols[0]) if sols else None)
        else:
            shortcut = guide + (steps(sols[0]) if sols else "")
            standard = steps(sols[1]) if len(sols) > 1 else None
        if note.get("tip"):
            tip = self.r(note["tip"])
        else:
            names = self.concept_names(sol.get("concept_refs") or [])
            tip = self.r((names + " — " if names else "") + (sol.get("skill_point") or ""))
        if reuse_note:
            tip += f"<br><b>이 테마에서</b> {self.r(reuse_note)}"
        error = self.r(note["error"]) if note.get("error") else (self.r(sol.get("supplement")) or None)
        return {"no2": two(no), "kind": "예제" if no == 1 else "연습", "source": H.escape(self.source_of(ref, rec)),
                "answer": H.escape(answer_display(rec)), "shortcut": shortcut, "fig": None,
                "standard": standard, "tip": tip or None, "error": error}

    # ---- DAY
    def day(self, d):
        ctx = self.ctx
        w = f"DAY {d['day']}"
        t = ctx.themes[d["theme"]]
        base = {"day2": two(d["day"]), "title": self.r(d["title"])}
        refs = day_refs(d)
        diffs = [None] + [p["difficulty"] for p in d["practice"]]
        reuse = [d["first_pitch"].get("reuse_note")] + [p.get("reuse_note") for p in d["practice"]]
        notes = d.get("notes") or {}

        c = d["concept"]
        concept = {**base, "core": self.r(c["core"]),
                   "figures": [{"svg": self.svg(f, f"{w} concept"), "caption": self.r(f.get("caption"))}
                               for f in c.get("figures") or []],
                   "analogy": self.r(c["analogy"]), "analogy_limit": self.r(c["analogy_limit"]),
                   "map": [{"k": self.r(x["k"]), "v": self.r(x["v"])} for x in c["map"]]}

        s = d["strategy"]
        structure = s.get("structure") or f"{t['kice_intent']}\n이런 신호: {t['signals']}"
        tools, tools_compact = [], []
        for cid in s.get("concept_ids") or []:
            k = ctx.concepts.get(cid)
            if not k:
                continue
            body = k["statement"] + (f"\n→ {k['when']}" if k.get("when") else "")
            tools.append({"name": self.r(k["name"]), "body": self.r(body)})
            tools_compact.append({"name": self.r(k["name"]), "body": self.r(k["statement"])})
        for x in s.get("tools") or []:
            item = {"name": self.r(x["name"]), "body": self.r(x["body"])}
            tools.append(item)
            tools_compact.append(item)
        fig = s.get("figure")
        strategy = {**base, "structure": self.r(structure), "tools": tools, "tools_compact": tools_compact,
                    "figure": {"svg": self.svg(fig, f"{w} strategy"), "caption": self.r(fig.get("caption"))} if fig else None}

        fp = d["first_pitch"]
        first = {**base, "type": self.r(fp["type"]), "signal": self.r(fp["signal"]),
                 "q": self.question(refs[0], 1, None, f"{w} #1 {refs[0]}")}

        sr = d["sign_reading"]
        reading = {**base, "hint": self.r(sr["hint"]), "analysis": self.r(sr["analysis"]),
                   "points": [{"no2": two(i), "text": self.r(x)} for i, x in enumerate(sr["points"], 1)],
                   "verdict": self.r(sr["verdict"]),
                   "scouting": [{"source": H.escape(source_label(ctx.db[x["ref"]])), "note": self.r(x["note"])}
                                for x in sr["scouting"]]}

        practice = [{**base, "q": self.question(ref, i, diffs[i - 1], f"{w} #{i} {ref}")}
                    for i, ref in enumerate(refs[1:], 2)]
        replay = [{"no2": two(x["no"]), "wrong": self.r(x["wrong"]), "stuck": self.r(x["stuck"]), "fix": self.r(x["fix"])}
                  for x in d["replay"]]
        dugout = {**base, "nos": [two(i) for i in range(1, len(refs) + 1)]}

        over = {x["no"]: x for x in d["sign_book"].get("rows") or []}
        rows = []
        for i, ref in enumerate(refs, 1):
            if i in over:
                rows.append({"no2": two(i), "signal": self.r(over[i]["signal"]), "method": self.r(over[i]["method"])})
                continue
            rec = self.record(ref)
            if is_created_id(ref):
                sig, cids = rec["target"]["first_judgment"], rec["target"]["concept_ids"]
            else:
                sig, cids = rec["first_judgment"], ctx.study[ref].get("concept_refs") or []
            rows.append({"no2": two(i), "signal": self.r(reuse[i - 1] or sig), "method": self.r(self.concept_names(cids))})
        signbook = {**base, "rows": rows, "next": self.r(d["sign_book"]["next"])}

        qa = {"day2": base["day2"], "title": base["title"],
              "cells": [{"no2": two(i), "ans": H.escape(answer_display(self.record(ref)))} for i, ref in enumerate(refs, 1)]}
        sols = [self.solution_item(ref, i, notes, reuse[i - 1]) for i, ref in enumerate(refs, 1)]

        n_created = sum(1 for r in refs[1:] if is_created_id(r))
        corners = {
            "THE SIGN": H.escape(t["name"]),
            "FIRST PITCH": "예제 · " + H.escape(self.source_of(refs[0], self.record(refs[0]))),
            "PRACTICE": f"연습 {len(refs) - 1}문항 · 기출 {len(refs) - 1 - n_created} · 창작 {n_created}",
            "DUGOUT NOTE": "채점 기록과 나의 복기",
            "SIGN BOOK": "문항별 신호와 고른 방법 정리",
        }
        return {"day": d["day"], "base": base, "concept": concept, "strategy": strategy, "first": first,
                "reading": reading, "practice": practice, "replay": replay, "dugout": dugout,
                "signbook": signbook, "qa": qa, "sols": sols, "corners": corners}


# ---------------------------------------------------------------- 판면 측정

MEASURE_JS = """async (h) => {
  const B = document.getElementById('B');
  B.innerHTML = h;
  await document.fonts.ready;
  const why = [];
  B.querySelectorAll('.page').forEach(pg => {
    pg.querySelectorAll('.fill,.pad,.sol-wrap,[style*="flex:1"]').forEach(el => { if (el.scrollHeight > el.clientHeight + 2) why.push('내용 넘침'); });
    const sc = pg.querySelector('.sol-cols'); if (sc && sc.scrollWidth > sc.clientWidth + 2) why.push('해설 넘침');
    const ws = pg.querySelector('.ws'); if (ws && ws.clientHeight < 160) why.push('풀이 공간 부족');
  });
  return why;
}"""


class Measurer:
    def __init__(self, head: str, week2: str):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = launch_chromium(self._pw)
        self.page = self.browser.new_page(viewport={"width": 900, "height": 1300})
        route_network(self.page, allow_fonts=True)
        self.page.set_content(f'<!DOCTYPE html><html lang="ko">{head.replace(WEEK_TOKEN, week2)}'
                              f'<body><div class="book" id="B"></div></body></html>', wait_until="load")
        self.count = 0

    def fonts_ok(self) -> bool:
        return self.page.evaluate("""async () => { await document.fonts.ready;
            return document.fonts.check('500 16px "Noto Sans KR"') && document.fonts.check('16px "Black Han Sans"'); }""")

    def issues(self, page_html: str) -> list[str]:
        self.count += 1
        return self.page.evaluate(MEASURE_JS, page_html)

    def close(self):
        self.browser.close()
        self._pw.stop()


def overflow(issues) -> bool:
    return any(x != "풀이 공간 부족" for x in issues)


# ---------------------------------------------------------------- 조립

def run(ctx: Context) -> Log:
    log = Log("build")
    math = Math()
    model = Model(ctx, math, log)
    math.render(ctx, log)
    model.book = math.fill(model.book)
    model.days = math.fill(model.days)
    tpl = load(ctx.path("template"), katex_css(ctx))
    B = model.book

    def render(kind, P, pg="000"):
        return tpl.pages[kind].render(book=B, pg=pg, P=P)

    meas = Measurer(tpl.head, B["week2"])
    try:
        if not meas.fonts_ok():
            log.warn("글꼴", "웹 글꼴(Noto Sans KR·Black Han Sans)을 불러오지 못해 대체 글꼴로 판면을 쟀습니다. "
                           "인터넷 연결 상태에서 다시 빌드하면 정확합니다")

        def fits_single(kind, P, where):
            iss = meas.issues(render(kind, P))
            if overflow(iss):
                log.error(where, f"{kind} 한 장에 넘침 — 내용을 줄일 것")
            elif iss:
                log.warn(where, f"{kind}: {', '.join(sorted(set(iss)))}")

        def flow(kind, base, key, items, where, cap=None):
            """items를 A4 한 장에 들어가는 만큼씩 나눈다"""
            pages, cur = [], []
            for it in items:
                trial = cur + [it]
                if cur and ((cap and len(trial) > cap) or overflow(meas.issues(render(kind, {**base, key: trial})))):
                    pages.append(cur)
                    cur = [it]
                else:
                    cur = trial
            if cur:
                pages.append(cur)
            for chunk in pages:
                if len(chunk) == 1 and overflow(meas.issues(render(kind, {**base, key: chunk}))):
                    log.error(where, f"{kind} 항목 하나가 한 장을 넘음 — 내용을 줄일 것")
            return [{**base, key: chunk} for chunk in pages]

        seq = []  # (kind, P, tag)
        seq.append(("COVER", {}, None))
        contents_items = [{"day2": d["base"]["day2"], "title": d["base"]["title"], "day": d["day"],
                           "corners": [{"name": c, "line": d["corners"][c], "page": "000"} for c in CORNERS]}
                          for d in model.days]
        contents_pages = flow("CONTENTS", {}, "days", contents_items, "목차", cap=5)
        seq += [("CONTENTS", P, None) for P in contents_pages]

        for d in model.days:
            w = f"DAY {d['day']}"
            st = d["strategy"]
            P = {**st}
            if overflow(meas.issues(render("STRATEGY", P))):
                P = {**st, "tools": st["tools_compact"]}
                log.warn(w, "STRATEGY가 넘쳐 실전 개념의 '떠올릴 때' 줄을 뺐습니다")
            fits_single("CONCEPT", d["concept"], w)
            fits_single("STRATEGY", P, w)
            fits_single("FIRST_PITCH", d["first"], w)
            fits_single("SIGN_READING", d["reading"], w)
            seq += [("CONCEPT", d["concept"], (d["day"], "THE SIGN")), ("STRATEGY", P, None),
                    ("FIRST_PITCH", d["first"], (d["day"], "FIRST PITCH")), ("SIGN_READING", d["reading"], None)]
            for i, pr in enumerate(d["practice"]):
                fits_single("PRACTICE", pr, f"{w} #{i + 2}")
                seq.append(("PRACTICE", pr, (d["day"], "PRACTICE") if i == 0 else None))
            for P in flow("REPLAY", d["base"], "entries", d["replay"], f"{w} REPLAY", cap=3):
                seq.append(("REPLAY", P, None))
            fits_single("DUGOUT_NOTE", d["dugout"], w)
            fits_single("SIGN_BOOK", d["signbook"], w)
            seq += [("DUGOUT_NOTE", d["dugout"], (d["day"], "DUGOUT NOTE")), ("SIGN_BOOK", d["signbook"], (d["day"], "SIGN BOOK"))]

        for P in flow("QUICK_ANSWER", {}, "days", [d["qa"] for d in model.days], "정답표"):
            seq.append(("QUICK_ANSWER", P, None))
        for d in model.days:
            for P in flow("SOLUTION", d["base"], "entries", d["sols"], f"DAY {d['day']} 해설"):
                seq.append(("SOLUTION", P, None))
        seq.append(("BACK_COVER", {}, None))

        # ---- 쪽 번호와 목차 쪽수
        where = {tag: f"{i:03d}" for i, (_, _, tag) in enumerate(seq, 1) if tag}
        for P in contents_pages:
            for cd in P["days"]:
                for cc in cd["corners"]:
                    cc["page"] = where.get((cd["day"], cc["name"]), "000")
        out_pages, index = [], []
        for i, (kind, P, _) in enumerate(seq, 1):
            out_pages.append(render(kind, P, f"{i:03d}"))
            index.append({"no": i, "kind": kind, "day": P.get("day2") if isinstance(P, dict) else None})
        log.stats["measures"] = meas.count
    finally:
        meas.close()

    doc = ("<!DOCTYPE html>\n<!-- STEAL THE SIGN : KICE — build.py가 STS_template.html로 생성 -->\n"
           '<html lang="ko">\n' + tpl.head.replace(WEEK_TOKEN, B["week2"]) + "\n<body>\n<div class=\"book\">\n\n"
           + "\n".join(out_pages) + "\n</div>\n</body>\n</html>\n")
    out = ctx.out_dir / "book.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    write_json(ctx.out_dir / "pages.json", index)
    log.stats.update({"pages": len(seq), "file": str(out), "kb": round(len(doc.encode("utf-8")) / 1024)})
    return log
