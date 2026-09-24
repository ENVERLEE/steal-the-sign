"""verify 코드 실행기 (mathval.run_verify가 별도 프로세스로 부른다).

stdin: {"code": "...", "funcs": ["skill", "standard", "unique"]}
stdout: {"results": {...}, "errors": {...}}
verify 코드에서는 sympy(별칭 sp와 모든 이름), numpy(np), math, itertools, Fraction을 바로 쓸 수 있다.
"""
import contextlib
import io
import itertools
import json
import math
import sys
from fractions import Fraction


def _fmt(v):
    import sympy
    if isinstance(v, (list, tuple, set, frozenset)):
        return [_fmt(x) for x in v]
    if isinstance(v, Fraction):
        v = sympy.Rational(v.numerator, v.denominator)
    try:
        return sympy.sstr(sympy.nsimplify(v) if isinstance(v, float) else sympy.sympify(v))
    except Exception:  # noqa: BLE001
        return str(v)


def main():
    for s in (sys.stdout, sys.stdin):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    req = json.loads(sys.stdin.read())
    import numpy as np
    import sympy as sp
    ns = {"sp": sp, "np": np, "math": math, "itertools": itertools, "Fraction": Fraction}
    exec("from sympy import *", ns)  # noqa: S102
    out = {"results": {}, "errors": {}}
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink):
            exec(compile(req["code"], "<verify>", "exec"), ns)  # noqa: S102
    except Exception as e:  # noqa: BLE001
        out["errors"]["*"] = f"{type(e).__name__}: {e}"
        print(json.dumps(out, ensure_ascii=False))
        return
    for name in req["funcs"]:
        fn = ns.get(name)
        if not callable(fn):
            out["errors"][name] = "함수가 정의되지 않음"
            continue
        try:
            with contextlib.redirect_stdout(sink):
                out["results"][name] = _fmt(fn())
        except Exception as e:  # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
