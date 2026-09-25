"""out/book.html → out/book.pdf (A4, 쪽마다 한 장)

템플릿의 인쇄 CSS(@page A4, margin 0, .page마다 쪽 나눔)를 그대로 써서 Chromium으로 인쇄한다.
웹 글꼴은 판면 점검과 같은 방식으로 불러오고, 결과 PDF의 쪽 수가 HTML의 .page 수와 같은지 확인한다.
"""
from __future__ import annotations

from scripts.common import FONTS_LOADED_JS, Context, Log, launch_chromium, route_network


def run(ctx: Context) -> Log:
    log = Log("export_pdf")
    src = ctx.out_dir / "book.html"
    dst = ctx.out_dir / "book.pdf"
    if not src.exists():
        log.error("book.html", "먼저 build 단계를 실행하세요")
        return log
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 900, "height": 1300})
        route_network(page, allow_fonts=True)
        page.goto(src.resolve().as_uri(), wait_until="load")
        page.evaluate("async () => { await document.fonts.ready; }")
        fonts = page.evaluate(FONTS_LOADED_JS, ["Noto Sans KR", "Black Han Sans"])
        n_html = page.evaluate("() => document.querySelectorAll('.page').length")
        page.emulate_media(media="print")
        page.pdf(path=str(dst), prefer_css_page_size=True, print_background=True,
                 margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        browser.close()

    if not fonts:
        log.warn("글꼴", "웹 글꼴을 불러오지 못해 대체 글꼴로 인쇄했습니다")
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(dst))
    n_pdf = len(doc)
    w, h = doc[0].get_size() if n_pdf else (0, 0)
    doc.close()
    if n_pdf != n_html:
        log.error("쪽 수", f"PDF {n_pdf}쪽 ≠ HTML {n_html}쪽 — 인쇄 중 쪽이 밀렸다")
    if n_pdf and (abs(w - 595.3) > 2 or abs(h - 841.9) > 2):
        log.error("크기", f"PDF 쪽 크기 {w:.1f}×{h:.1f}pt ≠ A4(595×842pt)")
    log.stats = {"pages": n_pdf, "bytes": dst.stat().st_size, "path": str(dst)}
    return log
