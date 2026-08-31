#!/usr/bin/env python3
"""One-shot Dixon lift and exact reconstruction of the residual-114 chart."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 2_053
COLUMNS = 114
ENTRIES = ROWS * COLUMNS
DIGITS = 72
SOURCE = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
SOURCE_SHA256 = "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74"
AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit.json"
AUDIT_SHA256 = "7eba0e65e40abd7eea0065ecd84c3803237fa9cc5c51391f3202b4d300b7185a"
PREREGISTRATION = CAMPAIGN / "research/THIRD_COLON_RESIDUAL_114_P181_72DIGIT_EXACT_CHART_PREREGISTRATION.md"
PREREGISTRATION_SHA256 = "450d6f88c5fb6198c14212e2d71a6f67784cddba711b421be8de676b70e7945e"
AMENDMENT = CAMPAIGN / "research/THIRD_COLON_RESIDUAL_114_P181_72DIGIT_EXACT_CHART_PREREGISTRATION_AMENDMENT_01.md"
REPLAY_PRIMES = (181, 173, 197, 2_147_483_647, 2_147_483_629)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_sparse_rows(payload: list[list[list[object]]], column_count: int) -> list[tuple[tuple[int, int], ...]]:
    rows = []
    for encoded in payload:
        row = tuple((int(column), int(value)) for column, value in encoded)
        require(tuple(sorted(row)) == row, "sparse row ordering drift")
        require(len({column for column, _value in row}) == len(row), "duplicate sparse column")
        require(all(0 <= column < column_count and value for column, value in row), "malformed sparse row")
        rows.append(row)
    return rows


def dense_c(c_rows: list[tuple[tuple[int, int], ...]]) -> list[list[int]]:
    matrix = [[0] * COLUMNS for _ in range(ROWS)]
    for row_index, row in enumerate(c_rows):
        for column, value in row:
            matrix[row_index][column] = value
    return matrix


def multiply_sparse_dense(b_rows: list[tuple[tuple[int, int], ...]], matrix: list[list[int]]) -> list[list[int]]:
    product = []
    for row in b_rows:
        total = [0] * COLUMNS
        for coordinate, coefficient in row:
            vector = matrix[coordinate]
            total = [left + coefficient * right for left, right in zip(total, vector)]
        product.append(total)
    return product


def factor_mod_p(b_rows: list[tuple[tuple[int, int], ...]]) -> tuple[list[dict[int, int]], list[tuple[tuple[tuple[int, int], ...], int, int]]]:
    basis: dict[int, dict[int, int]] = {}
    plan = []
    for row_index, integer_row in enumerate(b_rows):
        work = {column: value % P for column, value in integer_row if value % P}
        reductions = []
        while work:
            pivot = min(work)
            if pivot not in basis:
                break
            factor = work[pivot]
            reductions.append((pivot, factor))
            for column, value in basis[pivot].items():
                updated = (work.get(column, 0) - factor * value) % P
                if updated:
                    work[column] = updated
                else:
                    work.pop(column, None)
        require(bool(work), f"B singular modulo 181 at row {row_index}")
        pivot = min(work)
        inverse = pow(work[pivot], -1, P)
        normalized = {column: value * inverse % P for column, value in work.items()}
        require(normalized[pivot] == 1 and pivot not in basis, "factorization pivot drift")
        basis[pivot] = normalized
        plan.append((tuple(reductions), pivot, inverse))
    require(set(basis) == set(range(ROWS)), "B factorization rank drift")
    return [basis[index] for index in range(ROWS)], plan


def solve_factored(
    basis_b: list[dict[int, int]],
    plan: list[tuple[tuple[tuple[int, int], ...], int, int]],
    rhs: list[list[int]],
) -> list[list[int]]:
    basis_rhs: list[list[int] | None] = [None] * ROWS
    for row_index, (reductions, pivot, inverse) in enumerate(plan):
        work = [value % P for value in rhs[row_index]]
        for earlier_pivot, factor in reductions:
            earlier = basis_rhs[earlier_pivot]
            require(earlier is not None, "forward substitution order drift")
            work = [(left - factor * right) % P for left, right in zip(work, earlier)]
        if inverse != 1:
            work = [value * inverse % P for value in work]
        basis_rhs[pivot] = work
    solution: list[list[int] | None] = [None] * ROWS
    for pivot in range(ROWS - 1, -1, -1):
        stored = basis_rhs[pivot]
        require(stored is not None, "missing factored RHS row")
        result = list(stored)
        for later, coefficient in basis_b[pivot].items():
            if later == pivot:
                continue
            require(later > pivot and solution[later] is not None, "back substitution order drift")
            result = [(left - coefficient * right) % P for left, right in zip(result, solution[later])]
        solution[pivot] = result
    require(all(row is not None for row in solution), "incomplete modular solution")
    return [row for row in solution if row is not None]


def flatten_u8(matrix: list[list[int]]) -> bytes:
    require(len(matrix) == ROWS and all(len(row) == COLUMNS for row in matrix), "matrix dimension drift")
    require(all(0 <= value < P for row in matrix for value in row), "matrix entry outside GF(181)")
    return bytes(value for row in matrix for value in row)


def equal_height_reconstruction(residue: int, modulus: int) -> tuple[int, int] | None:
    """Unique rational reconstruction in the symmetric sqrt(M/2) box."""
    residue %= modulus
    if residue == 0:
        return (0, 1)
    bound = math.isqrt((modulus - 1) // 2)
    old_r, r = modulus, residue
    old_t, t = 0, 1
    while abs(r) > bound:
        quotient = old_r // r
        old_r, r = r, old_r - quotient * r
        old_t, t = t, old_t - quotient * t
    numerator, denominator = r, t
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if (
        denominator <= 0
        or abs(numerator) > bound
        or denominator > bound
        or math.gcd(abs(numerator), denominator) != 1
        or math.gcd(denominator, P) != 1
        or (residue * denominator - numerator) % modulus
    ):
        return None
    return numerator, denominator


def exact_chart(
    pairs: list[tuple[int, int]],
    b_rows: list[tuple[tuple[int, int], ...]],
    c_matrix: list[list[int]],
    source: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], bool]:
    denominators = [denominator for _numerator, denominator in pairs]
    global_denominator = math.lcm(*denominators)
    numerators = [numerator * (global_denominator // denominator) for numerator, denominator in pairs]
    content = 0
    for value in numerators:
        content = math.gcd(content, abs(value))
    require(global_denominator > 0 and math.gcd(global_denominator, content) == 1, "global primitive normalization failed")
    numerator_matrix = [numerators[start:start + COLUMNS] for start in range(0, ENTRIES, COLUMNS)]
    product = multiply_sparse_dense(b_rows, numerator_matrix)
    mismatches = 0
    residual_hash = hashlib.sha256()
    for row in range(ROWS):
        for column in range(COLUMNS):
            residual = product[row][column] - global_denominator * c_matrix[row][column]
            mismatches += int(residual != 0)
            residual_hash.update(f"{residual}\n".encode("ascii"))
    reductions = {}
    all_reductions_pass = mismatches == 0
    if mismatches == 0:
        for prime in REPLAY_PRIMES:
            denominator_is_unit = global_denominator % prime != 0
            if denominator_is_unit:
                inverse = pow(global_denominator % prime, -1, prime)
                reduced = [[value % prime * inverse % prime for value in row] for row in numerator_matrix]
                expected = source["prime_records"][str(prime)]["transition_matrix_row_major"]
                mismatch_count = sum(left != right for left_row, right_row in zip(reduced, expected) for left, right in zip(left_row, right_row))
                reduced_hash = canonical_hash(reduced)
            else:
                mismatch_count = ENTRIES
                reduced_hash = None
            reductions[str(prime)] = {
                "denominator_is_unit": denominator_is_unit,
                "mismatch_count": mismatch_count,
                "transition_matrix_row_major_sha256": reduced_hash,
            }
            all_reductions_pass = all_reductions_pass and denominator_is_unit and mismatch_count == 0
    chart = {
        "schema": "hc4.third-colon-residual-114-p181-72digit-rational-chart.v1",
        "global_denominator": str(global_denominator),
        "global_denominator_bit_length": global_denominator.bit_length(),
        "primitive_content": str(content),
        "rational_pairs_row_major": [[str(numerator), str(denominator)] for numerator, denominator in pairs],
        "integer_numerator_matrix_row_major": [[str(value) for value in row] for row in numerator_matrix],
    }
    replay = {
        "exact_scalar_mismatches": mismatches,
        "exact_residual_stream_sha256": residual_hash.hexdigest(),
        "five_fibre_reductions": reductions,
        "rational_pair_stream_sha256": canonical_hash(chart["rational_pairs_row_major"]),
        "integer_numerator_matrix_sha256": canonical_hash(chart["integer_numerator_matrix_row_major"]),
    }
    return chart, replay, all_reductions_pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    require(file_hash(SOURCE) == SOURCE_SHA256, "source chart hash drift")
    require(file_hash(AUDIT) == AUDIT_SHA256, "independent source audit hash drift")
    require(file_hash(PREREGISTRATION) == PREREGISTRATION_SHA256, "preregistration hash drift")
    amendment_hash = file_hash(AMENDMENT)
    fixture_modulus = P**10
    fixtures = ((0, 1), (37, 1), (-91, 1), (4_115, 2_263))
    for numerator, denominator in fixtures:
        residue = numerator * pow(denominator, -1, fixture_modulus) % fixture_modulus
        require(equal_height_reconstruction(residue, fixture_modulus) == (numerator, denominator), "equal-height reconstruction fixture failed")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    require(source.get("status") == "PASS_FIVE_FIBRE_COMMON_RESIDUAL_114_QUOTIENT_CHART", "source status drift")
    require(audit.get("status") == "PASS_INDEPENDENT_RESIDUAL_114_QUOTIENT_AND_M70_REPLAY", "audit status drift")
    b_rows = parse_sparse_rows(source["B_sparse_integer_rows"], ROWS)
    c_rows = parse_sparse_rows(source["C_sparse_integer_rows"], COLUMNS)
    require(len(b_rows) == len(c_rows) == ROWS, "integer chart row count drift")
    require(sum(map(len, b_rows)) == 9_711 and sum(map(len, c_rows)) == 143, "integer chart support drift")
    c_matrix = dense_c(c_rows)
    transition = [[int(value) for value in row] for row in source["prime_records"]["181"]["transition_matrix_row_major"]]
    require(flatten_u8(transition) == flatten_u8([[value % P for value in row] for row in transition]), "initial transition range drift")
    require(canonical_hash(transition) == "5aea98233b15d428dfc2b3614bb145403ed47c434d1fc6c4925ed30d47bfff57", "initial transition hash drift")
    basis_b, plan = factor_mod_p(b_rows)
    factor_record = {
        "basis_nonzeros": sum(len(row) for row in basis_b),
        "reduction_count": sum(len(reductions) for reductions, _pivot, _inverse in plan),
        "plan_sha256": canonical_hash([[[list(item) for item in reductions], pivot, inverse] for reductions, pivot, inverse in plan]),
    }

    modulus = P
    product = multiply_sparse_dense(b_rows, transition)
    quotient = []
    starting_mismatches = 0
    for row in range(ROWS):
        quotient_row = []
        for column in range(COLUMNS):
            residual = c_matrix[row][column] - product[row][column]
            starting_mismatches += int(residual % modulus != 0)
            quotient_row.append(residual // modulus)
        quotient.append(quotient_row)
    require(starting_mismatches == 0, "initial p181 divisibility failed")

    correction_records = []
    for digit_index in range(1, DIGITS):
        digit_started = time.perf_counter()
        rhs_matrix = [[value % P for value in row] for row in quotient]
        rhs_path = output / f"correction_rhs_digit_{digit_index:02d}.u8"
        digit_path = output / f"digit_{digit_index:02d}.u8"
        rhs_payload = flatten_u8(rhs_matrix)
        rhs_path.write_bytes(rhs_payload)
        digit = solve_factored(basis_b, plan, rhs_matrix)
        digit_payload = flatten_u8(digit)
        digit_path.write_bytes(digit_payload)
        digit_product = multiply_sparse_dense(b_rows, digit)
        next_quotient = []
        divisibility_mismatches = 0
        modular_mismatches = 0
        for row in range(ROWS):
            next_row = []
            for column in range(COLUMNS):
                modular_mismatches += int((digit_product[row][column] - rhs_matrix[row][column]) % P != 0)
                numerator = quotient[row][column] - digit_product[row][column]
                divisibility_mismatches += int(numerator % P != 0)
                next_row.append(numerator // P)
            next_quotient.append(next_row)
        require(modular_mismatches == 0 and divisibility_mismatches == 0, f"correction replay failed at digit {digit_index}")
        transition = [
            [left + modulus * right for left, right in zip(left_row, right_row)]
            for left_row, right_row in zip(transition, digit)
        ]
        modulus *= P
        quotient = next_quotient
        correction_records.append({
            "digit_index": digit_index,
            "cumulative_digits": digit_index + 1,
            "rhs_sha256": hashlib.sha256(rhs_payload).hexdigest(),
            "digit_sha256": hashlib.sha256(digit_payload).hexdigest(),
            "modular_mismatches": modular_mismatches,
            "divisibility_mismatches": divisibility_mismatches,
            "wall_seconds": time.perf_counter() - digit_started,
        })

    require(modulus == P**DIGITS, "terminal modulus drift")
    transition_path = output / "T_mod_181_power_72.json"
    transition_path.write_text(json.dumps([[str(value) for value in row] for row in transition], separators=(",", ":")) + "\n", encoding="ascii")
    terminal_product = multiply_sparse_dense(b_rows, transition)
    terminal_mismatches = 0
    for row in range(ROWS):
        for column in range(COLUMNS):
            terminal_mismatches += int(c_matrix[row][column] - terminal_product[row][column] != modulus * quotient[row][column])
    require(terminal_mismatches == 0, "terminal exact invariant failed")

    outcomes = {"unique_zero": 0, "unique_nonzero": 0, "no_candidate": 0}
    pairs = []
    candidate_count_hash = hashlib.sha256()
    outcome_hash = hashlib.sha256()
    maximum_numerator_bits = 0
    maximum_denominator_bits = 0
    for row in transition:
        for residue in row:
            candidate = equal_height_reconstruction(residue, modulus)
            candidate_count_hash.update((b"0\n" if candidate is None else b"1\n"))
            if candidate is None:
                outcome = "no_candidate"
            elif candidate[0] == 0:
                outcome = "unique_zero"
            else:
                outcome = "unique_nonzero"
            outcomes[outcome] += 1
            outcome_hash.update(f"{outcome}\n".encode("ascii"))
            if candidate is not None:
                pairs.append(candidate)
                maximum_numerator_bits = max(maximum_numerator_bits, abs(candidate[0]).bit_length())
                maximum_denominator_bits = max(maximum_denominator_bits, candidate[1].bit_length())
            else:
                pairs.append((0, 0))
    unresolved = outcomes["no_candidate"]
    chart_output = None
    exact_replay = None
    if unresolved == 0:
        chart, exact_replay, exact_pass = exact_chart(pairs, b_rows, c_matrix, source)
        chart_path = output / ("rational_chart.json" if exact_pass else "candidate_rational_chart_failed_replay.json")
        chart_path.write_text(json.dumps(chart, separators=(",", ":"), sort_keys=True) + "\n", encoding="ascii")
        chart_output = {"path": chart_path.name, "sha256": file_hash(chart_path), "bytes": chart_path.stat().st_size}
        status = "PASS_P181_72DIGIT_EXACT_RESIDUAL_114_RATIONAL_CHART" if exact_pass else "PASS_P181_72DIGIT_INCOMPLETE_RESIDUAL_114_HEIGHT_BOUND"
    else:
        status = "PASS_P181_72DIGIT_INCOMPLETE_RESIDUAL_114_HEIGHT_BOUND"

    receipt = {
        "schema": "hc4.third-colon-residual-114-p181-72digit-lift.v1",
        "status": status,
        "inputs": {
            "source_chart_sha256": file_hash(SOURCE),
            "independent_source_audit_sha256": file_hash(AUDIT),
            "preregistration_sha256": file_hash(PREREGISTRATION),
            "amendment_01_sha256": amendment_hash,
        },
        "dimensions": {"B": [ROWS, ROWS], "C": [ROWS, COLUMNS], "transition_entries": ENTRIES},
        "factorization": factor_record,
        "starting_divisibility_mismatches": starting_mismatches,
        "corrections": correction_records,
        "terminal": {
            "digits": DIGITS,
            "modulus": str(modulus),
            "modulus_bit_length": modulus.bit_length(),
            "integer_invariant_mismatches": terminal_mismatches,
            "transition": {"path": transition_path.name, "sha256": file_hash(transition_path), "bytes": transition_path.stat().st_size},
        },
        "reconstruction": {
            "outcomes": outcomes,
            "unresolved": unresolved,
            "equal_height_bound": str(math.isqrt((modulus - 1) // 2)),
            "maximum_unique_numerator_bit_length": maximum_numerator_bits,
            "maximum_unique_denominator_bit_length": maximum_denominator_bits,
            "candidate_count_stream_sha256": candidate_count_hash.hexdigest(),
            "outcome_stream_sha256": outcome_hash.hexdigest(),
        },
        "rational_chart": chart_output,
        "exact_replay": exact_replay,
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {
            "exactly_71_new_digits": True,
            "no_73rd_digit": True,
            "single_prime_181_only": True,
            "no_selector_used_for_reconstruction": True,
            "failed_two_prime_candidate_not_read": True,
            "target_multiplier_not_read": True,
        },
        "claim_boundary": "An exact PASS proves only B*T=C for the fixed rational Koszul quotient chart. An incomplete PASS is only a 181^72 height bound. Neither proves QQ target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    receipt_path = output / "lift.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
