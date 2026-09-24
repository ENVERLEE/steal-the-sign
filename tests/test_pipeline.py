"""파이프라인 테스트: python -m unittest discover tests

브라우저가 필요한 테스트(KaTeX·조판·판면)는 Chromium이 없으면 건너뛴다.
"""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import (build, check_book, check_created, check_layout, render_figs, report,
                     validate_sources, verify_answers)
from scripts.common import ROOT, Context, launch_chromium, read_json, write_json
from scripts.mathval import run_verify, same_value, tex_to_sympy
from scripts.template import load as load_template
from scripts.tex import split_math

SAMPLE_BOOK = ROOT / "samples" / "book.sample.json"
SAMPLE_CREATED = ROOT / "samples" / "created"


def browser_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            launch_chromium(p).close()
        return True
    except Exception:  # noqa: BLE001
        return False


HAS_BROWSER = browser_available()


class Sandbox:
    """임시 폴더에 문제은행·책·출력 폴더를 만든다"""

    def __init__(self, book: dict | None = None):
        self.dir = Path(tempfile.mkdtemp(prefix="sts-"))
        self.created = self.dir / "created"
        shutil.copytree(SAMPLE_CREATED, self.created)
        self.book = self.dir / "book.json"
        write_json(self.book, book if book is not None else read_json(SAMPLE_BOOK))
        self.out = self.dir / "out"

    def ctx(self) -> Context:
        return Context(book_path=self.book, created_dir=self.created, out_dir=self.out)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestMath(unittest.TestCase):
    def test_tex_to_sympy(self):
        self.assertTrue(same_value(tex_to_sympy(r"\frac97\pi"), "9*pi/7"))
        self.assertTrue(same_value(tex_to_sympy(r"36+30\sqrt3"), "36+30*sqrt(3)"))
        self.assertTrue(same_value(tex_to_sympy(r"\frac72\log_2 3-\frac74"), "7*log(3)/(2*log(2))-7/4"))
        self.assertTrue(same_value(tex_to_sympy(r"2^{\frac94}"), "2**(9/4)"))
        self.assertTrue(same_value(tex_to_sympy(r"\frac{117}{50}"), "2.34"))

    def test_text_answers(self):
        self.assertTrue(same_value("ㄱ, ㄷ", "ㄷ,ㄱ"))
        self.assertFalse(same_value("ㄱ", "ㄴ"))

    def test_all_db_choices_parse(self):
        ctx = Context()
        for r in ctx.db.values():
            if r.get("choices"):
                self.assertTrue(same_value(r["answer_value"], r["choices"][int(r["answer"]) - 1]), r["id"])

    def test_run_verify(self):
        res = run_verify("def skill():\n    return Rational(1, 3) + Rational(1, 6)\n"
                         "def unique():\n    return [1, 2]\n", ["skill", "unique", "standard"], 30)
        self.assertEqual(res["results"]["skill"], "1/2")
        self.assertEqual(res["results"]["unique"], ["1", "2"])
        self.assertIn("standard", res["errors"])
        self.assertIn("*", run_verify("while True:\n    pass\n", ["skill"], 2)["errors"])

    def test_split_math(self):
        parts = split_math(r"넓이 $S=\int_0^t f\,dx+(\text{$t$에 따라})$ 끝 $$x^2$$ \$5")
        self.assertEqual([k for k, _ in parts], ["text", "inline", "text", "display", "text"])
        self.assertIn(r"\text{$t$에 따라}", parts[1][1])
        self.assertTrue(parts[-1][1].endswith("$5"))


class TestSources(unittest.TestCase):
    def test_validate_clean(self):
        with tempfile.TemporaryDirectory() as d:
            log = validate_sources.run(Context(out_dir=d), katex=HAS_BROWSER)
            self.assertEqual(log.errors, [])
            self.assertEqual(read_json(Path(d) / "excluded.json"), [])

    def test_themes_cover_all(self):
        ctx = Context()
        home = [pid for t in ctx.themes.values() for pid in t["problem_ids"]]
        self.assertEqual(sorted(home), sorted(ctx.db))
        self.assertEqual(len(ctx.themes), 28)

    def test_template_compiles(self):
        ctx = Context()
        t = load_template(ctx.path("template"), "")
        self.assertEqual(len(t.pages), 13)


class TestCreated(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.close()

    def test_samples_pass(self):
        log = check_created.run(self.sb.ctx())
        self.assertEqual(log.errors, [])
        for f in self.sb.created.rglob("*.json"):
            self.assertEqual(read_json(f)["status"], "verified")

    def test_detects_problems(self):
        src = read_json(SAMPLE_CREATED / "M1-01" / "C-M1-01-002.json")
        bad = {
            "C-M1-01-003": lambda r: r.update(answer="3", answer_value="5"),
            "C-M1-01-004": lambda r: r.update(distractors=r["distractors"][:2]),
            "C-M1-01-005": lambda r: r["solution"]["solutions"].__setitem__(0, r["solution"]["solutions"][1]),
        }
        for rid, mutate in bad.items():
            r = copy.deepcopy(src)
            r["id"] = rid
            mutate(r)
            write_json(self.sb.created / "M1-01" / f"{rid}.json", r)
        log = check_created.run(self.sb.ctx())
        msgs = {e["where"]: " ".join(x["msg"] for x in log.errors if x["where"] == e["where"]) for e in log.errors}
        self.assertIn("정답", msgs["C-M1-01-003"])
        self.assertIn("distractors", msgs["C-M1-01-004"])
        self.assertIn("스킬", msgs["C-M1-01-005"])

    def test_batch_limit_persists(self):
        src = read_json(SAMPLE_CREATED / "M1-01" / "C-M1-01-002.json")
        for n in range(3, 8):
            r = copy.deepcopy(src)
            r["id"] = f"C-M1-01-{n:03d}"
            r["answer"] = "3"  # 모두 틀리게 → 계속 draft
            write_json(self.sb.created / "M1-01" / f"{r['id']}.json", r)
        for _ in range(2):
            log = check_created.run(self.sb.ctx())
            self.assertTrue(any("한 번에" in e["msg"] for e in log.errors))

    def test_edit_after_verify_rechecks(self):
        ctx = self.sb.ctx()
        check_created.run(ctx)
        f = self.sb.created / "M1-01" / "C-M1-01-001.json"
        r = read_json(f)
        r["answer"] = "11"
        write_json(f, r)
        log = check_created.run(self.sb.ctx())
        self.assertTrue(any(e["where"] == "C-M1-01-001" for e in log.errors))
        self.assertEqual(read_json(f)["status"], "draft")


class TestBook(unittest.TestCase):
    def run_checks(self, book):
        sb = Sandbox(book)
        try:
            ctx = sb.ctx()
            check_created.run(ctx)
            return check_book.run(sb.ctx())
        finally:
            sb.close()

    def test_sample_ok(self):
        log = self.run_checks(read_json(SAMPLE_BOOK))
        self.assertEqual(log.errors, [])
        self.assertEqual(log.stats["problems"], 10)

    def test_rules(self):
        book = read_json(SAMPLE_BOOK)
        d2 = book["days"][1]
        d2["practice"].append({"ref": "M1-270610", "difficulty": "기본 적용"})      # 같은 DAY 중복
        d2["practice"].append({"ref": "M1-260610", "difficulty": "기본 적용"})      # 다른 테마 기출, reuse_note 없음
        d2["practice"].append({"ref": "M2-231110", "difficulty": "기본 적용"})      # 과목 다름·후보 밖·그림
        book["days"][0]["replay"][0]["no"] = 99                                    # 번호 범위 밖
        book["days"][0]["concept"]["core"] += " 스트라이크"                         # 금지어
        msgs = " | ".join(e["msg"] for e in self.run_checks(book).errors)
        for key in ("중복", "reuse_note", "과목", "그림", "REPLAY", "야구 용어"):
            self.assertIn(key, msgs)

    def test_theme_plan(self):
        book = read_json(SAMPLE_BOOK)
        book["days"] = book["days"][:1]
        msgs = " | ".join(e["msg"] for e in self.run_checks(book).errors)
        self.assertIn("DAY 1개", msgs)
        self.assertIn("문항 4개", msgs)


@unittest.skipUnless(HAS_BROWSER, "Chromium 없음")
class TestBuild(unittest.TestCase):
    def test_full_pipeline(self):
        sb = Sandbox()
        try:
            ctx = sb.ctx()
            for mod in (validate_sources, check_created):
                self.assertEqual(mod.run(ctx).errors, [], mod.__name__)
            ctx = sb.ctx()
            for mod in (check_book, verify_answers, render_figs, build, check_layout):
                log = mod.run(ctx)
                log.save(ctx)
                self.assertEqual(log.errors, [], f"{mod.__name__}: {log.errors[:3]}")
            report.run(ctx)
            html = (sb.out / "book.html").read_text(encoding="utf-8")
            self.assertNotIn("[[", html.split("<body>", 1)[1])
            self.assertIn('data-page="BACK_COVER"', html)
            pages = read_json(sb.out / "pages.json")
            self.assertEqual(pages[0]["kind"], "COVER")
            self.assertTrue((sb.out / "report.md").exists())
        finally:
            sb.close()

    def test_figure(self):
        svg = render_figs.render_svg({"fn": "x^3-3x", "domain": [-2, 2], "points": [{"x": 1, "y": -2, "label": "A"}],
                                      "shade": [{"upper": "x^3-3x", "from": -1, "to": 0}]})
        self.assertTrue(svg.startswith("<svg"))
        with self.assertRaises(Exception):
            render_figs.render_svg({"fn": "x^^", "domain": [0, 1]})


if __name__ == "__main__":
    unittest.main()
