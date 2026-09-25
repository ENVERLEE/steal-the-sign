"""out/logs/*.json → out/report.md

맨 앞의 'AI에게 전달할 수정 목록'은 그대로 채팅에 붙여 넣어 해당 항목만 고치게 한다.
"""
from __future__ import annotations

from collections import defaultdict

from scripts.common import Context, Log, now, read_json

ORDER = ["pdf_pages", "validate_sources", "check_created", "check_source", "curate", "check_book", "verify_answers",
         "render_figs", "build", "check_layout", "export_pdf"]
NAMES = {"pdf_pages": "PDF 쪽 변환", "validate_sources": "원천 검증", "check_created": "창작 검문",
         "check_source": "교재 판독 검사", "curate": "큐레이션", "check_book": "교재 규칙",
         "verify_answers": "정답 검산", "render_figs": "그림", "build": "조판", "check_layout": "판면 점검", "export_pdf": "PDF"}


def run(ctx: Context) -> Log:
    log = Log("report")
    logs = {}
    for name in ORDER:
        f = ctx.logs / f"{name}.json"
        if f.exists():
            logs[name] = read_json(f)

    L = [f"# STEAL THE SIGN : KICE — 빌드 보고서", "", f"생성: {now()}", ""]
    total_e = sum(len(x["errors"]) for x in logs.values())
    total_w = sum(len(x["warnings"]) for x in logs.values())
    L += ["## 요약", "", "| 단계 | 결과 | 오류 | 경고 | 실행 시각 |", "|---|---|---|---|---|"]
    for name in ORDER:
        x = logs.get(name)
        if not x:
            L.append(f"| {NAMES[name]} | 실행 안 함 | - | - | - |")
            continue
        mark = "통과" if not x["errors"] else "**오류**"
        L.append(f"| {NAMES[name]} | {mark} | {len(x['errors'])} | {len(x['warnings'])} | {x['at']} |")
    L += ["", f"전체 오류 {total_e} · 경고 {total_w}", ""]

    # ---- AI 수정 목록
    L += ["## AI에게 전달할 수정 목록", ""]
    if total_e:
        L += ["아래 항목만 고친다. 고친 뒤 `python run.py`를 다시 실행한다.", "", "```"]
        for name in ORDER:
            for e in (logs.get(name) or {}).get("errors", []):
                L.append(f"[{NAMES[name]}] {e['where']}: {e['msg']}")
        L += ["```", ""]
    else:
        L += ["오류 없음.", ""]

    # ---- 교재 구성
    cb = (logs.get("check_book") or {}).get("stats") or {}
    if cb:
        L += ["## 교재 구성", "",
              f"- DAY {cb.get('days')}개 · 테마 {cb.get('themes')}개 · 문항 {cb.get('problems')}개 "
              f"(교재 {cb.get('textbook', 0)} · 기출 {cb.get('past')} · 창작 {cb.get('created')}, "
              f"기출 비율 {fmt_ratio(cb.get('past_ratio'))})",
              f"- 고난도 번호 기출: {cb.get('hard_numbers')}문항", ""]
        ts = cb.get("theme_stats") or {}
        if ts:
            L += ["| 테마 | 이름 | DAY | 문항 | 교재 | 기출 | 창작 | 창작 비중 |", "|---|---|---|---|---|---|---|---|"]
            for th, s in ts.items():
                name = ctx.themes.get(th, {}).get("name", "")
                share = s["created"] / s["problems"] if s["problems"] else 0
                L.append(f"| {th} | {name} | {s['days']} | {s['problems']} | {s.get('textbook', 0)} | {s['past']} | "
                         f"{s['created']} | {share:.0%} |")
            L.append("")
        for key, title in (("behavior", "행동 영역"), ("difficulty", "난도(연습 문항)")):
            dist = cb.get(key) or {}
            if dist:
                tot = sum(dist.values())
                L.append(f"- {title}: " + " · ".join(f"{k} {v}({v / tot:.0%})" for k, v in sorted(dist.items(), key=lambda kv: -kv[1])))
        if cb.get("reused"):
            L.append("- 여러 번 쓴 문항: " + ", ".join(f"{k}×{v}" for k, v in cb["reused"].items()))
        L.append("")

    # ---- 교재 판독·큐레이션
    cs = (logs.get("check_source") or {}).get("stats") or {}
    if cs and cs.get("problems"):
        L += ["## 교재 판독", ""]
        for b in cs.get("books") or []:
            L.append(f"- {b['id']} {b['title']}: 문항 {b['problems']}개" + (f", PDF {b['pages']}쪽" if b.get("pages") else ""))
        L.append(f"- 검사 통과 {cs.get('verified')} · 미통과 {cs.get('draft')}")
        bt = cs.get("by_theme") or {}
        if bt:
            L.append("- 테마별: " + ", ".join(f"{k} {len(v)}" for k, v in bt.items()))
        cu = (logs.get("curate") or {}).get("stats") or {}
        if cu:
            L.append(f"- 큐레이션 초안: 테마 {cu.get('themes')}개 · DAY {cu.get('days')}개 · 문항 {cu.get('problems')}개 "
                     f"→ `out/curation.md`, `out/plan.json`")
        L.append("")

    # ---- 창작 문제은행
    cc = (logs.get("check_created") or {}).get("stats") or {}
    if cc:
        L += ["## 창작 문제은행", "",
              f"- 레코드 {cc.get('records')}개: 검문 통과(verified) {cc.get('verified')} · 미통과(draft) {cc.get('draft')}"]
        vt = cc.get("verified_by_theme") or {}
        if vt:
            L.append("- 테마별 통과: " + ", ".join(f"{k} {v}" for k, v in vt.items()))
        L.append("")

    # ---- 판면
    lay = (logs.get("check_layout") or {}).get("stats") or {}
    bst = (logs.get("build") or {}).get("stats") or {}
    if lay or bst:
        L += ["## 판면", ""]
        if bst:
            L.append(f"- 결과물: `{bst.get('file')}` ({bst.get('pages')}쪽, {bst.get('kb')}KB, 수식 {bst.get('math')}개)")
        if lay:
            L.append("- 페이지 구성: " + ", ".join(f"{k} {v}" for k, v in (lay.get("by_kind") or {}).items()))
            L.append(f"- 웹 글꼴 로드: {'예' if lay.get('fonts_loaded') else '아니오(대체 글꼴 기준 측정)'}")
        L.append("")

    vs = (logs.get("validate_sources") or {}).get("stats") or {}
    if vs:
        L += ["## 원천 데이터", "",
              f"- 기출 {vs.get('problems')} · 제외(excluded) {vs.get('excluded')} · 테마 {vs.get('themes')} · "
              f"실전개념 {vs.get('concepts')} · 수식 {vs.get('math', '-')}", ""]

    # ---- 경고
    warns = [(n, w) for n in ORDER for w in (logs.get(n) or {}).get("warnings", [])]
    if warns:
        L += ["## 경고", ""]
        grouped = defaultdict(list)
        for n, w in warns:
            grouped[n].append(w)
        for n, ws in grouped.items():
            L.append(f"### {NAMES[n]}")
            L += [f"- {w['where']}: {w['msg']}" for w in ws]
            L.append("")

    out = ctx.out_dir / "report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    log.stats = {"file": str(out), "errors": total_e, "warnings": total_w}
    return log


def fmt_ratio(r):
    return f"{r:.0%}" if isinstance(r, (int, float)) else "-"
