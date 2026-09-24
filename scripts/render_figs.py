"""그림 명세(schema/figure.schema.json) → SVG

실제 함수를 표본점으로 계산해 그린다. 결과는 out/figs/{해시}.svg에 캐시한다.
"""
from __future__ import annotations

import html
import math
import re

import numpy as np
import sympy
from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application,
                                        parse_expr, standard_transformations)

from scripts.common import Context, Log, content_hash, is_created_id
from scripts.schemas import validate

X = sympy.Symbol("x", real=True)
T = sympy.Symbol("t", real=True)
_TR = standard_transformations + (implicit_multiplication_application, convert_xor)
_LOCAL = {"x": X, "t": T, "e": sympy.E, "E": sympy.E, "pi": sympy.pi, "ln": sympy.log, "abs": sympy.Abs}

INK, RED, GRAY = "#111111", "#F0503A", "#8a8a8a"
STROKE = {
    "main": (INK, 1.8, None), "sub": (INK, 1.1, None), "dash": (INK, 1.0, "4 3"),
    "red": (RED, 2.0, None), "red-dash": (RED, 1.4, "4 3"), "fill": (INK, 1.2, None),
    "red-fill": (RED, 1.4, None), "open": (INK, 1.2, None), "dot": (INK, 1.2, None),
}
FILL = {"fill": "rgba(17,17,17,0.10)", "red-fill": "rgba(240,80,58,0.20)"}


class FigError(ValueError):
    pass


def expr(s) -> sympy.Expr:
    if isinstance(s, (int, float)):
        return sympy.nsimplify(s)
    try:
        return parse_expr(str(s), local_dict=_LOCAL, transformations=_TR)
    except Exception as e:  # noqa: BLE001
        raise FigError(f"식을 읽을 수 없음: {s} ({e})") from e


def num(s) -> float:
    v = complex(sympy.N(expr(s)))
    if abs(v.imag) > 1e-12 or not math.isfinite(v.real):
        raise FigError(f"실수가 아님: {s}")
    return v.real


def fn_of(s: str, var=X):
    e = expr(s)
    extra = e.free_symbols - {var}
    if extra:
        raise FigError(f"{s}: {var} 외의 문자 {sorted(map(str, extra))}")
    f = sympy.lambdify(var, e, modules=["numpy"])

    def call(arr):
        with np.errstate(all="ignore"):
            y = f(arr)
        y = np.asarray(y, dtype=complex) * np.ones_like(arr)
        out = np.where(np.abs(y.imag) < 1e-9, y.real, np.nan)
        return out.astype(float)
    return call


def _normalize(spec: dict) -> dict:
    spec = dict(spec)
    if spec.get("fn"):
        spec.setdefault("fns", [])
        spec["fns"] = [{"expr": spec.pop("fn"), "domain": spec.pop("domain", None)}] + spec["fns"]
    spec.pop("domain", None)
    return spec


class Canvas:
    def __init__(self, xr, yr, size, equal):
        self.W, self.H = size
        self.m = 16
        (x0, x1), (y0, y1) = xr, yr
        if equal:
            sx = (self.W - 2 * self.m) / (x1 - x0)
            sy = (self.H - 2 * self.m) / (y1 - y0)
            s = min(sx, sy)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            hw, hh = (self.W - 2 * self.m) / s / 2, (self.H - 2 * self.m) / s / 2
            x0, x1, y0, y1 = cx - hw, cx + hw, cy - hh, cy + hh
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.sx = (self.W - 2 * self.m) / (x1 - x0)
        self.sy = (self.H - 2 * self.m) / (y1 - y0)
        self.parts: list[str] = []

    def px(self, x):
        return self.m + (x - self.x0) * self.sx

    def py(self, y):
        return self.H - self.m - (y - self.y0) * self.sy

    def add(self, s):
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, style="main", clip=True):
        c, w, d = STROKE[style]
        dash = f' stroke-dasharray="{d}"' if d else ""
        cl = ' clip-path="url(#CLIP)"' if clip else ""
        self.add(f'<line x1="{self.px(x1):.1f}" y1="{self.py(y1):.1f}" x2="{self.px(x2):.1f}" '
                 f'y2="{self.py(y2):.1f}" stroke="{c}" stroke-width="{w}"{dash}{cl}/>')

    def path(self, pts_list, style="main", fill=None, close=False):
        c, w, d = STROKE[style]
        dash = f' stroke-dasharray="{d}"' if d else ""
        segs = []
        for pts in pts_list:
            if len(pts) < 2:
                continue
            segs.append("M" + " L".join(f"{self.px(x):.1f},{self.py(y):.1f}" for x, y in pts) + (" Z" if close else ""))
        if segs:
            f = fill or "none"
            stroke = c
            self.add(f'<path d="{" ".join(segs)}" fill="{f}" stroke="{stroke}" stroke-width="{w}"'
                     f'{dash} stroke-linejoin="round" clip-path="url(#CLIP)"/>')

    def text(self, x, y, s, pos="ne", color=INK, size=12, raw_px=False):
        X_, Y_ = (x, y) if raw_px else (self.px(x), self.py(y))
        dx = {"e": 6, "ne": 5, "se": 5, "n": 0, "s": 0, "w": -6, "nw": -5, "sw": -5}[pos]
        dy = {"n": -6, "ne": -5, "nw": -5, "e": 4, "w": 4, "s": 14, "se": 13, "sw": 13}[pos]
        anchor = "start" if dx > 0 else ("end" if dx < 0 else "middle")
        italic = "" if re.search(r"[가-힣]", s) else ' font-style="italic"'
        self.add(f'<text x="{X_ + dx:.1f}" y="{Y_ + dy:.1f}" font-size="{size}" fill="{color}" '
                 f'text-anchor="{anchor}" font-family="\'Times New Roman\',serif"{italic}>{_rich(s)}</text>')

    def svg(self) -> str:
        clip = (f'<clipPath id="CLIP"><rect x="{self.m - 2}" y="{self.m - 2}" '
                f'width="{self.W - 2 * self.m + 4}" height="{self.H - 2 * self.m + 4}"/></clipPath>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.W} {self.H}" '
                f'width="{self.W}" height="{self.H}" role="img"><defs>{clip}</defs>{"".join(self.parts)}</svg>')


def _rich(s: str) -> str:
    """라벨의 ^{…}·^c는 위첨자, _{…}·_c는 아래첨자로"""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c in "^_" and i + 1 < len(s):
            if s[i + 1] == "{" and "}" in s[i + 2:]:
                k = s.index("}", i + 2)
                inner, i = s[i + 2:k], k + 1
            else:
                inner, i = s[i + 1], i + 2
            shift = "super" if c == "^" else "sub"
            out.append(f'<tspan baseline-shift="{shift}" font-size="75%">{html.escape(inner)}</tspan>')
        else:
            out.append(html.escape(c))
            i += 1
    return "".join(out)


def _split(xs, ys, yspan):
    """불연속·정의되지 않는 곳에서 끊는다"""
    runs, cur = [], []
    for i, (x, y) in enumerate(zip(xs, ys)):
        if not math.isfinite(y):
            if cur:
                runs.append(cur)
            cur = []
            continue
        if cur and abs(y - cur[-1][1]) > yspan * 0.6:
            runs.append(cur)
            cur = []
        cur.append((float(x), float(y)))
    if cur:
        runs.append(cur)
    return runs


def render_svg(spec: dict) -> str:
    errs = validate("figure", spec)
    if errs:
        raise FigError("; ".join(errs[:3]))
    spec = _normalize(spec)
    size = tuple(spec.get("size") or (320, 220))

    # ---- 범위 추정
    xs_all, ys_all, ys_curve = [], [], []
    fns = []
    for f in spec.get("fns") or []:
        dom = [num(v) for v in (f.get("domain") or spec.get("x") or (-5, 5))]
        call = fn_of(f["expr"])
        xs = np.linspace(dom[0], dom[1], 600)
        ys = call(xs)
        fns.append((f, xs, ys))
        xs_all += dom
        ys_curve += [v for v in ys if math.isfinite(v)]
    params = []
    for pc in spec.get("param") or []:
        t0, t1 = (num(v) for v in pc["t"])
        ts = np.linspace(t0, t1, 600)
        px_, py_ = fn_of(pc["x"], T)(ts), fn_of(pc["y"], T)(ts)
        params.append((pc, px_, py_))
        xs_all += [v for v in px_ if math.isfinite(v)]
        ys_curve += [v for v in py_ if math.isfinite(v)]
    for p in spec.get("points") or []:
        xs_all.append(num(p["x"]))
        ys_all.append(num(p["y"]))
    for s in spec.get("segments") or []:
        for a in (s["from"], s["to"]):
            xs_all.append(num(a[0]))
            ys_all.append(num(a[1]))
    for pg in spec.get("polygons") or []:
        for a in pg["pts"]:
            xs_all.append(num(a[0]))
            ys_all.append(num(a[1]))
    for c in spec.get("circles") or []:
        cx, cy, r = num(c["c"][0]), num(c["c"][1]), num(c["r"])
        xs_all += [cx - r, cx + r]
        ys_all += [cy - r, cy + r]
    for h in spec.get("hlines") or []:
        ys_all.append(num(h["y"]))
    for v in spec.get("vlines") or []:
        xs_all.append(num(v["x"]))
    if spec.get("axes", True):
        xs_all.append(0.0)
        ys_all.append(0.0)
    if not xs_all or not (ys_all or ys_curve):
        raise FigError("그릴 것이 없음")

    if spec.get("x"):
        xr = [num(v) for v in spec["x"]]
    else:
        lo, hi = min(xs_all), max(xs_all)
        pad = (hi - lo) * 0.08 or 1
        xr = [lo - pad, hi + pad]
    if spec.get("y"):
        yr = [num(v) for v in spec["y"]]
    else:
        cand = list(ys_all)
        if ys_curve:
            arr = np.array(ys_curve)
            cand += [float(np.percentile(arr, 1)), float(np.percentile(arr, 99))]
        lo, hi = min(cand), max(cand)
        pad = (hi - lo) * 0.1 or 1
        yr = [float(lo - pad), float(hi + pad)]
    if xr[0] >= xr[1] or yr[0] >= yr[1]:
        raise FigError(f"범위가 잘못됨 x={xr} y={yr}")
    cv = Canvas(xr, yr, size, spec.get("equal", False))
    yspan = cv.y1 - cv.y0

    # ---- 칠하기
    for sh in spec.get("shade") or []:
        a, b = num(sh["from"]), num(sh["to"])
        xs = np.linspace(a, b, 300)
        up, lo = fn_of(sh["upper"])(xs), fn_of(sh.get("lower", "0"))(xs)
        pts = [(float(x), float(y)) for x, y in zip(xs, up) if math.isfinite(y)]
        pts += [(float(x), float(y)) for x, y in zip(xs[::-1], lo[::-1]) if math.isfinite(y)]
        color = "rgba(240,80,58,0.22)" if sh.get("style", "red") == "red" else "rgba(17,17,17,0.12)"
        cv.add(f'<path d="M{" L".join(f"{cv.px(x):.1f},{cv.py(y):.1f}" for x, y in pts)} Z" '
               f'fill="{color}" stroke="none" clip-path="url(#CLIP)"/>')
        if sh.get("label"):
            mx = (a + b) / 2
            my = (float(fn_of(sh["upper"])(np.array([mx]))[0]) + float(fn_of(sh.get("lower", "0"))(np.array([mx]))[0])) / 2
            cv.text(mx, my, sh["label"], pos="e")
    for pg in spec.get("polygons") or []:
        st = pg.get("style", "fill")
        pts = [(num(a[0]), num(a[1])) for a in pg["pts"]]
        cv.path([pts], style=st if st in STROKE else "main", fill=FILL.get(st), close=True)

    # ---- 축
    if spec.get("axes", True):
        ax_y = min(max(0.0, cv.y0), cv.y1)
        ax_x = min(max(0.0, cv.x0), cv.x1)
        cv.add(f'<line x1="{cv.m - 4}" y1="{cv.py(ax_y):.1f}" x2="{cv.W - cv.m + 6}" y2="{cv.py(ax_y):.1f}" '
               f'stroke="{INK}" stroke-width="0.9"/>')
        cv.add(f'<line x1="{cv.px(ax_x):.1f}" y1="{cv.H - cv.m + 4}" x2="{cv.px(ax_x):.1f}" y2="{cv.m - 6}" '
               f'stroke="{INK}" stroke-width="0.9"/>')
        xa, ya = cv.W - cv.m + 6, cv.m - 6
        cv.add(f'<path d="M{xa:.1f},{cv.py(ax_y):.1f} l-6,-3 v6 Z" fill="{INK}"/>')
        cv.add(f'<path d="M{cv.px(ax_x):.1f},{ya:.1f} l-3,6 h6 Z" fill="{INK}"/>')
        cv.text(xa, cv.py(ax_y), "x", pos="se", raw_px=True)
        cv.text(cv.px(ax_x), ya, "y", pos="e", raw_px=True)
        if spec.get("origin", True) and cv.x0 <= 0 <= cv.x1 and cv.y0 <= 0 <= cv.y1:
            cv.text(0, 0, "O", pos="sw")
        ticks = spec.get("ticks") or {}
        for tk in ticks.get("x") or []:
            v = num(tk["at"])
            cv.add(f'<line x1="{cv.px(v):.1f}" y1="{cv.py(ax_y) - 3:.1f}" x2="{cv.px(v):.1f}" '
                   f'y2="{cv.py(ax_y) + 3:.1f}" stroke="{INK}" stroke-width="0.9"/>')
            cv.text(v, ax_y, tk.get("label", _fmt(v)), pos="s", size=11)
        for tk in ticks.get("y") or []:
            v = num(tk["at"])
            cv.add(f'<line x1="{cv.px(ax_x) - 3:.1f}" y1="{cv.py(v):.1f}" x2="{cv.px(ax_x) + 3:.1f}" '
                   f'y2="{cv.py(v):.1f}" stroke="{INK}" stroke-width="0.9"/>')
            cv.text(ax_x, v, tk.get("label", _fmt(v)), pos="w", size=11)

    # ---- 보조선
    for h in spec.get("hlines") or []:
        y = num(h["y"])
        cv.line(cv.x0, y, cv.x1, y, h.get("style", "dash"))
        if h.get("label"):
            cv.text(cv.x1, y, h["label"], pos="nw")
    for v in spec.get("vlines") or []:
        x = num(v["x"])
        cv.line(x, cv.y0, x, cv.y1, v.get("style", "dash"))
        if v.get("label"):
            cv.text(x, cv.y1, v["label"], pos="se")
    for s in spec.get("segments") or []:
        (a0, a1), (b0, b1) = [(num(p[0]), num(p[1])) for p in (s["from"], s["to"])]
        cv.line(a0, a1, b0, b1, s.get("style", "main"))
        if s.get("label"):
            cv.text((a0 + b0) / 2, (a1 + b1) / 2, s["label"], pos="ne")
    for c in spec.get("circles") or []:
        cx, cy, r = num(c["c"][0]), num(c["c"][1]), num(c["r"])
        col, w, d = STROKE[c.get("style", "main")]
        dash = f' stroke-dasharray="{d}"' if d else ""
        cv.add(f'<ellipse cx="{cv.px(cx):.1f}" cy="{cv.py(cy):.1f}" rx="{r * cv.sx:.1f}" ry="{r * cv.sy:.1f}" '
               f'fill="none" stroke="{col}" stroke-width="{w}"{dash} clip-path="url(#CLIP)"/>')

    # ---- 곡선
    for f, xs, ys in fns:
        st = f.get("style", "main")
        cv.path(_split(xs, ys, yspan), style=st)
        for end in f.get("open_ends") or []:
            i = 0 if end == "left" else -1
            if math.isfinite(ys[i]):
                cv.add(f'<circle cx="{cv.px(xs[i]):.1f}" cy="{cv.py(ys[i]):.1f}" r="3" fill="#fff" '
                       f'stroke="{STROKE[st][0]}" stroke-width="1.2"/>')
        if f.get("label"):
            lx = num(f["label_at"]) if f.get("label_at") is not None else xs[int(len(xs) * 0.85)]
            ly = float(fn_of(f["expr"])(np.array([lx]))[0])
            if math.isfinite(ly):
                ly = min(max(ly, cv.y0), cv.y1)
                cv.text(lx, ly, f["label"], pos="ne", color=RED if st.startswith("red") else INK)
    for pc, px_, py_ in params:
        pts = [(float(a), float(b)) for a, b in zip(px_, py_) if math.isfinite(a) and math.isfinite(b)]
        cv.path([pts], style=pc.get("style", "main"))

    # ---- 점·라벨
    for p in spec.get("points") or []:
        x, y = num(p["x"]), num(p["y"])
        st = p.get("style", "dot")
        if p.get("guides"):
            ax_y = min(max(0.0, cv.y0), cv.y1)
            ax_x = min(max(0.0, cv.x0), cv.x1)
            cv.line(x, y, x, ax_y, "dash")
            cv.line(x, y, ax_x, y, "dash")
        fill = "#fff" if st == "open" else (RED if st.startswith("red") else INK)
        stroke = RED if st.startswith("red") else INK
        cv.add(f'<circle cx="{cv.px(x):.1f}" cy="{cv.py(y):.1f}" r="{3.2 if st == "open" else 2.9}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        if p.get("label"):
            cv.text(x, y, p["label"], pos=p.get("pos", "ne"))
    for lb in spec.get("labels") or []:
        st = lb.get("style", "main")
        cv.text(num(lb["at"][0]), num(lb["at"][1]), lb["text"], pos="e",
                color=RED if st.startswith("red") else INK)
    return cv.svg()


def _fmt(v: float) -> str:
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:g}"


# ---------------------------------------------------------------- 단계

def collect(ctx: Context) -> list[tuple[str, dict]]:
    """책에서 쓰는 모든 그림 명세 (위치, 명세)"""
    book = ctx.book
    out = []
    for i, d in enumerate(book.get("days") or []):
        for j, f in enumerate((d.get("concept") or {}).get("figures") or []):
            out.append((f"DAY {d.get('day')} concept/figures/{j}", f))
        if (d.get("strategy") or {}).get("figure"):
            out.append((f"DAY {d.get('day')} strategy/figure", d["strategy"]["figure"]))
        refs = [(d.get("first_pitch") or {}).get("ref")] + [p.get("ref") for p in d.get("practice") or []]
        for r in refs:
            if r and is_created_id(r) and r in ctx.created and ctx.created[r]["rec"].get("figure"):
                out.append((r, ctx.created[r]["rec"]["figure"]))
    for ref, f in (book.get("figures") or {}).items():
        out.append((f"figures/{ref}", f))
    return out


def svg_for(spec: dict, ctx: Context) -> str:
    """캐시(out/figs)를 거쳐 SVG를 돌려준다"""
    key = content_hash(spec)
    path = ctx.out_dir / "figs" / f"{key}.svg"
    if path.exists():
        return path.read_text(encoding="utf-8")
    svg = render_svg(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")
    return svg


def run(ctx: Context) -> Log:
    log = Log("render_figs")
    n = 0
    for where, spec in collect(ctx):
        try:
            svg_for(spec, ctx)
            n += 1
        except Exception as e:  # noqa: BLE001
            log.error(where, f"그림 오류: {e}")
    log.stats = {"figures": n}
    return log
