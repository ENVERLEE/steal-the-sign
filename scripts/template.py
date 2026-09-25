"""STS_template.html → 페이지별 Jinja2 템플릿

템플릿 규칙(PAGE/REPEAT/OPTION 마커, [[ 슬롯 ]], data-slot 가짜 번호)을 기계적으로 옮긴다.
CSS·마크업은 그대로 두고, 슬롯 자리만 Jinja 식으로 바꾼다. 매핑이 없는 슬롯이 있으면
(템플릿이 바뀐 것이므로) 조용히 넘어가지 않고 오류를 낸다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from jinja2 import Environment, StrictUndefined, Template

PAGE_RE = re.compile(r"<!-- PAGE:START (\w+)[^>]*-->\n?(.*?)<!-- PAGE:END \1 -->", re.S)
REPEAT_RE = re.compile(r"[ \t]*<!-- REPEAT:START (\w+)[^>]*-->\n?(.*?)[ \t]*<!-- REPEAT:END \1 -->\n?", re.S)
OPTION_RE = re.compile(r"[ \t]*<!-- OPTION:.*?-->\s*\n([ \t]*<(\w+) class=\"([\w-]+)[^\n]*)\n", re.S)
SLOT_RE = re.compile(r"\[\[ ?(.*?) ?\]\]")
DSLOT_RE = re.compile(r'<span data-slot="(\w+)">0+</span>')
COMMENT_RE = re.compile(r"<!--.*?-->\n?", re.S)

# REPEAT 이름 → (반복 변수, 목록 식)
REPEATS = {
    "CONTENTS_DAY": ("cd", "P.days"), "CONTENTS_CORNER": ("cc", "cd.corners"),
    "VIZ": ("viz", "P.figures"), "CONCEPT_ROW": ("row", "P.map"),
    "TOOL_ROW": ("tool", "P.tools"),
    "ANALYSIS_STEP": ("pt", "P.points"), "SCOUT_ITEM": ("sc", "P.scouting"),
    "REPLAY_ITEM": ("it", "P.entries"), "BS_CELL": ("n", "P.nos"), "SIGNBOOK_ROW": ("row", "P.rows"),
    "QA_DAY": ("qd", "P.days"), "QA_CELL": ("c", "qd.cells"), "SOL_ITEM": ("s", "P.entries"),
}

# OPTION 블록: 요소의 첫 class → 남길 조건
OPTIONS = {"cond": "q.cond", "fig": "q.fig", "choices": "q.choices", "viz-row": "P.figure", "s-fig": "s.fig"}

# data-slot: (페이지, 반복 범위) → 식. 범위가 없으면 페이지 기본값
DSLOTS = {
    "WEEK": {None: "book.week2"},
    "DAY": {None: "P.day2", "CONTENTS_DAY": "cd.day2", "QA_DAY": "qd.day2"},
    "PAGE": {None: "pg", "CONTENTS_CORNER": "cc.page"},
    "NO": {None: "q.no2", "ANALYSIS_STEP": "pt.no2", "REPLAY_ITEM": "it.no2", "BS_CELL": "n",
           "SIGNBOOK_ROW": "row.no2", "QA_CELL": "c.no2", "SOL_ITEM": "s.no2"},
    "ANS": {"QA_CELL": "c.ans"},
}

# [[ 슬롯 ]] 글자 → 식 (페이지별)
SLOTS = {
    "COVER": {"학년도": "book.year_label", "과목": "book.subject_label", "전체 권 수": "book.total2"},
    "CONTENTS": {"챕터 제목": "cd.title", "코너명": "cc.name", "코너 내용 한 줄": "cc.line"},
    "CONCEPT": {
        "챕터 제목": "P.title",
        "개념을 2~4문장으로. 정의 → 왜 그런지 → 어디에 쓰는지": "P.core",
        "SVG 그림": "viz.svg", "그림에서 볼 곳 한 줄": "viz.caption",
        "일상 비유 2~3문장. 비유의 각 요소가 수학의 무엇에 대응하는지 밝힌다": "P.analogy",
        "이 비유로 생각하면 틀리는 지점 한 줄": "P.analogy_limit",
        "항목": "row.k", "내용": "row.v",
    },
    "STRATEGY": {
        "챕터 제목": "P.title",
        "조건이 주는 정보, 출제자가 요구하는 첫 판단, 주로 측정하는 능력": "P.structure",
        "SVG 그림": "P.figure.svg", "한 줄": "P.figure.caption",
        "실전 개념 이름": "tool.name", "내용(식 포함) · 쓸 수 있는 조건 · 이런 문제에서 떠올린다": "tool.body",
    },
    "FIRST_PITCH": {
        "유형": "P.type", "출처 예: 2026학년도 9월 모의평가 14번": "q.source", "챕터 제목": "P.title",
        "이 챕터에서 읽어야 할 신호와 핵심 질문 1~2문장": "P.signal",
        "문제 본문 (수식은 미리 조판)": "q.text", "조건 박스 내용": "q.cond", "SVG": "q.fig",
    },
    "SIGN_READING": {
        "챕터 제목": "P.title",
        "첫 번째로 해야 할 판단, 막히는 지점의 실마리. 쓸 실전 개념의 이름은 말해도 되지만 풀이는 쓰지 않는다": "P.hint",
        "어떤 조건이 왜 핵심인지 한두 문장": "P.analysis", "판단 포인트": "pt.text",
        "이 문항이 측정하는 능력과 자주 나오는 오답": "P.verdict",
        "출처": "sc.source", "예제와 같은 점 / 다른 점": "sc.note",
    },
    "PRACTICE": {
        "난도": "q.difficulty", "기출/창작": "q.kind", "출처": "q.source", "챕터 제목": "P.title",
        "문제 본문": "q.text", "조건 박스 내용": "q.cond", "SVG": "q.fig",
    },
    "REPLAY": {
        "챕터 제목": "P.title", "학생이 흔히 택하는 접근": "it.wrong",
        "정확히 어디서, 왜 막히는가": "it.stuck", "어떤 신호를 보고 무엇으로 바꾸는가": "it.fix",
    },
    "DUGOUT_NOTE": {"챕터 제목": "P.title"},
    "SIGN_BOOK": {
        "챕터 제목": "P.title", "신호": "row.signal", "개념·방법": "row.method",
        "이 챕터의 판단이 다음 DAY에서 어떻게 확장되는가": "P.next",
    },
    "QUICK_ANSWER": {"챕터 제목": "qd.title"},
    "SOLUTION": {
        "챕터 제목": "P.title", "예제/연습": "s.kind", "출처": "s.source", "정답": "s.answer",
        "실전 개념을 쓴 빠른 풀이. 식 위주 2~5줄": "s.shortcut", "작은 SVG": "s.fig",
        "교과서 방법의 풀이. 식 위주, 핵심 단계만": "s.standard",
        "개념 이름 — 한 줄 요약 · 팁": "s.tip",
        "많이 고르는 오답 → 왜 그렇게 틀리는지 → 한 줄 교정": "s.error",
    },
    "BACK_COVER": {"학년도": "book.year_label"},
}


WEEK_TOKEN = "\ue002WEEK\ue003"


class TemplateError(RuntimeError):
    pass


def _specials(name: str, body: str) -> str:
    """구조를 바꾸지 않는 선에서 필요한 치환 (권 칸 수, 선지, 배점, 없는 해설 줄)"""
    if name == "COVER":
        body, n = re.subn(r"(?:[ \t]*<div class=\"wk[^\n]*\n)+",
                          "      {% for w in book.weeks %}<div class=\"wk{{ ' now' if w.now else '' }}\">"
                          "{{ w.label }}</div>{% endfor %}\n", body)
        if n != 1:
            raise TemplateError("COVER 권 칸(.wk) 구조가 바뀜")
    if name in ("FIRST_PITCH", "PRACTICE"):
        body, n = re.subn(r'<div class="choices">(?:<div>[①②③④⑤] \[\[ \]\]</div>){5}</div>',
                          '<div class="choices{{ q.choices_class }}">{% for c in q.choices %}'
                          '<div>{{ c.label }} {{ c.html }}</div>{% endfor %}</div>', body)
        body, m = re.subn(r'<span class="pt">\[4점\]</span>', '<span class="pt">[{{ q.points }}점]</span>', body)
        if n != 1 or m != 1:
            raise TemplateError(f"{name} 선지·배점 구조가 바뀜")
        body = "{% set q = P.q %}" + body
    if name == "CONCEPT":
        body, n = re.subn(r'([ \t]*<div class="viz-row">.*?REPEAT:END VIZ -->\n\s*</div>\n)',
                          r"{% if P.figures %}\1{% endif %}", body, flags=re.S)
        if n != 1:
            raise TemplateError("CONCEPT viz-row 구조가 바뀜")
    if name == "SOLUTION":
        for key, cond in (('<b class="lb alt">정석</b>', "s.standard"), ('class="s-tip"', "s.tip"),
                          ('class="s-err"', "s.error")):
            body, n = re.subn(r"([ \t]*<p[^\n]*" + re.escape(key) + r"[^\n]*\n)",
                              "{% if " + cond + r" %}\1{% endif %}", body)
            if n != 1:
                raise TemplateError(f"SOLUTION '{key}' 줄 구조가 바뀜")
    return body


def _slots(text: str, name: str, scope: str | None) -> str:
    def ds(m):
        key = m.group(1)
        table = DSLOTS.get(key) or {}
        expr = table.get(scope) or table.get(None)
        if not expr:
            raise TemplateError(f"{name}/{scope}: data-slot {key} 매핑 없음")
        return f'<span data-slot="{key}">{{{{ {expr} }}}}</span>'

    def sl(m):
        expr = SLOTS.get(name, {}).get(m.group(1).strip())
        if not expr:
            raise TemplateError(f"{name}: 슬롯 [[ {m.group(1)} ]] 매핑 없음 (템플릿이 바뀌었으면 scripts/template.py SLOTS 수정)")
        return "{{ " + expr + " }}"
    return SLOT_RE.sub(sl, DSLOT_RE.sub(ds, text))


def _compile(text: str, name: str, scope: str | None) -> str:
    out, pos = [], 0
    for m in REPEAT_RE.finditer(text):
        out.append(_slots(text[pos:m.start()], name, scope))
        rname = m.group(1)
        if rname not in REPEATS:
            raise TemplateError(f"{name}: REPEAT {rname} 매핑 없음")
        var, src = REPEATS[rname]
        out.append(f"{{% for {var} in {src} %}}" + _compile(m.group(2), name, rname) + "{% endfor %}\n")
        pos = m.end()
    out.append(_slots(text[pos:], name, scope))
    return "".join(out)


def _options(body: str, name: str) -> str:
    def rep(m):
        cls = m.group(3)
        cond = OPTIONS.get(cls)
        if not cond:
            raise TemplateError(f"{name}: OPTION 요소 class={cls} 매핑 없음")
        return "{% if " + cond + " %}" + m.group(1) + "{% endif %}\n"
    return OPTION_RE.sub(rep, body)


@dataclass
class PageTemplates:
    head: str                      # <head>…</head> (KaTeX CSS 내장, 제목의 권 번호는 WEEK_TOKEN)
    pages: dict[str, Template]
    sources: dict[str, str]        # 컴파일된 Jinja 원문(디버그용)


def load(path, katex_css: str) -> PageTemplates:
    raw = path.read_text(encoding="utf-8")
    m = re.search(r"<head>.*?</head>", raw, re.S)
    if not m:
        raise TemplateError("템플릿에 <head>가 없음")
    head = m.group(0)
    head = head.replace("[[ WEEK ]]", WEEK_TOKEN)
    head, n = re.subn(r"<!-- SLOT: 미리 조판한 KaTeX[^>]*-->", lambda _: "<style>" + katex_css + "</style>", head)
    if n != 1:
        raise TemplateError("head의 KaTeX SLOT 주석이 없음")
    env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
    pages, sources = {}, {}
    for pm in PAGE_RE.finditer(raw):
        name, body = pm.group(1), pm.group(2)
        body = _options(body, name)
        body = _specials(name, body)
        body = _compile(body, name, None)
        body = COMMENT_RE.sub("", body)
        if "[[" in body or re.search(r'data-slot="\w+">0+<', body):
            raise TemplateError(f"{name}: 채우지 못한 슬롯이 남음")
        sources[name] = body
        pages[name] = env.from_string(body)
    need = {"COVER", "CONTENTS", "CONCEPT", "STRATEGY", "FIRST_PITCH", "SIGN_READING", "PRACTICE",
            "REPLAY", "DUGOUT_NOTE", "SIGN_BOOK", "QUICK_ANSWER", "SOLUTION", "BACK_COVER"}
    if need - set(pages):
        raise TemplateError(f"템플릿에 없는 페이지: {sorted(need - set(pages))}")
    return PageTemplates(head=head, pages=pages, sources=sources)


XPAGE_RE = re.compile(r"<!-- XPAGE:START (\w+) -->\n?(.*?)<!-- XPAGE:END \1 -->", re.S)
HEAD_RE = re.compile(r"<!-- HEAD:START -->\n?(.*?)<!-- HEAD:END -->", re.S)


def load_ext(path) -> tuple[str, dict[str, Template]]:
    """STS_ext.html: head 끝에 덧붙일 블록(웹 글꼴·확장 CSS)과 교과서형 페이지(Jinja)"""
    raw = path.read_text(encoding="utf-8")
    m = HEAD_RE.search(raw)
    if not m:
        raise TemplateError("확장 템플릿에 HEAD 블록이 없음")
    env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
    pages = {pm.group(1): env.from_string(pm.group(2)) for pm in XPAGE_RE.finditer(raw)}
    need = {"CONCEPT_X", "STRATEGY_X", "SIGN_READING_X"}
    if need - set(pages):
        raise TemplateError(f"확장 템플릿에 없는 페이지: {sorted(need - set(pages))}")
    return m.group(1), pages
