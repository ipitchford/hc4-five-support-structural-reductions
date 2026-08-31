#!/usr/bin/env python3
"""Reconstruct and audit the Brouwer-Popoviciu binary-decimic HSOP.

The implementation starts from the paper's transvectant definitions rather
than expanded coefficient polynomials.  It provides a checked frontend for the
campaign's optional invariant-nullcone computation; it does not test ideal
membership by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp


s, t = sp.symbols("s t")

HSOP_DEGREES = {
    "j2": 2,
    "j4": 4,
    "A6": 6,
    "C6": 6,
    "j8": 8,
    "j9": 9,
    "j10": 10,
    "j14_plus_A14": 14,
}


def transvectant(first: sp.Expr, second: sp.Expr, order: int) -> sp.Expr:
    """Return the unnormalised order-``order`` binary transvectant."""

    return sp.expand(
        sum(
            (-1) ** index
            * sp.binomial(order, index)
            * sp.diff(first, s, order - index, t, index)
            * sp.diff(second, s, index, t, order - index)
            for index in range(order + 1)
        )
    )


def covariants(binary_decimic: sp.Expr) -> dict[str, sp.Expr]:
    f = sp.expand(binary_decimic)
    k = transvectant(f, f, 8)
    m = transvectant(f, k, 4)
    q = transvectant(f, f, 6)
    r = transvectant(f, q, 8)
    k_q = transvectant(q, q, 6)
    k_m = transvectant(m, m, 4)
    m_q = transvectant(q, k_q, 4)
    return {
        "f": f,
        "k": k,
        "m": m,
        "q": q,
        "r": r,
        "k_q": k_q,
        "k_m": k_m,
        "m_q": m_q,
    }


def hsop(binary_decimic: sp.Expr) -> dict[str, sp.Expr]:
    values = covariants(binary_decimic)
    f = values["f"]
    k = values["k"]
    m = values["m"]
    q = values["q"]
    r = values["r"]
    k_q = values["k_q"]
    k_m = values["k_m"]
    m_q = values["m_q"]

    kk2 = transvectant(k, k, 2)
    mm2 = transvectant(m, m, 2)
    j14 = transvectant(transvectant(k_q, k_q, 2), m_q, 4)
    A14 = transvectant(sp.expand(kk2**2), mm2, 8)
    result = {
        "j2": transvectant(f, f, 10),
        "j4": transvectant(k, k, 4),
        "A6": transvectant(m, m, 6),
        "C6": transvectant(r, r, 2),
        "j8": transvectant(k, k_m, 4),
        "j9": transvectant(
            transvectant(m, k, 1), sp.expand(k**2), 8
        ),
        "j10": transvectant(mm2, sp.expand(k**2), 8),
        "j14_plus_A14": sp.expand(j14 + A14),
    }
    for name, value in result.items():
        if sp.Poly(value, s, t).total_degree() != 0:
            raise AssertionError(f"{name} is not an invariant")
    return result


def transform(binary_form: sp.Expr, matrix: tuple[int, int, int, int]) -> sp.Expr:
    a, b, c, d = matrix
    if a * d - b * c != 1:
        raise ValueError("matrix must lie in SL_2(Z)")
    return sp.expand(binary_form.subs({s: a * s + b * t, t: c * s + d * t}, simultaneous=True))


def scalar(value: sp.Expr) -> int:
    simplified = sp.expand(value)
    if simplified.free_symbols:
        raise AssertionError(f"expected scalar, received {simplified}")
    return int(simplified)


def digest_values(values: dict[str, int]) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def run_audit() -> dict[str, object]:
    base = (
        s**10
        + 2 * s**9 * t
        - 3 * s**7 * t**3
        + 5 * s**5 * t**5
        - 2 * s**2 * t**8
        + 7 * t**10
    )
    matrices = (
        (1, 1, 0, 1),
        (1, 0, 1, 1),
        (0, -1, 1, 0),
    )
    base_values = {name: scalar(value) for name, value in hsop(base).items()}
    covariance_rows = []
    for matrix in matrices:
        transformed_values = {
            name: scalar(value)
            for name, value in hsop(transform(base, matrix)).items()
        }
        covariance_rows.append(
            {
                "matrix": list(matrix),
                "equal_to_base": transformed_values == base_values,
                "values_sha256": digest_values(transformed_values),
            }
        )

    nullform = sp.expand(s**6 * (s + t) ** 4)
    null_values = {
        name: scalar(value) for name, value in hsop(nullform).items()
    }
    nonnull_values = base_values
    checks = {
        "eight_parameters": tuple(HSOP_DEGREES) == tuple(base_values),
        "three_exact_sl2_transforms": all(
            row["equal_to_base"] for row in covariance_rows
        ),
        "multiplicity_six_nullform_vanishes": all(
            value == 0 for value in null_values.values()
        ),
        "nonnull_control_detected": any(
            value != 0 for value in nonnull_values.values()
        ),
    }
    return {
        "schema": "hc4-binary-decimic-hsop-reconstruction-v1",
        "source": {
            "citation": "Brouwer-Popoviciu, The invariants of the binary decimic",
            "arxiv": "1002.1008",
            "doi": "10.1016/j.jsc.2010.03.002",
        },
        "normalization": "unnormalised transvectants; vanishing locus unchanged",
        "degrees": HSOP_DEGREES,
        "base_values_sha256": digest_values(base_values),
        "covariance_rows": covariance_rows,
        "nullform_values": null_values,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "claim_boundary": (
            "reconstructs and audits the invariant frontend only; no clean "
            "ideal membership or nullcone containment is inferred"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    result = run_audit()
    result["wall_seconds"] = time.perf_counter() - started
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
