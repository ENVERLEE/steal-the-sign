"""schema/*.schema.json 검증"""
from __future__ import annotations

from functools import lru_cache

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from scripts.common import ROOT, read_json

SCHEMA_DIR = ROOT / "schema"


@lru_cache(maxsize=None)
def _registry() -> Registry:
    reg = Registry()
    for f in SCHEMA_DIR.glob("*.schema.json"):
        reg = reg.with_resource(f.name, Resource.from_contents(read_json(f)))
    return reg


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(read_json(SCHEMA_DIR / f"{name}.schema.json"), registry=_registry())


def validate(name: str, data) -> list[str]:
    """스키마 위반 목록: ['days/0/practice/2/ref: ... 형식 아님', ...]"""
    out = []
    for e in sorted(_validator(name).iter_errors(data), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in e.absolute_path) or "(최상위)"
        out.append(f"{where}: {e.message}")
    return out
