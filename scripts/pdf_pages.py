"""교재 PDF → 쪽 이미지(PNG)·텍스트 층 (AI 판독용)

  python run.py pages --pdf 교재.pdf --id KB1
    → work/source/KB1/pages/p001.png, p001.txt …, work/source/KB1/pages.json

판독(OCR)은 AI가 채팅에서 이미지를 보고 한다(스크립트는 AI를 부르지 않는다).
텍스트 층이 있는 PDF면 p###.txt가 판독의 보조 자료가 된다(수식은 대개 깨져 있으니 이미지를 기준으로).
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.common import Context, Log, write_json


def book_id_from(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", Path(name).stem).upper()[:8]
    return s or "BOOK1"


def run(ctx: Context, pdf: str | None = None, book_id: str | None = None) -> Log:
    log = Log("pdf_pages")
    if not pdf:
        log.error("pages", "--pdf 경로를 주세요: python run.py pages --pdf 교재.pdf --id KB1")
        return log
    src = Path(pdf)
    if not src.exists():
        log.error("pages", f"{src} 가 없습니다")
        return log
    bid = (book_id or book_id_from(src.name)).upper()
    if not re.fullmatch(r"[A-Z0-9]{1,8}", bid):
        log.error("pages", f"교재 id '{bid}'는 영문 대문자·숫자 1~8자")
        return log

    import pypdfium2 as pdfium
    out = ctx.source_dir / bid / "pages"
    out.mkdir(parents=True, exist_ok=True)
    scale = ctx.config["textbook"]["pages_scale"]
    doc = pdfium.PdfDocument(str(src))
    pages = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            n = i + 1
            img = page.render(scale=scale).to_pil()
            img.save(out / f"p{n:03d}.png")
            text = page.get_textpage().get_text_range()
            (out / f"p{n:03d}.txt").write_text(text, encoding="utf-8")
            pages.append({"page": n, "image": f"p{n:03d}.png", "text_chars": len(text.strip())})
    finally:
        doc.close()
    write_json(ctx.source_dir / bid / "pages.json", {"book_id": bid, "pdf": src.name, "pages": pages})
    no_text = sum(1 for p in pages if p["text_chars"] == 0)
    if no_text == len(pages):
        log.warn(bid, "텍스트 층이 없는 PDF(스캔본) — 이미지만으로 판독한다")
    log.stats = {"book_id": bid, "pages": len(pages), "dir": str(out), "no_text_pages": no_text}
    print(f"   {len(pages)}쪽 → {out}  (판독 결과는 {ctx.source_dir / (bid + '.json')} 에 쓴다)")
    return log
