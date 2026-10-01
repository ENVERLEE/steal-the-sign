"""변형 창작 문항 뼈대: 부모 기출을 복사해 `work/created/{테마}/C-{테마}-NNN.json`을 만든다.

  python run.py new --parent M1-230911 [--theme M1-01] [--variation 수치]

AI는 빈 칸부터 쓰지 않고 이 파일에서 바뀌는 부분(본문·정답·풀이·verify)만 고친다.
AI API를 부르지 않는다. 만든 파일은 draft이고 `python run.py created`를 통과해야 쓸 수 있다.
"""
from __future__ import annotations

import re

from scripts.common import Context, Log, write_json

VARIATIONS = ("수치", "조건", "역방향", "일반화", "결합")


def next_id(ctx: Context, theme: str) -> str:
    nums = [int(m.group(1)) for rid in ctx.created
            if (m := re.fullmatch(rf"C-{re.escape(theme)}-(\d{{3}})", rid)) and int(m.group(1)) < 100]
    return f"C-{theme}-{max(nums, default=0) + 1:03d}"


def run(ctx: Context, parent: str | None, theme: str | None = None, variation: str = "수치") -> Log:
    log = Log("new_created")
    p = ctx.db.get(parent or "")
    if not p:
        log.error(parent or "--parent", "data/problems에 없는 기출 id")
        return log
    theme = theme or ctx.home.get(parent)
    if theme not in ctx.themes:
        log.error(theme or "theme", "themes.json에 없는 테마")
        return log
    if variation not in VARIATIONS:
        log.error(variation, f"variation은 {'·'.join(VARIATIONS)} 중 하나")
        return log
    st = ctx.study.get(parent) or {}
    rid = next_id(ctx, theme)
    rec = {
        "id": rid, "theme": theme,
        "origin": {"type": "variant", "parent_id": parent, "variation": variation, "note": "TODO: 무엇을 어떻게 바꿨는지 한 줄"},
        "target": {"concept_ids": st.get("concept_refs") or [], "strategy_ids": p.get("strategy_ids") or [],
                   "first_judgment": p.get("first_judgment") or ""},
        "difficulty": "기본 적용", "behavior": p.get("behavior") or "이해",
        "question": p["question"], "condition": p.get("condition"),
        "choices": None, "answer": "TODO", "answer_value": "TODO", "figure": None,
        "solution": {"concept_refs": st.get("concept_refs") or [], "guide": st.get("guide") or "",
                     "solutions": st.get("solutions") or [], "supplement": st.get("supplement") or "",
                     "skill_point": st.get("skill_point") or ""},
        "verify": "def skill():\n    return None\n\ndef standard():\n    return None\n\ndef unique():\n    return []\n",
    }
    path = ctx.created_dir / theme / f"{rid}.json"
    write_json(path, rec)
    log.stats.update({"id": rid, "file": str(path)})
    print(f"{rid} → {path}\n부모 본문·풀이가 복사돼 있다. 바뀌는 부분만 고치고 TODO를 없앤 뒤 python run.py created")
    return log
