#!/usr/bin/env python3
"""Exhaustive continued-fraction classifier from Amendment 01 Section 7."""

from __future__ import annotations

import math
from dataclasses import dataclass


NO_CANDIDATE = 0
UNIQUE_ZERO = 1
UNIQUE_NONZERO = 2
AMBIGUOUS = 3


@dataclass(frozen=True)
class Classification:
    label: int
    candidates: tuple[tuple[int, int], ...]
    euclidean_divisions: int
    convergents_tested: int


def classify(residue: int, modulus: int) -> Classification:
    residue = int(residue)
    modulus = int(modulus)
    if modulus < 2 or not 0 <= residue < modulus:
        raise ValueError("require modulus >=2 and residue in canonical range")
    if residue == 0:
        return Classification(UNIQUE_ZERO, ((0, 1),), 0, 1)

    # Canonical Euclidean quotients for residue/modulus.
    numerator, denominator = residue, modulus
    quotients: list[int] = []
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        quotients.append(quotient)
        numerator, denominator = denominator, remainder

    k_minus_2, k_minus_1 = 0, 1
    d_minus_2, d_minus_1 = 1, 0
    candidates: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    tested = 0
    for quotient in quotients:
        k = quotient * k_minus_1 + k_minus_2
        d = quotient * d_minus_1 + d_minus_2
        tested += 1
        n = residue * d - modulus * k
        candidate = (n, d)
        if (
            d > 0
            and (residue * d - n) % modulus == 0
            and 2 * abs(n) * d < modulus
            and math.gcd(abs(n), d) == 1
            and candidate not in seen
        ):
            candidates.append(candidate)
            seen.add(candidate)
        k_minus_2, k_minus_1 = k_minus_1, k
        d_minus_2, d_minus_1 = d_minus_1, d

    frozen = tuple(candidates)
    if not frozen:
        label = NO_CANDIDATE
    elif len(frozen) > 1:
        label = AMBIGUOUS
    elif frozen[0][0] == 0:
        label = UNIQUE_ZERO
    else:
        label = UNIQUE_NONZERO
    return Classification(label, frozen, len(quotients), tested)


def brute_force_candidates(residue: int, modulus: int) -> tuple[tuple[int, int], ...]:
    """Finite oracle used only by the preregistered small-modulus regression."""

    if modulus < 2 or not 0 <= residue < modulus:
        raise ValueError("invalid brute-force domain")
    if residue == 0:
        return ((0, 1),)
    result: set[tuple[int, int]] = set()
    for d in range(1, (modulus - 1) // 2 + 1):
        centered = (residue * d) % modulus
        for n in (centered, centered - modulus):
            if (
                2 * abs(n) * d < modulus
                and math.gcd(abs(n), d) == 1
                and (residue * d - n) % modulus == 0
            ):
                result.add((n, d))
    # Match convergent order by sorting on denominator, then approximation data.
    return tuple(sorted(result, key=lambda item: (item[1], abs(item[0]), item[0])))


def regression(maximum_modulus: int = 512) -> dict[str, int]:
    if maximum_modulus < 2:
        raise ValueError("maximum modulus is too small")
    residue_cases = 0
    candidate_pairs = 0
    for modulus in range(2, maximum_modulus + 1):
        for residue in range(modulus):
            observed = classify(residue, modulus)
            expected = brute_force_candidates(residue, modulus)
            if set(observed.candidates) != set(expected):
                raise AssertionError(
                    f"RR mismatch at modulus={modulus}, residue={residue}: "
                    f"continued={observed.candidates}, brute={expected}"
                )
            residue_cases += 1
            candidate_pairs += len(expected)
    return {
        "maximum_modulus": maximum_modulus,
        "residue_cases": residue_cases,
        "candidate_pairs": candidate_pairs,
    }


if __name__ == "__main__":
    print(regression())
