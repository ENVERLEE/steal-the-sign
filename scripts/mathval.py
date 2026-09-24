"""정답 값 비교: LaTeX 정답 → sympy, verify 코드 실행(별도 프로세스, 시간 제한)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import sympy
from sympy.parsing.sympy_parser import (implicit_multiplication_application, parse_expr,
                                        standard_transformations)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)
_CMDS_SKIP = ("\\left", "\\right", "\\displaystyle", "\\,", "\\;", "\\!", "\\ ")


class TexError(ValueError):
    pass


def _tex_convert(s: str) -> str:
    out, i, n = [], 0, len(s)

    def match_group(j: int) -> int:
        depth = 0
        for k in range(j, n):
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
                if depth == 0:
                    return k
        raise TexError(f"중괄호 짝이 맞지 않음: {s}")

    def arg(j: int) -> tuple[str, int]:
        while j < n and s[j] == " ":
            j += 1
        if j >= n:
            raise TexError(f"인자 없음: {s}")
        if s[j] == "{":
            k = match_group(j)
            return _tex_convert(s[j + 1:k]), k + 1
        if s[j] == "\\":
            k = j + 1
            while k < n and s[k].isalpha():
                k += 1
            return _tex_convert(s[j:k]), k
        return s[j], j + 1

    while i < n:
        c = s[i]
        skip = next((cmd for cmd in _CMDS_SKIP if s.startswith(cmd, i)), None)
        if skip:
            i += len(skip)
            continue
        if s.startswith(("\\frac", "\\dfrac", "\\tfrac"), i):
            i += 5 if s.startswith("\\frac", i) else 6
            a, i = arg(i)
            b, i = arg(i)
            out.append(f"(({a})/({b}))")
        elif s.startswith("\\sqrt", i):
            i += 5
            idx = None
            if i < n and s[i] == "[":
                k = s.index("]", i)
                idx, i = _tex_convert(s[i + 1:k]), k + 1
            a, i = arg(i)
            out.append(f"root(({a}),({idx}))" if idx else f"sqrt({a})")
        elif s.startswith("\\log", i) or s.startswith("\\ln", i):
            is_ln = s.startswith("\\ln", i)
            i += 3 if is_ln else 4
            base = None
            if not is_ln and i < n and s[i] == "_":
                base, i = arg(i + 1)
            a, i = arg(i)
            out.append(f"log(({a}),({base}))" if base else f"log({a})")
        elif s.startswith("\\pi", i):
            out.append("pi")
            i += 3
        elif s.startswith(("\\times", "\\cdot"), i):
            out.append("*")
            i += 6 if s.startswith("\\times", i) else 5
        elif c == "^":
            a, i = arg(i + 1)
            out.append(f"**({a})")
        elif c == "{":
            k = match_group(i)
            out.append(f"({_tex_convert(s[i + 1:k])})")
            i = k + 1
        elif c == "\\":
            raise TexError(f"지원하지 않는 명령: {s[i:i + 12]}")
        elif c == " ":
            i += 1
        elif c.isdigit() or c == ".":
            k = i
            while k < n and (s[k].isdigit() or s[k] == "."):
                k += 1
            out.append(s[i:k])
            i = k
        else:
            out.append(c)
            i += 1
    return " ".join(out)


def tex_to_sympy(tex: str):
    """LaTeX 정답 표기(\\frac97\\pi, 2^{\\frac94}, \\log_2 3 등)를 sympy 식으로"""
    text = str(tex).strip().strip("$")
    try:
        return parse_expr(_tex_convert(text), transformations=_TRANSFORMS, evaluate=True)
    except TexError:
        raise
    except Exception as e:  # noqa: BLE001
        raise TexError(f"해석 실패 '{tex}': {e}") from e


def to_value(x):
    """verify 결과·정답 문자열 → sympy"""
    if isinstance(x, (int, float)):
        return sympy.nsimplify(x) if isinstance(x, float) else sympy.Integer(x)
    s = str(x).strip()
    try:
        return sympy.sympify(s)
    except Exception:  # noqa: BLE001
        return tex_to_sympy(s)


def _is_text_answer(x) -> bool:
    """ㄱ, ㄴ, ㄷ 같은 보기 조합 정답"""
    return any("\uac00" <= ch <= "\ud7a3" or "\u3131" <= ch <= "\u318e" for ch in str(x))


def _norm_text(x) -> str:
    return ",".join(sorted(t.strip() for t in str(x).replace("，", ",").split(",") if t.strip()))


def same_value(a, b, tol: float = 1e-9) -> bool:
    if _is_text_answer(a) or _is_text_answer(b):
        return _norm_text(a) == _norm_text(b)
    try:
        va, vb = to_value(a), to_value(b)
        d = sympy.simplify(va - vb)
        if d == 0:
            return True
        return abs(complex(sympy.N(d, 30))) < tol
    except Exception:  # noqa: BLE001
        return str(a).strip() == str(b).strip()


# ---------------------------------------------------------------- verify 실행

RUNNER = Path(__file__).with_name("verify_runner.py")


def run_verify(code: str, funcs: list[str], timeout: float) -> dict:
    """verify 코드를 별도 파이썬 프로세스에서 실행해 함수별 결과(문자열)를 받는다.

    반환: {"results": {이름: 값 또는 [값...]}, "errors": {이름: 메시지}}
    """
    payload = json.dumps({"code": code, "funcs": funcs}, ensure_ascii=False)
    try:
        proc = subprocess.run([sys.executable, str(RUNNER)], input=payload.encode("utf-8"),
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"results": {}, "errors": {"*": f"시간 초과 {timeout}초"}}
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        return {"results": {}, "errors": {"*": err[-1] if err else f"종료 코드 {proc.returncode}"}}
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return {"results": {}, "errors": {"*": "verify가 결과 외의 출력을 냈습니다(print 금지)"}}
