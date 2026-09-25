"""판면 점검: out/book.html을 브라우저로 열어 페이지마다 검사한다.

- A4(794×1123px) 크기, 내용·해설 넘침, 풀이 공간 부족
- [[ ]] 슬롯·data-slot 가짜 번호(00·000·0) 잔존, KaTeX 오류 표시
- 책 순서(COVER → CONTENTS → … → BACK_COVER), 쪽 번호 연속
"""
from __future__ import annotations

from scripts.common import Context, Log, launch_chromium, route_network

CHECK_JS = """async () => {
  await document.fonts.ready;
  const fonts = (await document.fonts.load('16px "Noto Sans KR"', '가A')).length > 0;
  const out = [];
  document.querySelectorAll('.page').forEach((pg, i) => {
    const why = [];
    const r = pg.getBoundingClientRect();
    if (Math.round(r.width) !== 794 || Math.round(r.height) !== 1123) why.push(`크기 ${Math.round(r.width)}×${Math.round(r.height)}`);
    pg.querySelectorAll('.fill,.pad,.sol-wrap,.x-body,[style*="flex:1"]').forEach(el => { if (el.scrollHeight > el.clientHeight + 2) why.push('내용 넘침'); });
    const sc = pg.querySelector('.sol-cols'); if (sc && sc.scrollWidth > sc.clientWidth + 2) why.push('해설 넘침');
    const ws = pg.querySelector('.ws'); const small = ws && ws.clientHeight < 160;
    if (pg.innerHTML.indexOf('[[') > -1 || pg.innerHTML.indexOf(']]') > -1) why.push('빈 슬롯 [[ ]]');
    pg.querySelectorAll('[data-slot]').forEach(s => { if (/^0+$/.test(s.textContent.trim())) why.push('가짜 번호 ' + s.getAttribute('data-slot')); });
    const kerr = pg.querySelectorAll('.katex-error').length; if (kerr) why.push(`KaTeX 오류 ${kerr}곳`);
    const tw = document.createTreeWalker(pg, NodeFilter.SHOW_TEXT, {acceptNode: n =>
      (n.parentElement.closest('.katex,style,script,svg') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT)});
    let leak = null; while (tw.nextNode()) { const m = tw.currentNode.nodeValue.match(/\\[a-zA-Z]{2,}|\$[^$]{1,40}\$/); if (m) { leak = m[0]; break; } }
    if (leak) why.push('수식 기호 노출: ' + leak);
    const pgno = (pg.querySelector('.pg [data-slot="PAGE"], .hd-no [data-slot="PAGE"]') || {}).textContent || null;
    out.push({i: i + 1, kind: pg.getAttribute('data-page'), why: [...new Set(why)], small, pgno});
  });
  return {fonts, pages: out, flagged: document.querySelectorAll('.chk-flag').length};
}"""


def run(ctx: Context) -> Log:
    log = Log("check_layout")
    path = ctx.out_dir / "book.html"
    if not path.exists():
        log.error("book.html", "먼저 build 단계를 실행하세요")
        return log
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 900, "height": 1300})
        route_network(page, allow_fonts=True)
        page.goto(path.resolve().as_uri(), wait_until="load")
        res = page.evaluate(CHECK_JS)
        browser.close()

    pages = res["pages"]
    if not res["fonts"]:
        log.warn("글꼴", "웹 글꼴을 불러오지 못한 상태에서 점검했습니다(대체 글꼴 기준)")
    kinds = [p["kind"] for p in pages]
    if not kinds or kinds[0] != "COVER" or kinds[-1] != "BACK_COVER":
        log.error("순서", "책은 COVER로 시작해 BACK_COVER로 끝나야 함")
    if "CONTENTS" in kinds and kinds.index("CONTENTS") != 1:
        log.error("순서", "CONTENTS는 표지 바로 뒤")
    for p in pages:
        where = f"{p['i']:03d}쪽 {p['kind']}"
        for w in p["why"]:
            log.error(where, w)
        if p["small"]:
            log.warn(where, "풀이 공간 부족(160px 미만) — 문제 본문이 길다")
        if p["pgno"] and p["pgno"].strip() != f"{p['i']:03d}":
            log.error(where, f"쪽 번호 {p['pgno']} ≠ 실제 순서 {p['i']:03d}")
    log.stats = {"pages": len(pages), "by_kind": {k: kinds.count(k) for k in dict.fromkeys(kinds)},
                 "fonts_loaded": res["fonts"], "template_flags": res["flagged"]}
    return log
