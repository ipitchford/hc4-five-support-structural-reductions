#!/usr/bin/env -S sage -python
"""Independent algebra, digit, reconstruction, and exact-chart replay."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import time
from pathlib import Path

import audit_j2_secant_r10_third_colon_residual_114_quotient_independent as source_independent


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 2_053
COLUMNS = 114
ENTRIES = ROWS * COLUMNS
DIGITS = 72
SOURCE = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
ARTIFACT = CAMPAIGN / "artifacts/third-colon-residual-114-p181-72digit-chart-v1"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-residual-114-p181-72digit-terminal.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-residual-114-p181-72digit-independent-audit.json"
REPLAY_PRIMES = (181, 173, 197, 2_147_483_647, 2_147_483_629)
EXPECTED = {
    "source": "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74",
    "lift": "cc5e83f0bce1ecc939434a53f908c337e3bbf33c64172424f7cbe9a2ee78aabe",
    "rational_chart": "914a21ab8c8556dec7b75737d076472a997a3ccd9d187279e046921ceac813fe",
    "T72": "8e085a734f7139af32c9f4a42a3a474e1f3637faf5a44733892024d062b28ff0",
    "terminal": "5490692f1ca86f633757a84a6bc1185cf2ab9b4beeb36cb0237f5d7b4688779e",
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def multiply_sparse_dense(rows, matrix):
    product = []
    for sparse_row in rows:
        total = [0] * COLUMNS
        for coordinate, coefficient in sparse_row:
            vector = matrix[coordinate]
            for column in range(COLUMNS):
                total[column] += coefficient * vector[column]
        product.append(total)
    return product


def decode_u8(path: Path):
    payload = path.read_bytes()
    require(len(payload) == ENTRIES, f"byte matrix length drift: {path.name}")
    require(all(value < P for value in payload), f"byte matrix value outside GF(181): {path.name}")
    return [list(payload[start:start + COLUMNS]) for start in range(0, ENTRIES, COLUMNS)], payload


def reconstruct_equal_height(residue: int, modulus: int):
    """Second spelling of symmetric rational reconstruction."""
    residue %= modulus
    if residue == 0:
        return (0, 1)
    limit = math.isqrt((modulus - 1) // 2)
    remainder_before, remainder = modulus, residue
    coefficient_before, coefficient = 0, 1
    while abs(remainder) > limit:
        quotient, next_remainder = divmod(remainder_before, remainder)
        remainder_before, remainder = remainder, next_remainder
        coefficient_before, coefficient = coefficient, coefficient_before - quotient * coefficient
    numerator, denominator = remainder, coefficient
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if not (
        denominator > 0
        and abs(numerator) <= limit
        and denominator <= limit
        and math.gcd(abs(numerator), denominator) == 1
        and math.gcd(denominator, P) == 1
        and (residue * denominator - numerator) % modulus == 0
    ):
        return None
    return numerator, denominator


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "72-digit independent audit already exists")
    require(file_hash(SOURCE) == EXPECTED["source"], "source artifact hash drift")
    require(file_hash(ARTIFACT / "lift.json") == EXPECTED["lift"], "producer receipt hash drift")
    require(file_hash(ARTIFACT / "rational_chart.json") == EXPECTED["rational_chart"], "rational chart hash drift")
    require(file_hash(ARTIFACT / "T_mod_181_power_72.json") == EXPECTED["T72"], "T72 hash drift")
    require(file_hash(TERMINAL) == EXPECTED["terminal"], "terminal hash drift")
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    producer = json.loads((ARTIFACT / "lift.json").read_text(encoding="utf-8"))
    require(terminal.get("status") == "PASS_P181_72DIGIT_EXACT_RESIDUAL_114_RATIONAL_CHART", "terminal PASS drift")
    require(producer.get("status") == terminal.get("status"), "producer PASS drift")

    source_independent.WALL_CAP_SECONDS = 600.0
    source_independent.RSS_CAP_BYTES = 1_500_000_000
    integer_rows = source_independent.reconstruct_koszul(CAMPAIGN, started)
    free, _bindings = source_independent.load_free_sources(CAMPAIGN)
    restricted, _absolute_to_local = source_independent.restrict_rows(integer_rows, free)
    pivots, pivot_telemetry = source_independent.select_p181_pivots(restricted, started)
    complement = sorted(set(range(source_independent.FREE_COUNT)) - set(pivots))
    require(len(pivots) == ROWS and len(complement) == COLUMNS, "independent pivot dimensions drift")
    b_rows, c_rows = source_independent.split_matrices(restricted, pivots, complement)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    b_payload = [[[column, str(value)] for column, value in row] for row in b_rows]
    c_payload = [[[column, str(value)] for column, value in row] for row in c_rows]
    require(b_payload == source["B_sparse_integer_rows"], "independent B payload drift")
    require(c_payload == source["C_sparse_integer_rows"], "independent C payload drift")
    c_matrix = [[0] * COLUMNS for _ in range(ROWS)]
    for row_index, row in enumerate(c_rows):
        for column, value in row:
            c_matrix[row_index][column] = value

    transition = [[int(value) for value in row] for row in source["prime_records"]["181"]["transition_matrix_row_major"]]
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
    require(starting_mismatches == 0, "independent initial divisibility failed")

    digit_audits = []
    for digit_index in range(1, DIGITS):
        rhs_path = ARTIFACT / f"correction_rhs_digit_{digit_index:02d}.u8"
        digit_path = ARTIFACT / f"digit_{digit_index:02d}.u8"
        rhs_matrix, rhs_payload = decode_u8(rhs_path)
        expected_rhs = bytes(value % P for row in quotient for value in row)
        require(rhs_payload == expected_rhs, f"correction RHS drift at digit {digit_index}")
        digit, digit_payload = decode_u8(digit_path)
        digit_product = multiply_sparse_dense(b_rows, digit)
        next_quotient = []
        modular_mismatches = 0
        divisibility_mismatches = 0
        for row in range(ROWS):
            next_row = []
            for column in range(COLUMNS):
                modular_mismatches += int((digit_product[row][column] - rhs_matrix[row][column]) % P != 0)
                numerator = quotient[row][column] - digit_product[row][column]
                divisibility_mismatches += int(numerator % P != 0)
                next_row.append(numerator // P)
            next_quotient.append(next_row)
        require(modular_mismatches == 0 and divisibility_mismatches == 0, f"digit replay failed at {digit_index}")
        transition = [
            [left + modulus * right for left, right in zip(left_row, right_row)]
            for left_row, right_row in zip(transition, digit)
        ]
        modulus *= P
        quotient = next_quotient
        digit_audits.append({
            "digit_index": digit_index,
            "rhs_sha256": hashlib.sha256(rhs_payload).hexdigest(),
            "digit_sha256": hashlib.sha256(digit_payload).hexdigest(),
            "modular_mismatches": modular_mismatches,
            "divisibility_mismatches": divisibility_mismatches,
        })
        if digit_index % 8 == 0:
            source_independent.guard(started, f"independent digit replay {digit_index}")
    require(modulus == P**DIGITS, "independent terminal modulus drift")
    serialized = [[int(value) for value in row] for row in json.loads((ARTIFACT / "T_mod_181_power_72.json").read_text(encoding="utf-8"))]
    require(transition == serialized, "independent T72 serialization drift")
    terminal_product = multiply_sparse_dense(b_rows, transition)
    terminal_mismatches = sum(
        c_matrix[row][column] - terminal_product[row][column] != modulus * quotient[row][column]
        for row in range(ROWS)
        for column in range(COLUMNS)
    )
    require(terminal_mismatches == 0, "independent terminal invariant failed")

    pairs = []
    outcomes = {"unique_zero": 0, "unique_nonzero": 0, "no_candidate": 0}
    label_hash = hashlib.sha256()
    for row in transition:
        for residue in row:
            candidate = reconstruct_equal_height(residue, modulus)
            if candidate is None:
                label = "no_candidate"
                pairs.append((0, 0))
            elif candidate[0] == 0:
                label = "unique_zero"
                pairs.append(candidate)
            else:
                label = "unique_nonzero"
                pairs.append(candidate)
            outcomes[label] += 1
            label_hash.update(f"{label}\n".encode("ascii"))
    require(outcomes == {"unique_zero": 228_643, "unique_nonzero": 5_399, "no_candidate": 0}, "independent reconstruction census drift")
    chart = json.loads((ARTIFACT / "rational_chart.json").read_text(encoding="utf-8"))
    chart_pairs = [(int(numerator), int(denominator)) for numerator, denominator in chart["rational_pairs_row_major"]]
    require(pairs == chart_pairs, "independent rational-pair stream drift")

    global_denominator = math.lcm(*(denominator for _numerator, denominator in pairs))
    numerators = [numerator * (global_denominator // denominator) for numerator, denominator in pairs]
    numerator_matrix = [numerators[start_index:start_index + COLUMNS] for start_index in range(0, ENTRIES, COLUMNS)]
    stored_numerators = [[int(value) for value in row] for row in chart["integer_numerator_matrix_row_major"]]
    require(str(global_denominator) == chart["global_denominator"], "independent global denominator drift")
    require(numerator_matrix == stored_numerators, "independent integer numerator matrix drift")
    content = 0
    for value in numerators:
        content = math.gcd(content, abs(value))
    require(math.gcd(global_denominator, content) == 1, "independent primitive normalization failed")
    exact_product = multiply_sparse_dense(b_rows, numerator_matrix)
    exact_mismatches = 0
    residual_hash = hashlib.sha256()
    for row in range(ROWS):
        for column in range(COLUMNS):
            residual = exact_product[row][column] - global_denominator * c_matrix[row][column]
            exact_mismatches += int(residual != 0)
            residual_hash.update(f"{residual}\n".encode("ascii"))
    require(exact_mismatches == 0, "independent B*N=D*C replay failed")

    reductions = {}
    for prime in REPLAY_PRIMES:
        require(global_denominator % prime != 0, f"independent denominator nonunit at {prime}")
        inverse = pow(global_denominator % prime, -1, prime)
        reduced = [[value % prime * inverse % prime for value in row] for row in numerator_matrix]
        expected = source["prime_records"][str(prime)]["transition_matrix_row_major"]
        mismatches = sum(left != right for left_row, right_row in zip(reduced, expected) for left, right in zip(left_row, right_row))
        require(mismatches == 0, f"independent fibre replay failed at {prime}")
        reductions[str(prime)] = {"mismatch_count": mismatches, "transition_matrix_row_major_sha256": canonical_hash(reduced)}

    receipt = {
        "schema": "hc4.third-colon-residual-114-p181-72digit-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_72DIGIT_EXACT_RESIDUAL_114_RATIONAL_CHART_REPLAY",
        "bound_hashes": {
            "auditor_script": file_hash(Path(__file__)),
            "source_chart": file_hash(SOURCE),
            "producer_receipt": file_hash(ARTIFACT / "lift.json"),
            "rational_chart": file_hash(ARTIFACT / "rational_chart.json"),
            "T72": file_hash(ARTIFACT / "T_mod_181_power_72.json"),
            "terminal": file_hash(TERMINAL),
        },
        "source_reconstruction": {
            "integer_koszul_rows": len(integer_rows),
            "integer_koszul_nonzeros": sum(map(len, integer_rows)),
            "B_nonzeros": sum(map(len, b_rows)),
            "C_nonzeros": sum(map(len, c_rows)),
            "pivot_telemetry": pivot_telemetry,
            "B_payload_sha256": canonical_hash(b_payload),
            "C_payload_sha256": canonical_hash(c_payload),
        },
        "lift_replay": {
            "starting_divisibility_mismatches": starting_mismatches,
            "correction_count": len(digit_audits),
            "digit_audits": digit_audits,
            "terminal_modulus": str(modulus),
            "terminal_modulus_bit_length": modulus.bit_length(),
            "terminal_integer_invariant_mismatches": terminal_mismatches,
        },
        "reconstruction": {
            "outcomes": outcomes,
            "equal_height_bound": str(math.isqrt((modulus - 1) // 2)),
            "acceptance_label_stream_sha256": label_hash.hexdigest(),
            "rational_pair_stream_sha256": canonical_hash([[str(numerator), str(denominator)] for numerator, denominator in pairs]),
            "global_denominator": str(global_denominator),
            "global_denominator_bit_length": global_denominator.bit_length(),
            "integer_numerator_matrix_sha256": canonical_hash([[str(value) for value in row] for row in numerator_matrix]),
        },
        "exact_replay": {
            "B_times_N_equals_D_times_C_mismatches": exact_mismatches,
            "residual_stream_sha256": residual_hash.hexdigest(),
            "five_fibre_reductions": reductions,
        },
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
        },
        "declarations": {
            "producer_not_imported_or_executed": True,
            "source_integer_chart_rebuilt_from_rational_generators": True,
            "all_71_raw_digits_and_rhs_replayed": True,
            "equal_height_reconstruction_reimplemented": True,
            "global_primitive_chart_rebuilt": True,
            "no_73rd_digit": True,
            "target_multiplier_not_read": True,
        },
        "claim_boundary": "This PASS independently certifies only the exact rational identity B*T=C for the fixed Koszul quotient chart. It does not prove QQ target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    require(receipt["resources"]["process_swaps"] == 0, "independent audit process swapped")
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
