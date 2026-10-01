"""STEAL THE SIGN : KICE 교재 파이프라인

  python run.py pages --pdf 교재.pdf --id KB1 --title "교재 이름"   교재 PDF → 쪽 이미지·텍스트 (AI 판독용)
  python run.py mock --json 분석.json --id MK1 --title "실모 제1회"  실모 오답 분석 JSON → 판독 뼈대
  python run.py split --book work/book_x.json   책 JSON을 DAY별 폴더로 나누기 (join: 다시 합치기)
  python run.py title --id KB1 --title "교재 이름"                 교재 출처 표기 바꾸기
  python run.py source       교재 판독 검사 + 큐레이션 초안: validate → source → curate → report
  python run.py created      창작 문제은행 검문: validate → created → report
  python run.py              전체: validate → created → source → check → verify → figs → build → layout → pdf → report
  python run.py check        검사만: validate → created → source → check → verify → report
  python run.py build        조판만: figs → build → layout → pdf → report
  python run.py <단계>       validate | curate | check | verify | figs | layout | pdf | report 중 하나

  옵션: --book PATH  --created DIR  --source DIR  --out DIR
        --recheck(창작·교재 전체 재검사)  --force(검사 오류가 있어도 조판)
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from scripts.common import Context, Log, ensure_utf8_stdout

STAGES = {
    "validate": ("validate_sources", "validate_sources"),
    "created": ("check_created", "check_created"),
    "source": ("check_source", "check_source"),
    "curate": ("curate", "curate"),
    "pages": ("pdf_pages", "pdf_pages"),
    "mock": ("mock_import", "mock_import"),
    "title": ("pdf_pages", "pdf_pages"),
    "split": ("book_dir", "book_dir"),
    "join": ("book_dir", "book_dir"),
    "check": ("check_book", "check_book"),
    "verify": ("verify_answers", "verify_answers"),
    "figs": ("render_figs", "render_figs"),
    "build": ("build", "build"),
    "layout": ("check_layout", "check_layout"),
    "pdf": ("export_pdf", "export_pdf"),
    "report": ("report", "report"),
}
PLANS = {
    "all": ["validate", "created", "source", "check", "verify", "figs", "build", "layout", "pdf", "report"],
    "check": ["validate", "created", "source", "check", "verify", "report"],
    "build": ["figs", "build", "layout", "pdf", "report"],
    "created": ["validate", "created", "report"],
    "source": ["validate", "source", "curate", "report"],
    "pages": ["pages"],
    "mock": ["mock"],
    "title": ["title"],
    "split": ["split"],
    "join": ["join"],
}
NEEDS_BOOK = {"check", "verify", "figs", "build"}
GATE = {"validate", "created", "source", "check", "verify"}  # 이 단계에 오류가 있으면 조판하지 않는다


def run_stage(key: str, ctx: Context, args) -> Log:
    module_name, log_name = STAGES[key]
    if key in NEEDS_BOOK and not ctx.book_path.exists():
        log = Log(log_name)
        found = sorted(p.name for p in ctx.book_path.parent.glob("book*") if p.suffix == ".json" or p.is_dir())
        hint = f" — --book으로 고르세요: {', '.join(found)}" if found else ""
        log.error("book.json", f"{ctx.book_path} 가 없습니다. AI가 교재 구성을 먼저 작성해야 합니다{hint}")
        return log
    try:
        module = __import__(f"scripts.{module_name}", fromlist=["run"])
        if key in ("created", "source"):
            return module.run(ctx, recheck=args.recheck)
        if key == "pages":
            return module.run(ctx, pdf=args.pdf, book_id=args.id, title=args.title)
        if key == "mock":
            return module.run(ctx, json_path=args.json, book_id=args.id, title=args.title)
        if key in ("split", "join"):
            return getattr(module, key)(ctx)
        if key == "title":
            return module.set_title(ctx, book_id=args.id, title=args.title)
        return module.run(ctx)
    except Exception as e:  # noqa: BLE001
        log = Log(log_name)
        tb = traceback.extract_tb(e.__traceback__)[-1]
        log.error("예외", f"{type(e).__name__}: {e} ({Path(tb.filename).name}:{tb.lineno})")
        return log


def main(argv=None) -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", default="all", choices=sorted(set(PLANS) | set(STAGES)))
    ap.add_argument("--book")
    ap.add_argument("--created")
    ap.add_argument("--source")
    ap.add_argument("--pdf")
    ap.add_argument("--json", help="mock 단계: 실모 오답 분석 JSON")
    ap.add_argument("--id")
    ap.add_argument("--title", help="교재 출처 표기(사용자가 정한 이름 그대로)")
    ap.add_argument("--out")
    ap.add_argument("--recheck", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    ctx = Context(book_path=args.book, created_dir=args.created, out_dir=args.out, source_dir=args.source)
    plan = PLANS.get(args.target, [args.target])
    failed_gate = False
    any_error = False
    for key in plan:
        if key in ("figs", "build", "layout", "pdf") and failed_gate and not args.force:
            print(f"[--] {key}: 검사 오류가 있어 건너뜀 (--force로 강제)")
            continue
        log = run_stage(key, ctx, args)
        if key != "report":
            log.save(ctx)
        log.print_summary()
        if not log.ok:
            any_error = True
            if key in GATE:
                failed_gate = True
        if key == "validate":
            ctx.__dict__.pop("excluded", None)  # 새 excluded.json 반영
        if key == "created":
            ctx.__dict__.pop("created", None)   # 갱신된 status 반영
        if key == "source":
            ctx.__dict__.pop("source", None)
    if "report" in plan:
        print(f"보고서: {ctx.out_dir / 'report.md'}")
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
