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

from scripts import (build, check_book, check_created, check_layout, check_source, curate, export_pdf, pdf_pages,
                     render_figs, report, validate_sources, verify_answers)
from scripts.common import ROOT, Context, launch_chromium, read_json, write_json
from scripts.mathval import run_verify, same_value, tex_to_sympy
from scripts.template import load as load_template
from scripts.tex import split_math

SAMPLE_BOOK = ROOT / "samples" / "book.sample.json"
SAMPLE_CREATED = ROOT / "samples" / "created"
SAMPLE_SOURCE = ROOT / "samples" / "source"


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
        self.source = self.dir / "source"
        shutil.copytree(SAMPLE_SOURCE, self.source)
        self.book = self.dir / "book.json"
        write_json(self.book, book if book is not None else read_json(SAMPLE_BOOK))
        self.out = self.dir / "out"

    def ctx(self) -> Context:
        return Context(book_path=self.book, created_dir=self.created, out_dir=self.out, source_dir=self.source)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestDataLayout(unittest.TestCase):
    """data/problems·solutions 문항별 파일 구조"""

    def test_problem_files(self):
        ctx = Context()
        self.assertGreaterEqual(len(ctx.db), 208)
        for pid, r in ctx.problem_files.items():
            self.assertEqual(r["id"], pid)
            self.assertIn(r["home"], ctx.themes)
            self.assertIn(pid, ctx.study)
        self.assertNotIn("home", next(iter(ctx.db.values())))

    def test_theme_problem_ids_from_home(self):
        ctx = Context()
        ids = [p for t in ctx.themes.values() for p in t["problem_ids"]]
        self.assertEqual(sorted(ids), sorted(ctx.db))

    def test_book_dir_roundtrip(self):
        from scripts.book_dir import load_dir, split
        box = Sandbox()
        try:
            ctx = box.ctx()
            self.assertTrue(split(ctx).ok)
            self.assertEqual(load_dir(box.book.with_suffix("")), read_json(box.book))
        finally:
            box.close()


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

    def test_rich_markup(self):
        # **굵게**·__밑줄__은 수식을 사이에 두어도 태그가 되고, 수식 뒤 조사는 수식과 한 덩어리로 묶인다
        from scripts.tex import Math
        h = Math().rich("가 **굵게 $x$에** 그리고 __$y$가 축__")
        self.assertIn("<b>굵게 <span class=\"nw\">", h)
        self.assertIn("에</span></b>", h)
        self.assertIn("<u><span class=\"nw\">", h)
        self.assertNotIn("**", h)

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
        check_created.run(self.sb.ctx())  # 샘플 2문항을 먼저 통과시켜 검사 대기 한도(4)를 비운다
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


class TestMock(unittest.TestCase):
    def test_import_makes_draft(self):
        from scripts import mock_import
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.json"
            write_json(src, {"wrong": [{"no": 12, "text": "$x^2=4$의 실근의 합은?", "options": ["$0$", "$1$", "$2$", "$3$", "$4$"],
                                        "correct": 1, "reason": "부호 실수", "tags": ["계산실수"], "subject": "수1"},
                                       {"no": 13}], "patterns": ["지수 부호"]})
            ctx = Context(source_dir=Path(d) / "source", out_dir=Path(d) / "out")
            log = mock_import.run(ctx, json_path=str(src), book_id="mk1", title="실모 제1회")
            self.assertEqual(log.errors, [])
            draft = read_json(Path(d) / "mock" / "MK1_draft.json")
            self.assertTrue(draft["book"]["mock"])
            self.assertEqual(len(draft["problems"]), 1)          # 본문 없는 항목은 건너뜀
            p = draft["problems"][0]
            self.assertEqual((p["id"], p["number"], p["subject"]), ("T-MK1-001", "12", "수학Ⅰ"))
            self.assertEqual(p["mistake"]["reason"], "부호 실수")
            self.assertEqual(read_json(Path(d) / "source" / "MK1" / "pages.json")["title"], "실모 제1회")

    def test_mock_problem_has_no_page_label(self):
        rec = {"id": "T-MK1-001", "number": "12", "page": None}
        # 쪽이 없으면 출처는 '{title} {번호}번'
        m = build.Model.source_of.__get__(type("M", (), {"ctx": type("C", (), {"source": {"T-MK1-001": {"book": {"title": "실모 제1회"}}}})()})())
        self.assertEqual(m("T-MK1-001", rec), "실모 제1회 12번")


class TestMockGroups(unittest.TestCase):
    def test_korean_keys_group_by_exam_and_bad_backslash(self):
        from scripts import mock_import
        raw = ('{"종합_분석": {"x": 1}, "오답_노트": [{"모의고사_이름": "실모 A", "문항_번호": "확률과 통계 27번", '
               '"문제_텍스트": "$\\pi < \\theta < 2\\pi$인 $\\theta$에 대하여 $\\tan\\theta=-\\frac{12}{5}$일 때 값은?", "틀린_이유": "부호"},'
               '{"모의고사_이름": "실모 B", "문항_번호": "3번", "문제_텍스트": "짧다..."}]}')
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.json"
            src.write_text(raw, encoding="utf-8")
            ctx = Context(source_dir=Path(d) / "source", out_dir=Path(d) / "out")
            log = mock_import.run(ctx, json_path=str(src))
            self.assertEqual(log.errors, [])
            a = read_json(Path(d) / "mock" / "MK1_draft.json")
            self.assertEqual(a["book"]["title"], "실모 A")
            p = a["problems"][0]
            self.assertEqual((p["number"], p["subject"], p["text_complete"]), ("27", "확률과 통계", True))
            self.assertIn("\\tan", p["question"])
            b = read_json(Path(d) / "mock" / "MK2_draft.json")
            self.assertFalse(b["problems"][0]["text_complete"])


class TestAppendix(unittest.TestCase):
    def test_calc_bank_rules(self):
        sb = Sandbox()
        try:
            ctx = sb.ctx()
            self.assertEqual(check_created.run(ctx).errors, [])
            ctx = sb.ctx()
            book = read_json(sb.book)
            self.assertEqual(check_book.run(ctx).errors, [])
            # DAY 연습에 부록 전용 창작을 쓰면 오류
            book["days"][0]["practice"][0]["ref"] = "C-M1-01-101"
            write_json(sb.book, book)
            errs = check_book.run(sb.ctx()).errors
            self.assertTrue(any("부록 전용" in m["msg"] if isinstance(m, dict) else "부록 전용" in str(m) for m in errs))
        finally:
            sb.close()

    def test_calc_batch_is_separate(self):
        sb = Sandbox()
        try:
            for f in sb.created.rglob("*.json"):   # 계산 8개 + 일반 창작을 모두 미검사로
                rec = read_json(f)
                rec.pop("status", None)
                rec.pop("review", None)
                write_json(f, rec)
            log = check_created.run(sb.ctx())
            self.assertEqual(log.errors, [])       # 일반 2개(한도 4)와 계산 8개(한도 10)가 따로 세어져 모두 통과
        finally:
            sb.close()


class TestBook(unittest.TestCase):
    def run_checks(self, book):
        sb = Sandbox(book)
        try:
            ctx = sb.ctx()
            check_created.run(ctx)
            check_source.run(ctx)
            return check_book.run(sb.ctx())
        finally:
            sb.close()

    def test_sample_ok(self):
        log = self.run_checks(read_json(SAMPLE_BOOK))
        self.assertEqual(log.errors, [])
        self.assertEqual(log.stats["problems"], 12)
        self.assertEqual(log.stats["textbook"], 3)

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
        self.assertIn("문항 5개", msgs)


class TestTextbook(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.close()

    def test_source_passes(self):
        log = check_source.run(self.sb.ctx())
        self.assertEqual(log.errors, [])
        self.assertEqual(log.stats["verified"], 3)

    def test_source_detects(self):
        f = self.sb.source / "SMP.json"
        data = read_json(f)
        data["problems"][0]["answer_value"] = "1"           # verify와 불일치
        data["problems"][1]["similar"] = ["M1-999999"]       # 없는 기출
        data["problems"][2]["theme"] = "M2-01"               # 과목 불일치
        write_json(f, data)
        log = check_source.run(self.sb.ctx())
        by = {e["where"]: e["msg"] for e in log.errors}
        self.assertIn("정답", by["T-SMP-001"])
        self.assertIn("M1-999999", by["T-SMP-002"])
        self.assertIn("과목", by["T-SMP-003"])

    def test_literal_newline_detected(self):
        # 줄바꿈을 두 번 이스케이프하면 교재에 '\n'이 글자 그대로 찍힌다. LaTeX \ne는 허용
        f = self.sb.source / "SMP.json"
        data = read_json(f)
        data["problems"][0]["solution"]["guide"] = "첫 줄\\n둘째 줄, $a\\ne0$"
        write_json(f, data)
        log = check_source.run(self.sb.ctx())
        msgs = [e["msg"] for e in log.errors if e["where"] == "T-SMP-001"]
        self.assertTrue(any("\\n" in m and "solution/guide" in m for m in msgs), msgs)
        data["problems"][0]["solution"]["guide"] = "첫 줄\n둘째 줄, $a\\ne0$"
        write_json(f, data)
        log = check_source.run(self.sb.ctx(), recheck=True)
        self.assertEqual([e for e in log.errors if e["where"] == "T-SMP-001"], [])

    def test_control_char_detected(self):
        # r-문자열이 아닌 곳에서 \rfloor·\theta가 \r·\t로 깨진다. 풀이 제목·단계 이름도 검사
        f = self.sb.source / "SMP.json"
        data = read_json(f)
        data["problems"][0]["solution"]["solutions"][0]["title"] = "풀이 1 · $\\lfloor x\rfloor$"
        write_json(f, data)
        log = check_source.run(self.sb.ctx())
        msgs = [e["msg"] for e in log.errors if e["where"] == "T-SMP-001"]
        self.assertTrue(any("제어문자" in m and "title" in m for m in msgs), msgs)

    def test_curate_plan(self):
        ctx = self.sb.ctx()
        check_created.run(ctx)
        check_source.run(ctx)
        log = curate.run(self.sb.ctx())
        plan = read_json(self.sb.out / "plan.json")["themes"][0]
        self.assertEqual(plan["theme"], "M1-01")
        self.assertEqual([d["first_pitch"] for d in plan["days"]], ["T-SMP-001", "T-SMP-002", "T-SMP-003"])
        self.assertGreaterEqual(plan["counts"]["past"], 5)
        self.assertTrue(8 <= plan["counts"]["total"] <= 13, plan["counts"])
        self.assertIn("M1-230911", plan["days"][0]["practice"] + plan["days"][0]["scouting"])
        self.assertTrue((self.sb.out / "curation.md").exists())
        self.assertEqual(log.errors, [])

    def test_book_textbook_rules(self):
        book = read_json(SAMPLE_BOOK)
        book["days"][1]["practice"] = [p for p in book["days"][1]["practice"] if p["ref"] != "T-SMP-003"]
        book["days"][1]["practice"].append({"ref": "M1-220610", "difficulty": "기본 적용"})
        write_json(self.sb.book, book)
        ctx = self.sb.ctx()
        check_created.run(ctx)
        check_source.run(ctx)
        log = check_book.run(self.sb.ctx())
        self.assertEqual(log.errors, [])
        self.assertTrue(any("T-SMP-003" in w["msg"] for w in log.warnings))

    @unittest.skipUnless(HAS_BROWSER, "Chromium 없음")
    def test_pdf_pages(self):
        from playwright.sync_api import sync_playwright
        pdf = self.sb.dir / "book.pdf"
        with sync_playwright() as p:
            b = launch_chromium(p)
            pg = b.new_page()
            pg.set_content("<h1>1</h1><div style='page-break-after:always'></div><h1>2</h1>")
            pg.pdf(path=str(pdf), format="A4")
            b.close()
        # 출처 표기는 사용자가 정한다: --title 없이는 거절
        self.assertTrue(pdf_pages.run(self.sb.ctx(), pdf=str(pdf), book_id="smp").errors)
        log = pdf_pages.run(self.sb.ctx(), pdf=str(pdf), book_id="smp", title="샘플 교재")
        self.assertEqual(log.errors, [])
        self.assertEqual(log.stats["pages"], 2)
        self.assertTrue((self.sb.source / "SMP" / "pages" / "p002.png").exists())
        self.assertEqual(read_json(self.sb.source / "SMP" / "pages.json")["title"], "샘플 교재")

    def test_source_title_is_user_input(self):
        # 판독 파일의 book.title은 사용자가 입력한 표기(pages.json title)와 같아야 한다
        f = self.sb.source / "SMP.json"
        data = read_json(f)
        data["book"]["title"] = "AI가 줄인 이름"
        write_json(f, data)
        log = check_source.run(self.sb.ctx())
        self.assertTrue(any("표기" in e["msg"] for e in log.errors), log.errors)
        pdf_pages.set_title(self.sb.ctx(), book_id="SMP", title="새 표기")
        self.assertEqual(read_json(f)["book"]["title"], "새 표기")
        self.assertEqual(check_source.run(self.sb.ctx()).errors, [])


@unittest.skipUnless(HAS_BROWSER, "Chromium 없음")
class TestBuild(unittest.TestCase):
    def test_full_pipeline(self):
        sb = Sandbox()
        try:
            ctx = sb.ctx()
            for mod in (validate_sources, check_created, check_source):
                self.assertEqual(mod.run(ctx).errors, [], mod.__name__)
            ctx = sb.ctx()
            for mod in (check_book, verify_answers, render_figs, build, check_layout, export_pdf):
                log = mod.run(ctx)
                log.save(ctx)
                self.assertEqual(log.errors, [], f"{mod.__name__}: {log.errors[:3]}")
            report.run(ctx)
            html = (sb.out / "book.html").read_text(encoding="utf-8")
            self.assertNotIn("[[", html.split("<body>", 1)[1])
            self.assertIn('data-page="BACK_COVER"', html)
            # DAY 1은 기존형, DAY 2는 교과서형(STS_ext.html) — 두 형식이 한 책에 함께 조판된다
            self.assertIn('class="x-body"', html)
            self.assertIn("Noto+Serif+KR", html)
            self.assertIn('<div class="box-label">비유로 이해하기</div>', html)
            pages = read_json(sb.out / "pages.json")
            self.assertEqual(pages[0]["kind"], "COVER")
            self.assertTrue((sb.out / "report.md").exists())
            import pypdfium2 as pdfium
            self.assertEqual(len(pdfium.PdfDocument(str(sb.out / "book.pdf"))), len(pages))
            # 부록(계산 연습): 목차에 오르고 CALC·CALC_SOL 쪽이 있다
            self.assertIn('data-page="CALC"', html)
            self.assertIn('data-page="CALC_SOL"', html)
            kinds = [p["kind"] for p in pages]
            self.assertEqual(kinds[:3], ["COVER", "ADVICE", "CONTENTS"])
            self.assertLess(kinds.index("CALC"), kinds.index("BACK_COVER"))
            cap = ctx.config["solution"]["per_page_max"] or 99
            for chunk in html.split('data-page="SOLUTION"')[1:]:
                self.assertLessEqual(chunk.split('data-page=')[0].count('<article class="s"'), cap)
        finally:
            sb.close()

    def test_figure(self):
        svg = render_figs.render_svg({"fn": "x^3-3x", "domain": [-2, 2], "points": [{"x": 1, "y": -2, "label": "A"}],
                                      "shade": [{"upper": "x^3-3x", "from": -1, "to": 0}]})
        self.assertTrue(svg.startswith("<svg"))
        with self.assertRaises(Exception):
            render_figs.render_svg({"fn": "x^^", "domain": [0, 1]})

    def test_figure_clip_ids_unique(self):
        # 한 HTML에 여러 그림이 들어가므로 clipPath id가 겹치면 뒤 그림의 곡선이 잘린다
        import re
        a = render_figs.render_svg({"fn": "x^2", "domain": [-2, 2]})
        b = render_figs.render_svg({"fn": "x^3", "domain": [-1, 3], "size": [600, 170]})
        ids = [re.search(r'<clipPath id="([^"]+)"', s).group(1) for s in (a, b)]
        self.assertNotEqual(ids[0], ids[1])
        for s, cid in zip((a, b), ids):
            self.assertNotIn("url(#CLIP)", s)
            self.assertIn(f"url(#{cid})", s)


if __name__ == "__main__":
    unittest.main()
