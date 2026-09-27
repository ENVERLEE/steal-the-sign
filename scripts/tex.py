"""KaTeX 일괄 조판 (Playwright + vendor/katex, CDN 없음)

텍스트는 두 단계로 바뀐다.
1) rich(text): $…$·$$…$$를 자리표시로 바꾸고 나머지는 HTML 이스케이프(\\n·\\\\ → <br>)
2) render(): 모인 수식을 브라우저 한 번에 조판(캐시) → fill()로 자리표시를 채운다
"""
from __future__ import annotations

import base64
import html
import re

from scripts.common import Context, Log, content_hash, launch_chromium, read_json, route_network, write_json

PH_OPEN, PH_CLOSE = "", ""
PH_RE = re.compile(PH_OPEN + r"(\d+)" + PH_CLOSE)


def katex_version(ctx: Context) -> str:
    js = (ctx.path("katex") / "katex.min.js").read_text(encoding="utf-8")
    m = re.search(r'version:"([\d.]+)"', js) or re.search(r"(\d+\.\d+\.\d+)", js)
    return m.group(1) if m else "?"


def katex_css(ctx: Context) -> str:
    """katex.min.css의 글꼴을 woff2 data URI로 내장 → 결과 HTML 한 파일로 완결"""
    kdir = ctx.path("katex")
    css = (kdir / "katex.min.css").read_text(encoding="utf-8")

    def src(m):
        name = re.search(r"url\(fonts/([^)]+)\.woff2\)", m.group(0))
        if not name:
            return m.group(0)
        data = base64.b64encode((kdir / "fonts" / f"{name.group(1)}.woff2").read_bytes()).decode()
        return f'src:url(data:font/woff2;base64,{data}) format("woff2")'
    return re.sub(r"src:[^;}]+", src, css)


class Math:
    def __init__(self):
        self.items: list[tuple[str, bool]] = []
        self.index: dict[tuple[str, bool], int] = {}
        self.html: dict[int, str] = {}
        self.errors: list[tuple[str, str]] = []

    def _ph(self, tex: str, display: bool) -> str:
        key = (tex, display)
        if key not in self.index:
            self.index[key] = len(self.items)
            self.items.append(key)
        return f"{PH_OPEN}{self.index[key]}{PH_CLOSE}"

    def rich(self, text) -> str:
        """텍스트 + $LaTeX$ → HTML(수식은 자리표시)"""
        if text is None:
            return ""
        # **굵게**·__밑줄__: 수식을 사이에 둘 수 있으므로 자르기 전에 표시 문자로 바꿔 두었다가 태그로 되돌린다
        text = EMPH_U.sub("\x03\\1\x04", EMPH_B.sub("\x01\\1\x02", str(text)))
        out, parts = [], split_math(text)
        glue = ""
        for i, (kind, part) in enumerate(parts):
            if kind == "text":
                part = part[len(glue):]
                glue = ""
                out.append(_plain(part))
                continue
            ph = self._ph(part, kind == "display")
            nxt = parts[i + 1] if i + 1 < len(parts) else None
            m = HANGUL_HEAD.match(nxt[1]) if kind == "inline" and nxt and nxt[0] == "text" else None
            if m:  # 수식 바로 뒤의 조사(예: $x$에)가 다음 줄로 떨어지지 않게 묶는다
                glue = m.group(0)
                out.append(f'<span class="nw">{ph}{_plain(glue)}</span>')
            else:
                out.append(ph)
        return "".join(out).translate(EMPH_TAGS)

    def render(self, ctx: Context, log: Log) -> None:
        cache_path = ctx.out_dir / ".cache" / "tex.json"
        cache = read_json(cache_path) if cache_path.exists() else {}
        ver = katex_version(ctx)
        keys = {i: content_hash([ver, t, d]) for i, (t, d) in enumerate(self.items)}
        todo = [i for i in keys if keys[i] not in cache]
        if todo:
            from playwright.sync_api import sync_playwright
            js = (ctx.path("katex") / "katex.min.js").read_text(encoding="utf-8")
            with sync_playwright() as p:
                browser = launch_chromium(p)
                page = browser.new_page()
                route_network(page, allow_fonts=False)
                page.set_content("<html><body></body></html>")
                page.add_script_tag(content=js)
                batch = [[self.items[i][0], self.items[i][1]] for i in todo]
                res = page.evaluate("""(items) => items.map(([t, d]) => {
                    const opt = {displayMode: d, throwOnError: true, strict: 'ignore', output: 'html', trust: false};
                    try { return [katex.renderToString(t, opt), null]; }
                    catch (e) { opt.throwOnError = false; return [katex.renderToString(t, opt), String(e.message || e)]; }
                })""", batch)
                browser.close()
            for i, (h, err) in zip(todo, res):
                cache[keys[i]] = {"html": h, "error": err, "tex": self.items[i][0]}
            write_json(cache_path, cache)
        for i, k in keys.items():
            c = cache[k]
            self.html[i] = c["html"]
            if c.get("error"):
                self.errors.append((c["tex"], c["error"]))
                log.error("수식", f"KaTeX 오류 ${c['tex'][:60]}$ — {c['error'][:120]}")
        log.stats["math"] = len(self.items)
        log.stats["math_rendered_now"] = len(todo)

    def fill(self, node):
        """모델 안의 모든 문자열에서 자리표시를 조판 결과로 바꾼다"""
        if isinstance(node, str):
            return PH_RE.sub(lambda m: self.html[int(m.group(1))], node)
        if isinstance(node, list):
            return [self.fill(v) for v in node]
        if isinstance(node, dict):
            return {k: self.fill(v) for k, v in node.items()}
        return node


def split_math(text: str) -> list[tuple[str, str]]:
    """[('text'|'inline'|'display', 내용)] — 중괄호 안의 $(\\text{$t$의 …})와 \\$는 수식 안으로 본다"""
    parts, buf, i, n = [], [], 0, len(text)
    while i < n:
        if text[i] == "\\" and i + 1 < n and text[i + 1] == "$":
            buf.append("$")
            i += 2
            continue
        if text[i] != "$":
            buf.append(text[i])
            i += 1
            continue
        display = text.startswith("$$", i)
        start = i + (2 if display else 1)
        j, depth = start, 0
        while j < n:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == "$" and depth <= 0:
                break
            j += 1
        if j >= n:  # 닫히지 않은 $ → 글자로
            buf.append(text[i:])
            break
        if buf:
            parts.append(("text", "".join(buf)))
            buf = []
        parts.append(("display" if display else "inline", text[start:j]))
        i = j + (2 if display else 1)
    if buf:
        parts.append(("text", "".join(buf)))
    return parts


HANGUL_HEAD = re.compile(r"[가-힣]+")
EMPH_B = re.compile(r"\*\*(.+?)\*\*", re.S)
EMPH_U = re.compile(r"__(.+?)__", re.S)
EMPH_TAGS = str.maketrans({"\x01": "<b>", "\x02": "</b>", "\x03": "<u>", "\x04": "</u>"})


def _plain(s: str) -> str:
    s = html.escape(s, quote=False)
    s = s.replace("\\\\", "<br>").replace("\n", "<br>")
    return s
