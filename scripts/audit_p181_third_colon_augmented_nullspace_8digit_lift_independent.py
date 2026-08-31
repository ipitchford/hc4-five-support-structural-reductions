#!/usr/bin/env python3
"""Independent exact replay of the successful eight-digit p181 lift."""

from __future__ import annotations

import hashlib
import json
import resource
import struct
import time
from array import array
from collections import Counter
from pathlib import Path

from fixed_p181_dixon_rr import (
    AMBIGUOUS,
    NO_CANDIDATE,
    UNIQUE_NONZERO,
    UNIQUE_ZERO,
    classify,
)


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-8digit-lift-v2"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-8digit-lift-v2.json"
INTEGRAL = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_b_Z_fixed_gauge.i64csr"
DIGIT_ZERO = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-solve-v1/solution_mod181.u8"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-8digit-lift-independent-audit.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI181", "integral magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "integral dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * nonzeros])]
    cursor += 8 * nonzeros
    rhs = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * rows])]
    cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return offsets, indices, values, rhs


def matvec(offsets: list[int], indices: list[int], values: list[int], vector: list[int]) -> list[int]:
    return [
        sum(values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1]))
        for row in range(ROWS)
    ]


def rr_labels(vector: list[int], modulus: int) -> tuple[bytes, dict[str, int]]:
    labels = bytearray()
    counts: Counter[int] = Counter()
    for value in vector:
        outcome = classify(value % modulus, modulus)
        labels.append(outcome.label)
        counts[outcome.label] += 1
    return bytes(labels), {
        "NO_CANDIDATE": counts[NO_CANDIDATE],
        "UNIQUE_ZERO": counts[UNIQUE_ZERO],
        "UNIQUE_NONZERO": counts[UNIQUE_NONZERO],
        "AMBIGUOUS": counts[AMBIGUOUS],
    }


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "independent lift audit already exists")
    producer = json.loads((ARTIFACT / "lift.json").read_text(encoding="utf-8"))
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    require(producer.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT", "producer PASS drift")
    require(terminal.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT", "terminal PASS drift")
    offsets, indices, values, rhs = read_integral()
    x = list(DIGIT_ZERO.read_bytes())
    product = matvec(offsets, indices, values, x)
    q = []
    digit_zero_divisibility_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        if residual % P:
            digit_zero_divisibility_mismatches += 1
        q.append(residual // P)
    require(digit_zero_divisibility_mismatches == 0, "digit-zero divisibility replay failed")
    modulus = P
    digit_audits = []
    rr_audits: dict[str, object] = {}
    for digit_index in range(1, 8):
        expected_rhs = bytes(value % P for value in q)
        rhs_path = ARTIFACT / f"correction_rhs_digit_{digit_index}.u8"
        digit_path = ARTIFACT / f"digit_{digit_index}.u8"
        require(rhs_path.read_bytes() == expected_rhs, f"correction RHS mismatch at digit {digit_index}")
        digit = list(digit_path.read_bytes())
        require(len(digit) == COLUMNS and all(value < P for value in digit), f"digit stream drift at {digit_index}")
        product_digit = matvec(offsets, indices, values, digit)
        next_q = []
        divisibility_mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - product_digit[row]
            if numerator % P:
                divisibility_mismatches += 1
            next_q.append(numerator // P)
        require(divisibility_mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        require(len(x) == len(digit), "digit length mismatch")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
        q = next_q
        digit_audits.append(
            {
                "digit_index": digit_index,
                "correction_rhs_sha256": file_hash(rhs_path),
                "digit_sha256": file_hash(digit_path),
                "divisibility_mismatches": divisibility_mismatches,
                "maximum_q_bit_length": max(abs(value).bit_length() for value in q),
            }
        )
        if digit_index + 1 in (4, 6, 8):
            labels, counts = rr_labels(x, modulus)
            expected_labels_path = ARTIFACT / f"rr_labels_{digit_index + 1}.u8"
            require(labels == expected_labels_path.read_bytes(), f"RR label replay failed at {digit_index + 1} digits")
            require(counts == producer["rr_snapshots"][str(digit_index + 1)]["aggregate_labels"], "RR count replay drift")
            rr_audits[str(digit_index + 1)] = {
                "aggregate_labels": counts,
                "label_stream_sha256": hashlib.sha256(labels).hexdigest(),
            }

    require(modulus == P**8 == 1_151_936_657_823_500_641, "terminal modulus drift")
    terminal_x_path = ARTIFACT / "X_mod_181_power_8.u64le"
    expected_x = array("Q", x).tobytes()
    require(terminal_x_path.read_bytes() == expected_x, "terminal X stream mismatch")
    direct = matvec(offsets, indices, values, x)
    terminal_invariant_mismatches = sum(
        rhs[row] - direct[row] != modulus * q[row] for row in range(ROWS)
    )
    require(terminal_invariant_mismatches == 0, "terminal exact integer invariant failed")
    external = terminal["telemetry"]["external_time"]
    require(
        external["real_seconds"] <= 1200
        and external["maximum_rss_bytes"] <= 4_294_967_296
        and external["process_swaps"] == 0,
        "producer resource gate drift",
    )
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-8digit-lift-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT_REPLAY",
        "bound_hashes": {
            "producer": file_hash(ARTIFACT / "lift.json"),
            "terminal": file_hash(TERMINAL),
            "integral_system": file_hash(INTEGRAL),
            "digit_zero": file_hash(DIGIT_ZERO),
            "terminal_X": file_hash(terminal_x_path),
        },
        "checks": {
            "digit_zero_divisibility_mismatches": digit_zero_divisibility_mismatches,
            "correction_count": len(digit_audits),
            "terminal_modulus": str(modulus),
            "terminal_integer_invariant_mismatches": terminal_invariant_mismatches,
        },
        "digit_audits": digit_audits,
        "rr_audits": rr_audits,
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "producer_external": external,
        },
        "declarations": {
            "producer_not_imported_or_executed": True,
            "linbox_not_called": True,
            "all_digits_recomputed_from_exact_integer_recurrence": True,
            "no_ninth_digit": True,
            "no_rational_identity_claim": True,
        },
        "claim_boundary": (
            "This PASS independently certifies the exact finite p181 lift through eight total digits and the "
            "registered reconstruction labels. It is not a QQ identity, colon, saturation, secant closure, "
            "nullcone containment, or HC4 theorem."
        ),
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
