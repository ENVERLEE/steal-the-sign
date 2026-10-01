"""책 JSON을 DAY 단위 폴더로 나누거나 합친다.

  python run.py split --book work/book_mock.json   → work/book_mock/meta.json + day01.json …
  python run.py join  --book work/book_mock        → work/book_mock.json (합친 한 파일)

`--book`에는 한 파일 또는 폴더를 모두 줄 수 있다. 폴더는 meta.json(days 제외 최상위 키)과
day{NN}.json(DAY 하나, NN = day 번호)으로 이루어지며, 읽을 때 한 책으로 합쳐진다.
AI는 고칠 DAY 파일만 열면 된다.
"""
from __future__ import annotations

from pathlib import Path

from scripts.common import Context, Log, read_json, write_json


def day_name(day: dict, index: int) -> str:
    return f"day{int(day.get('day') or index + 1):02d}.json"


def split(ctx: Context) -> Log:
    log = Log("book_dir")
    src = ctx.book_path
    if src.is_dir():
        log.error(str(src), "이미 폴더입니다")
        return log
    book = read_json(src)
    dst = src.with_suffix("")
    if dst.exists():
        log.error(str(dst), "폴더가 이미 있습니다. 지우고 다시 하세요")
        return log
    write_json(dst / "meta.json", {k: v for k, v in book.items() if k != "days"})
    for i, d in enumerate(book.get("days") or []):
        write_json(dst / day_name(d, i), d)
    log.stats.update({"days": len(book.get("days") or []), "folder": str(dst)})
    print(f"{src.name} → {dst}/ (meta.json + DAY {len(book.get('days') or [])}개). 확인 후 {src.name}은 지우세요")
    return log


def join(ctx: Context) -> Log:
    log = Log("book_dir")
    src = ctx.book_path
    if not src.is_dir():
        log.error(str(src), "폴더가 아닙니다")
        return log
    dst = src.with_suffix(".json")
    write_json(dst, load_dir(src))
    print(f"{src.name}/ → {dst}")
    return log


def load_dir(path: Path) -> dict:
    meta = path / "meta.json"
    if not meta.exists():
        raise FileNotFoundError(f"{meta} 가 없습니다")
    book = read_json(meta)
    days = [read_json(f) for f in sorted(path.glob("day*.json"))]
    book["days"] = days
    return book
