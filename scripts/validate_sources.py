"""원천 데이터 검증 → out/excluded.json

db.json·solutions.json·themes.json·strategy_notes.json 사이의 모순을 찾는다.
문항 자체에 문제가 있으면 excluded.json에 올려 교재에서 쓰지 못하게 한다.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from scripts.common import Context, Log, choice_text, read_json, write_json

ID_RE = re.compile(r"^(M1|M2|PS)-(\d{2})(\d{2})(\d{2})$")
PREFIX = {"수학Ⅰ": "M1", "수학Ⅱ": "M2", "확률과 통계": "PS"}


CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]|\r|\t")


def run(ctx: Context, katex: bool = True) -> Log:
    log = Log("validate_sources")
    cfg = ctx.config["sources"]
    excluded: dict[str, list[str]] = defaultdict(list)

    def exclude(pid: str, why: str) -> None:
        excluded[pid].append(why)
        log.error(pid, why)

    db = ctx.db
    y0, y1 = cfg["years"]

    # ---- 1. db.json 레코드 자체
    db_list = read_json(ctx.path("db"))
    for pid, n in Counter(r["id"] for r in db_list).items():
        if n > 1:
            exclude(pid, f"db.json에 id 중복 {n}회")

    for pid, r in db.items():
        s = r["source"]
        m = ID_RE.match(pid)
        if not m:
            exclude(pid, "id 형식이 {과목}-{YYMMNN}이 아님")
            continue
        if PREFIX.get(r["subject"]) != m.group(1):
            exclude(pid, f"id 접두어와 과목({r['subject']}) 불일치")
        if s["code"] != pid[3:]:
            exclude(pid, f"source.code {s['code']} ≠ id")
        yy, mm, nn = s["code"][:2], s["code"][2:4], int(s["code"][4:])
        if mm not in cfg["months"]:
            exclude(pid, f"월 코드 {mm}는 06·09·11이 아님")
        if not (y0 <= 2000 + int(yy) <= y1) or s["year"] != 2000 + int(yy):
            exclude(pid, f"학년도 {s['year']}가 범위 {y0}~{y1} 밖이거나 code와 불일치")
        lo, hi = cfg["number_range"][r["subject"]]
        if not (lo <= nn <= hi) or s["number"] != nn:
            exclude(pid, f"번호 {nn}이 {r['subject']} 범위 {lo}~{hi} 밖이거나 source.number와 불일치")
        if s.get("points") != ctx.config["points"]["past"]:
            exclude(pid, f"배점 {s.get('points')}점 (기출은 4점)")
        if r.get("choices"):
            if len(r["choices"]) != 5:
                exclude(pid, f"선택지 {len(r['choices'])}개")
            elif not (str(r["answer"]).isdigit() and 1 <= int(r["answer"]) <= 5):
                exclude(pid, f"객관식 정답 {r['answer']}이 1~5가 아님")
            elif str(r.get("answer_value")) != str(r["choices"][int(r["answer"]) - 1]):
                log.warn(pid, "answer_value가 정답 선지 값과 다름")
        else:
            a = str(r["answer"])
            if not (a.isdigit() and 1 <= int(a) <= 999):
                exclude(pid, f"단답형 정답 {a}이 3자리 이하 자연수가 아님")
        for f in ("question",):
            if (r.get(f) or "").count("$") % 2:
                exclude(pid, f"{f}의 $ 짝이 맞지 않음")
        if (r.get("condition") or "").count("$") % 2:
            exclude(pid, "condition의 $ 짝이 맞지 않음")
        for sid in r.get("strategy_ids") or []:
            if sid not in ctx.strategies:
                log.warn(pid, f"strategy {sid}가 strategy_notes에 없음")

    # ---- 2. 수학Ⅰ·Ⅱ 같은 시험 번호 공간 충돌
    shared = defaultdict(list)
    for pid, r in db.items():
        if r["subject"] in cfg["shared_number_space"]:
            shared[r["source"]["code"]].append(pid)
    for code, ids in shared.items():
        if len(ids) > 1:
            for pid in ids:
                exclude(pid, f"수학Ⅰ·Ⅱ가 같은 시험·번호 {code}를 공유 ({', '.join(ids)})")

    # ---- 3. strategy_notes 예시와 대조
    codes = defaultdict(list)
    for pid, r in db.items():
        codes[r["source"]["code"]].append(r)
    for sid, st in ctx.strategies.items():
        for ex in st.get("examples") or []:
            code = ex.get("db_code_candidate")
            if not code or ex.get("kind") != "평가원":
                continue
            if not (y0 <= 2000 + int(code[:2]) <= y1):
                continue  # DB 범위 밖 예시
            recs = codes.get(code)
            if not recs:
                log.warn(sid, f"예시 {code}({ex.get('source')})가 db.json에 없음")
            elif not any(sid in (r.get("strategy_ids") or []) for r in recs):
                log.warn(sid, f"예시 {code}의 db 레코드 strategy_ids에 {sid}가 없음")

    # ---- 4. solutions.json
    concepts = ctx.concepts
    for pid in db:
        st = ctx.study.get(pid)
        if st is None:
            exclude(pid, "solutions.json에 풀이 없음")
            continue
        if str(st.get("answer")) != str(db[pid]["answer"]):
            exclude(pid, f"풀이 정답 {st.get('answer')} ≠ DB 정답 {db[pid]['answer']}")
        for ref in st.get("concept_refs") or []:
            if ref not in concepts:
                exclude(pid, f"끊긴 concept_refs {ref}")
        for fld in ("guide", "solutions", "skill_point"):
            if not st.get(fld):
                exclude(pid, f"study_solution.{fld} 비어 있음")
        for sol in st.get("solutions") or []:
            for step in sol.get("steps") or []:
                if (step.get("body") or "").count("$") % 2:
                    exclude(pid, f"풀이 '{step.get('label')}'의 $ 짝이 맞지 않음")
    for pid in ctx.study:
        if pid not in db:
            log.warn(pid, "solutions.json에만 있는 문항")

    # ---- 5. themes.json
    home = Counter()
    for tid, t in ctx.themes.items():
        for pid in t["problem_ids"]:
            home[pid] += 1
            if pid not in db:
                log.error(tid, f"problem_ids의 {pid}가 db.json에 없음")
            elif db[pid]["subject"] != t["subject"]:
                log.error(tid, f"{pid} 과목이 테마 과목과 다름")
        for pid in t.get("related_ids") or []:
            if pid not in db:
                log.error(tid, f"related_ids의 {pid}가 db.json에 없음")
        for o in t["old_themes"]:
            if o not in ctx.old_themes:
                log.error(tid, f"old_themes {o}가 solutions.json에 없음")
        for sid in t.get("strategy_ids") or []:
            if sid not in ctx.strategies:
                log.error(tid, f"strategy {sid}가 strategy_notes에 없음")
    for pid in db:
        if home[pid] == 0:
            exclude(pid, "themes.json 어느 테마에도 배정되지 않음")
        elif home[pid] > 1:
            log.error(pid, f"themes.json 홈 테마 중복 배정 {home[pid]}회")
    counts = Counter(t["subject"] for t in ctx.themes.values())
    for subj, n in ctx.config["themes"]["count"].items():
        if counts[subj] != n:
            log.error("themes.json", f"{subj} 테마 {counts[subj]}개 (설정 {n}개)")

    # ---- 6. 텍스트: 깨진 이스케이프(\\f→폼피드 등)와 KaTeX 조판 오류
    owners = defaultdict(set)
    texts = []
    for pid, r in db.items():
        for f in ("question", "condition"):
            texts.append((pid, r.get(f)))
        texts += [(pid, choice_text(c)) for c in r.get("choices") or []]
        st = ctx.study.get(pid) or {}
        texts += [(pid, st.get(f)) for f in ("guide", "supplement", "skill_point")]
        for sol in st.get("solutions") or []:
            texts.append((pid, sol.get("title")))
            texts += [(pid, x.get(k)) for x in sol.get("steps") or [] for k in ("label", "body")]
    for t in ctx.solutions["themes"]:
        texts.append((t["theme"], t.get("overview")))
        for c in t["core_concepts"]:
            texts += [(c["id"], c.get(f)) for f in ("name", "statement", "why", "when")]
    for owner, text in texts:
        if text and CTRL_RE.search(text):
            log.error(owner, f"제어문자 {sorted({repr(ch) for ch in CTRL_RE.findall(text)})} — JSON 이스케이프로 깨진 LaTeX 명령(\\frac→\\f 등)")
    if katex:
        from scripts.tex import Math, split_math
        m = Math()
        for owner, text in texts:
            if text:
                m.rich(text)
                for kind, part in split_math(text):
                    if kind != "text":
                        owners[part].add(owner)
        klog = Log("katex")
        m.render(ctx, klog)
        for tex, err in m.errors:
            for owner in sorted(owners.get(tex, {"?"})):
                log.error(owner, f"KaTeX 오류 ${tex[:50]}$ — {err[:100]}")
        log.stats["math"] = len(m.items)

    out = [{"id": pid, "reasons": why} for pid, why in sorted(excluded.items())]
    write_json(ctx.excluded_path, out)
    log.stats.update({"problems": len(db), "excluded": len(out), "themes": len(ctx.themes),
                 "concepts": len(concepts), "solutions": len(ctx.study)})
    return log
