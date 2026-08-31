#!/usr/bin/env python3
"""Bounded radical-membership tests for the binary-decimic HSOP.

For one HSOP invariant eta and one of the two nonzero residual-quadratic
orbits, compute the clean direct equations together with ``inv*eta-1``.
A characteristic-zero unit ideal proves eta lies in the radical on that
orbit.  A finite-field unit is a route signal only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import sympy as sp

from reconstruct_decimic_hsop import HSOP_DEGREES, transvectant
from reconstruct_normal_layers import canonical_lift, q, s, t, x, y, z
from scout_five_support import general_cubic
from singular_process import run_singular_process


f_coefficients = sp.symbols("f0:11")
inverse = sp.Symbol("inv")


def generic_decimic() -> sp.Expr:
    return sp.expand(
        sum(
            f_coefficients[index] * s ** (10 - index) * t**index
            for index in range(11)
        )
    )


def selected_hsop(binary_decimic: sp.Expr, name: str) -> sp.Expr:
    """Build only the covariant dependency chain required by ``name``."""

    f = binary_decimic
    if name == "j2":
        return transvectant(f, f, 10)

    k = transvectant(f, f, 8)
    if name == "j4":
        return transvectant(k, k, 4)

    m = transvectant(f, k, 4)
    if name == "A6":
        return transvectant(m, m, 6)

    q_binary = transvectant(f, f, 6)
    if name == "C6":
        r = transvectant(f, q_binary, 8)
        return transvectant(r, r, 2)

    k_m = transvectant(m, m, 4)
    if name == "j8":
        return transvectant(k, k_m, 4)
    if name == "j9":
        return transvectant(
            transvectant(m, k, 1), sp.expand(k**2), 8
        )

    mm2 = transvectant(m, m, 2)
    if name == "j10":
        return transvectant(mm2, sp.expand(k**2), 8)

    if name == "j14_plus_A14":
        k_q = transvectant(q_binary, q_binary, 6)
        m_q = transvectant(q_binary, k_q, 4)
        j14 = transvectant(transvectant(k_q, k_q, 2), m_q, 4)
        A14 = transvectant(
            sp.expand(transvectant(k, k, 2) ** 2), mm2, 8
        )
        return sp.expand(j14 + A14)
    raise ValueError(name)


def normal_equations(orbit: str) -> tuple[list[sp.Expr], float]:
    started = time.perf_counter()
    f = generic_decimic()
    h5 = canonical_lift(f, 5) + q * general_cubic
    residual = x if orbit == "tangent" else y
    polynomial = sp.Poly(
        sp.expand(sp.hessian(h5, (x, y, z)).det() - q**4 * residual),
        x,
        y,
        z,
    )
    equations = [coefficient for _, coefficient in polynomial.terms()]
    if len(equations) != 55:
        raise AssertionError(f"expected 55 equations, received {len(equations)}")
    return equations, time.perf_counter() - started


def render(expression: sp.Expr) -> str:
    return str(sp.expand(expression)).replace("**", "^")


def digest(expressions: list[sp.Expr] | tuple[sp.Expr, ...]) -> str:
    payload = "\n".join(render(expression) for expression in expressions)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def singular_source(
    equations: list[sp.Expr], invariant: sp.Expr, characteristic: int
) -> str:
    cubic_symbols = tuple(
        sorted(general_cubic.free_symbols, key=lambda symbol: str(symbol))
    )
    variables = f_coefficients + cubic_symbols + (inverse,)
    variable_source = ",".join(map(str, variables))
    if characteristic == 0:
        header = ['LIB "modstd.lib";', f"ring r=0,({variable_source}),dp;"]
        basis_command = "ideal J=modStd(I);"
    else:
        header = [f"ring r={characteristic},({variable_source}),dp;"]
        basis_command = "ideal J=std(I);"
    equation_source = ",".join(render(equation) for equation in equations)
    localization = render(inverse * invariant - 1)
    return "\n".join(
        header
        + [
            "option(redSB);",
            "ideal I=" + equation_source + "," + localization + ";",
            basis_command,
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            "exit;",
        ]
    )


def marker(output: str, name: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(name)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def run_source(source: str, timeout: int) -> dict[str, object]:
    raw = run_singular_process(source, timeout)
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    diagnostic_error = (
        "error occurred" in stdout
        or "error occurred" in stderr
        or "expected ideal-expression" in stdout
        or "expected ideal-expression" in stderr
    )
    remainder = marker(stdout, "UNIT_REMAINDER")
    return {
        **raw,
        "diagnostic_error": diagnostic_error,
        "unit_remainder": remainder,
        "basis_size": marker(stdout, "BASIS_SIZE"),
        "is_unit": (
            not raw["timed_out"]
            and raw["return_code"] == 0
            and not diagnostic_error
            and remainder == "0"
        ),
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--invariant", choices=tuple(HSOP_DEGREES), required=True)
    parser.add_argument("--orbit", choices=("tangent", "secant"), required=True)
    parser.add_argument("--characteristic", type=int, default=32003)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be zero or a positive prime")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")
    if shutil.which("Singular") is None:
        raise SystemExit("Singular is required")

    started = time.perf_counter()
    equations, equation_build_seconds = normal_equations(arguments.orbit)
    invariant_started = time.perf_counter()
    invariant = selected_hsop(generic_decimic(), arguments.invariant)
    invariant_build_seconds = time.perf_counter() - invariant_started
    source = singular_source(equations, invariant, arguments.characteristic)
    calculation = run_source(source, arguments.timeout)
    if arguments.characteristic == 0 and calculation["is_unit"]:
        disposition = "EXACT_RADICAL_MEMBERSHIP_ON_ORBIT"
    elif arguments.characteristic > 0 and calculation["is_unit"]:
        disposition = "BOUNDED_MODULAR_UNIT_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"
    result = {
        "schema": "hc4-decimic-nullcone-hsop-radical-scout-v1",
        "invariant": arguments.invariant,
        "invariant_degree": HSOP_DEGREES[arguments.invariant],
        "orbit": arguments.orbit,
        "characteristic": arguments.characteristic,
        "equation_count": len(equations),
        "equation_build_seconds": equation_build_seconds,
        "equation_stream_sha256": digest(tuple(equations)),
        "invariant_build_seconds": invariant_build_seconds,
        "invariant_term_count": len(sp.Poly(invariant, *f_coefficients).terms()),
        "invariant_sha256": digest((invariant,)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "claim_boundary": (
            "finite-characteristic units are route signals only; all eight "
            "invariants on both residual orbits need characteristic-zero "
            "unit certificates for HSOP nullcone containment"
        ),
        "wall_seconds": time.perf_counter() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
