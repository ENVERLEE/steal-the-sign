"""공통 유틸: 설정·경로·JSON 입출력·로그·데이터 로딩·브라우저 실행."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- JSON

def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def content_hash(data) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- 로그

@dataclass
class Log:
    """단계별 오류·경고·통계. out/logs/{stage}.json으로 저장되어 report가 모은다."""
    stage: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def error(self, where: str, msg: str) -> None:
        self.errors.append({"where": where, "msg": msg})

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append({"where": where, "msg": msg})

    @property
    def ok(self) -> bool:
        return not self.errors

    def save(self, ctx: "Context") -> None:
        write_json(ctx.logs / f"{self.stage}.json",
                   {"stage": self.stage, "at": now(), "errors": self.errors,
                    "warnings": self.warnings, "stats": self.stats})

    def print_summary(self) -> None:
        mark = "OK " if self.ok else "ERR"
        print(f"[{mark}] {self.stage}: 오류 {len(self.errors)} · 경고 {len(self.warnings)}")
        for e in self.errors[:30]:
            print(f"   ✕ {e['where']}: {e['msg']}")
        if len(self.errors) > 30:
            print(f"   … 오류 {len(self.errors) - 30}개 더 (out/logs/{self.stage}.json)")
        for w in self.warnings[:10]:
            print(f"   △ {w['where']}: {w['msg']}")
        if len(self.warnings) > 10:
            print(f"   … 경고 {len(self.warnings) - 10}개 더 (out/logs/{self.stage}.json)")


# ---------------------------------------------------------------- 컨텍스트

@dataclass
class Context:
    """경로와 데이터를 한곳에서 읽는다. CLI 옵션으로 book·created·source·out을 바꿀 수 있다."""
    book_path: Path | None = None
    created_dir: Path | None = None
    out_dir: Path | None = None
    source_dir: Path | None = None

    def __post_init__(self):
        p = self.config["paths"]
        self.book_path = Path(self.book_path or ROOT / p["book"])
        self.created_dir = Path(self.created_dir or ROOT / p["created"])
        self.source_dir = Path(self.source_dir or ROOT / p["source"])
        self.out_dir = Path(self.out_dir or ROOT / p["out"])

    @cached_property
    def config(self) -> dict:
        return read_json(ROOT / "data" / "config.json")

    def path(self, key: str) -> Path:
        return ROOT / self.config["paths"][key]

    @property
    def logs(self) -> Path:
        return self.out_dir / "logs"

    @property
    def excluded_path(self) -> Path:
        return self.out_dir / "excluded.json"

    # ---- 데이터
    @cached_property
    def db(self) -> dict:
        return {r["id"]: r for r in read_json(self.path("db"))}

    @cached_property
    def solutions(self) -> dict:
        return read_json(self.path("solutions"))

    @cached_property
    def study(self) -> dict:
        """문항 id → study_solution"""
        return {p["id"]: p["study_solution"] for p in self.solutions["problems"]}

    @cached_property
    def old_themes(self) -> dict:
        """기존 64분류 id → solutions.json 테마 개념정리"""
        return {t["theme"]: t for t in self.solutions["themes"]}

    @cached_property
    def concepts(self) -> dict:
        """개념 id → 개념"""
        return {c["id"]: c for t in self.solutions["themes"] for c in t["core_concepts"]}

    @cached_property
    def themes(self) -> dict:
        return {t["id"]: t for t in read_json(self.path("themes"))["themes"]}

    @cached_property
    def strategies(self) -> dict:
        return {s["id"]: s for s in read_json(self.path("strategy_notes"))["items"]}

    @cached_property
    def excluded(self) -> set:
        if self.excluded_path.exists():
            return {e["id"] for e in read_json(self.excluded_path)}
        return set()

    @cached_property
    def created(self) -> dict:
        return load_created(self.created_dir)

    @cached_property
    def source(self) -> dict:
        return load_source(self.source_dir)

    @cached_property
    def book(self) -> dict:
        return read_json(self.book_path)


def load_created(created_dir: Path) -> dict:
    """문제은행: id → (경로, 레코드)"""
    bank = {}
    if created_dir.exists():
        for f in sorted(created_dir.rglob("*.json")):
            rec = read_json(f)
            bank[rec.get("id", f.stem)] = {"path": f, "rec": rec}
    return bank


# ---------------------------------------------------------------- 공통 판정

def load_source(source_dir: Path) -> dict:
    """교재 판독 문항: id → (경로, 레코드, 교재 정보). 교재 하나 = work/source/{교재id}.json"""
    bank = {}
    if source_dir.exists():
        for f in sorted(source_dir.glob("*.json")):
            data = read_json(f)
            for i, rec in enumerate(data.get("problems") or []):
                bank[rec.get("id", f"{f.stem}#{i}")] = {"path": f, "index": i, "rec": rec, "book": data.get("book") or {}}
    return bank


def is_textbook_id(ref: str) -> bool:
    return ref.startswith("T-")


def is_created_id(ref: str) -> bool:
    return ref.startswith("C-")


def has_choices(rec: dict) -> bool:
    return bool(rec.get("choices"))


CIRCLED = "①②③④⑤"


def choice_text(c: str) -> str:
    """db.json 선지는 $ 없이 LaTeX만 적혀 있다(\\frac{5}{3}). ㄱ·ㄴ·ㄷ 같은 글자 선지는 그대로"""
    c = str(c)
    if "$" in c or re.search(r"[가-힣ㄱ-ㅎ]", c):
        return c
    return f"${c}$"


def answer_display(rec: dict) -> str:
    """정답표·해설용 정답 표기: 객관식은 ②, 단답형은 숫자"""
    ans = str(rec["answer"]).strip()
    if has_choices(rec) and ans.isdigit() and 1 <= int(ans) <= 5:
        return CIRCLED[int(ans) - 1]
    return ans


def source_label(rec: dict) -> str:
    """기출 출처 표기: 2026학년도 9월 모의평가 14번"""
    s = rec["source"]
    return f"{s['year']}학년도 {s['exam']} {s['number']}번"


def kind_of(ref: str) -> str:
    """기출 | 창작 | 교재"""
    return "창작" if is_created_id(ref) else ("교재" if is_textbook_id(ref) else "기출")


def strip_tex(text: str) -> str:
    """글자 수 비교용: 수식 기호를 걷어 낸 길이 근사"""
    return re.sub(r"\\[a-zA-Z]+|[{}$\\^_]", "", text or "")


# ---------------------------------------------------------------- 브라우저

def launch_chromium(playwright):
    """Playwright 기본 브라우저 → 없으면 설치된 Chromium을 찾아 실행한다."""
    try:
        return playwright.chromium.launch()
    except Exception as first:
        candidates = []
        if os.environ.get("STS_CHROMIUM"):
            candidates.append(Path(os.environ["STS_CHROMIUM"]))
        base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        roots = [Path(base)] if base else []
        home = Path.home()
        roots += [home / ".cache" / "ms-playwright",
                  home / "Library" / "Caches" / "ms-playwright",
                  home / "AppData" / "Local" / "ms-playwright"]
        for r in roots:
            if r.exists():
                for pat in ("chromium-*/chrome-linux*/chrome", "chromium-*/chrome-win*/chrome.exe",
                            "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
                            "chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"):
                    candidates += sorted(r.glob(pat), reverse=True)
        for c in candidates:
            if c.exists():
                return playwright.chromium.launch(executable_path=str(c))
        raise RuntimeError(
            "Chromium을 찾지 못했습니다. `python -m playwright install chromium`을 실행하거나 "
            "환경변수 STS_CHROMIUM에 브라우저 경로를 지정하세요.") from first


FONT_HOSTS = ("https://fonts.googleapis.com/", "https://fonts.gstatic.com/")


def route_network(page, allow_fonts: bool = True) -> None:
    """외부 요청 차단. 판면 측정을 위해 템플릿의 웹 글꼴(Google Fonts)만 허용한다(스크립트 CDN 금지)."""
    def handle(route):
        url = route.request.url
        if allow_fonts and url.startswith(FONT_HOSTS):
            route.continue_()
        else:
            route.abort()
    page.route(re.compile(r"^https?://"), handle)


def ensure_utf8_stdout() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
