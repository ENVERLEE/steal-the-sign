"""창작 문제은행 검문 (work/created/{테마}/{id}.json)

통과하면 status=verified, 아니면 draft. 결과는 레코드의 review에 기록한다.
내용(status·review 제외)의 해시가 바뀌지 않았고 이미 verified면 다시 실행하지 않는다.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict

from scripts.common import Context, Log, content_hash, has_choices, now, strip_tex, write_json
from scripts.mathval import run_verify, same_value
from scripts.schemas import validate

TEXT_FIELDS = ("question", "condition")


def body_hash(rec: dict) -> str:
    return content_hash({k: v for k, v in rec.items() if k not in ("status", "review")})


def iter_texts(rec: dict):
    """금지어·$ 짝 검사 대상 텍스트 (경로, 문자열)"""
    for f in TEXT_FIELDS:
        if rec.get(f):
            yield f, rec[f]
    for i, c in enumerate(rec.get("choices") or []):
        yield f"choices/{i}", c
    sol = rec.get("solution") or {}
    for f in ("guide", "supplement", "skill_point"):
        if sol.get(f):
            yield f"solution/{f}", sol[f]
    for i, s in enumerate(sol.get("solutions") or []):
        for j, st in enumerate(s.get("steps") or []):
            yield f"solution/solutions/{i}/steps/{j}", st.get("body", "")
    for i, d in enumerate(rec.get("distractors") or []):
        yield f"distractors/{i}", d.get("error_path", "")
    if (rec.get("target") or {}).get("first_judgment"):
        yield "target/first_judgment", rec["target"]["first_judgment"]


# 글자 그대로의 \n(백슬래시+n): 줄바꿈을 두 번 이스케이프해서 생긴다. 교재에 '\n'이 그대로 찍힌다.
# 뒤에 영문자가 오면 LaTeX 명령(\ne, \neq, \nmid, \notin …)이므로 제외
LITERAL_NL_RE = re.compile(r"\\n(?![A-Za-z])")
LITERAL_NL_MSG = "글자 그대로의 '\\n' — 줄바꿈은 JSON에서 \\n 한 번(실제 개행)으로 쓴다"


def banned_hits(text: str, cfg: dict) -> list[str]:
    t = text
    for c in cfg["corner_names"]:
        t = t.replace(c, "")
    return [w for w in cfg["banned_terms"] if w in t]


def solution_length(sol: dict) -> int:
    return sum(len(strip_tex(st.get("body", ""))) for st in sol.get("steps") or [])


def check_record(rec: dict, path, ctx: Context) -> tuple[list[str], list[str]]:
    cfg, ccfg = ctx.config, ctx.config["created"]
    errs, warns = [], []

    errs += [f"스키마 {m}" for m in validate("created", rec)]
    if errs:
        return errs, warns  # 형식이 깨지면 이후 검사는 의미가 없다

    rid, theme = rec["id"], rec["theme"]
    if not rid.startswith(f"C-{theme}-"):
        errs.append(f"id {rid}가 테마 {theme}와 맞지 않음 (C-{theme}-NNN)")
    if path.parent.name != theme or path.stem != rid:
        errs.append(f"파일 위치는 {ccfg['dir']}/{theme}/{rid}.json 이어야 함")
    t = ctx.themes.get(theme)
    if not t:
        errs.append(f"테마 {theme}가 themes.json에 없음")
        return errs, warns

    # ---- 출처(기출 변형)
    o = rec["origin"]
    parent = None
    if o["type"] == "variant":
        pid = o.get("parent_id")
        if not pid:
            errs.append("variant는 origin.parent_id 필수")
        elif pid not in ctx.db:
            errs.append(f"parent_id {pid}가 db.json에 없음")
        elif pid in ctx.excluded:
            errs.append(f"parent_id {pid}는 excluded.json에 있음")
        else:
            parent = ctx.db[pid]
            if parent["subject"] != t["subject"]:
                errs.append(f"parent {pid} 과목이 테마 과목({t['subject']})과 다름")
            if pid not in t["problem_ids"] and pid not in (t.get("related_ids") or []):
                warns.append(f"parent {pid}가 테마 {theme}의 기출 후보 밖")
        if o.get("variation") not in ccfg["variations"]:
            errs.append(f"origin.variation은 {ccfg['variations']} 중 하나")

    # ---- 스킬 적중
    tg = rec["target"]
    for cid in tg["concept_ids"] + (rec["solution"].get("concept_refs") or []):
        if cid not in ctx.concepts:
            errs.append(f"개념 id {cid}가 solutions.json에 없음")
    olds = set(t["old_themes"])
    if not any(cid.rsplit("-C", 1)[0] in olds for cid in tg["concept_ids"]):
        warns.append(f"target.concept_ids가 테마 {theme}의 개념({', '.join(sorted(olds))})을 하나도 겨냥하지 않음")
    for sid in tg.get("strategy_ids") or []:
        if sid not in ctx.strategies:
            errs.append(f"strategy {sid}가 strategy_notes에 없음")
    sols = rec["solution"]["solutions"]
    l1, l2 = solution_length(sols[0]), solution_length(sols[1])
    ratio = l1 / l2 if l2 else 1.0
    if ratio > ccfg["skill_length_ratio_max"]:
        errs.append(f"풀이 1(스킬) 분량이 풀이 2(정석)의 {ratio:.0%} — {ccfg['skill_length_ratio_max']:.0%} 이하여야 스킬 문항")

    # ---- 정답·선지 형식
    ans = rec["answer"]
    if has_choices(rec):
        vals = rec.get("choice_values")
        if not (ans.isdigit() and 1 <= int(ans) <= cfg["created"]["choices"]):
            errs.append(f"객관식 정답 {ans}은 1~5")
        elif not vals:
            errs.append("객관식은 choice_values(5개) 필수")
        elif not rec.get("answer_value"):
            errs.append("객관식은 answer_value 필수")
        else:
            if not same_value(rec["answer_value"], vals[int(ans) - 1]):
                errs.append(f"answer_value {rec['answer_value']} ≠ {ans}번 선지 값 {vals[int(ans) - 1]}")
            for i in range(5):
                for j in range(i + 1, 5):
                    if same_value(vals[i], vals[j]):
                        errs.append(f"선지 {i + 1}·{j + 1}의 값이 같음")
        if ccfg["require_distractor_paths"]:
            got = Counter(d["choice"] for d in rec.get("distractors") or [])
            want = {i for i in range(1, 6) if str(i) != ans}
            if set(got) != want or any(n > 1 for n in got.values()):
                errs.append(f"distractors는 오답 선지 {sorted(want)} 각각 하나씩 오답 경로를 적어야 함")
    else:
        if not (ans.isdigit() and 1 <= int(ans) <= ccfg["short_answer_max"]):
            errs.append(f"단답형 정답 {ans}은 1~{ccfg['short_answer_max']} 자연수")
        if rec.get("answer_value") and not same_value(rec["answer_value"], ans):
            errs.append("단답형 answer_value가 answer와 다름")
        if rec.get("distractors"):
            warns.append("단답형인데 distractors가 있음")

    # ---- 텍스트
    for where, text in iter_texts(rec):
        if text.count("$") % 2:
            errs.append(f"{where}: $ 짝이 맞지 않음")
        if LITERAL_NL_RE.search(text):
            errs.append(f"{where}: {LITERAL_NL_MSG}")
        hits = banned_hits(text, cfg)
        if hits:
            errs.append(f"{where}: 야구 용어 {hits}")

    # ---- 원본 복제 방지
    if parent:
        a = (parent.get("question") or "") + (parent.get("condition") or "")
        b = (rec.get("question") or "") + (rec.get("condition") or "")
        sim = difflib.SequenceMatcher(None, a, b).ratio()
        if sim >= ccfg["near_copy_warn"]:
            warns.append(f"원본 {parent['id']}와 본문 유사도 {sim:.0%} — 수치만 바꾼 복제인지 확인")

    # ---- 그림
    if rec.get("figure"):
        from scripts.render_figs import render_svg
        try:
            render_svg(rec["figure"])
        except Exception as e:  # noqa: BLE001
            errs.append(f"그림 명세 오류: {e}")

    # ---- verify: 두 경로 검산 + 유일성
    target = rec.get("answer_value") if has_choices(rec) else ans
    res = run_verify(rec["verify"], ["skill", "standard", "unique"], ccfg["verify_timeout_sec"])
    for k, m in res.get("errors", {}).items():
        errs.append(f"verify {k}: {m}")
    r = res.get("results", {})
    for k, label in (("skill", "스킬 풀이"), ("standard", "정석 풀이")):
        if k in r and not same_value(r[k], target):
            errs.append(f"verify {k}()={r[k]} ≠ 정답 {target} ({label} 불일치)")
    if "unique" in r:
        u = r["unique"] if isinstance(r["unique"], list) else [r["unique"]]
        if len(u) != 1:
            errs.append(f"답이 유일하지 않음: unique()={u}")
        elif not same_value(u[0], target):
            errs.append(f"unique()={u} ≠ 정답 {target}")
    return errs, warns


def run(ctx: Context, recheck: bool = False) -> Log:
    log = Log("check_created")
    ccfg = ctx.config["created"]
    bank = ctx.created
    seen_ids = Counter(e["rec"].get("id") for e in bank.values())

    # 한 번에 너무 많이 만들지 않기: 아직 통과하지 못한(검사 대기) 레코드가 테마당 batch_max를 넘으면
    # id 순으로 앞의 batch_max개만 검사하고 나머지는 막는다.
    pending = defaultdict(list)
    for rid, e in sorted(bank.items()):
        rec = e["rec"]
        rv = rec.get("review") or {}
        if not (rec.get("status") == "verified" and rv.get("hash") == body_hash(rec)):
            pending[rec.get("theme")].append(rid)
    blocked = {rid for ids in pending.values() for rid in ids[ccfg["batch_max"]:]}

    originals = Counter()
    status = Counter()
    for rid, e in bank.items():
        rec, path = e["rec"], e["path"]
        h = body_hash(rec)
        rv = rec.get("review") or {}
        if not recheck and rec.get("status") == "verified" and rv.get("hash") == h and not rv.get("errors"):
            status["verified"] += 1
            if (rec.get("origin") or {}).get("type") == "original":
                originals[rec.get("theme")] += 1
            continue

        th = rec.get("theme")
        if rid in blocked:
            errs, warns = [f"테마 {th}의 검사 대기 {len(pending[th])}개 — 한 번에 {ccfg['batch_max']}개까지. "
                           f"앞의 문항을 먼저 통과시킬 것"], []
        else:
            errs, warns = check_record(rec, path, ctx)
        if seen_ids[rid] > 1:
            errs.append("같은 id의 레코드가 여러 개")
        if (rec.get("origin") or {}).get("type") == "original":
            originals[th] += 1
            if originals[th] > ccfg["original_per_theme_max"]:
                errs.append(f"테마 {th}의 신작(original)은 {ccfg['original_per_theme_max']}개까지")

        rec["status"] = "draft" if errs else "verified"
        rec["review"] = {"checked_at": now(), "hash": h, "errors": errs, "warnings": warns}
        write_json(path, rec)
        status[rec["status"]] += 1
        for m in errs:
            log.error(rid, m)
        for m in warns:
            log.warn(rid, m)

    by_theme = Counter(e["rec"].get("theme") for e in bank.values()
                       if e["rec"].get("status") == "verified")
    log.stats = {"records": len(bank), "verified": status["verified"], "draft": status["draft"],
                 "verified_by_theme": dict(sorted(by_theme.items()))}
    return log
