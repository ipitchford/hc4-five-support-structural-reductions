#!/usr/bin/env python3
"""Independent certificate replay for the exact p181 target solution."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import struct
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1"
INTEGRAL = SOURCE / "A_Z_b_Z_fixed_gauge.i64csr"
CERTIFICATE = CAMPAIGN / "artifacts/third-colon-p181-target-exact-rational-replay-v1"
PAIRS = CERTIFICATE / "rational_target_pairs_local.json"
COMMON = CERTIFICATE / "primitive_common_denominator_vector.json"
PRODUCER = CERTIFICATE / "replay.json"
X54 = CAMPAIGN / "artifacts/third-colon-p181-target-54digit-extension-v1/X_mod_181_power_54.json"
P54_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-54digit-extension-independent-audit.json"
INTEGRAL_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-integral-lift-system-independent-audit.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-exact-rational-independent-audit.json"


def digest(path: Path) -> str:
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
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor)); cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]; cursor += 4 * nonzeros
    values = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * nonzeros])]; cursor += 8 * nonzeros
    rhs = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * rows])]; cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return offsets, indices, values, rhs


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "independent target audit already exists")
    producer = json.loads(PRODUCER.read_text(encoding="utf-8"))
    p54_audit = json.loads(P54_AUDIT.read_text(encoding="utf-8"))
    integral_audit = json.loads(INTEGRAL_AUDIT.read_text(encoding="utf-8"))
    require(producer.get("status") == "PASS_P181_TARGET_EXACT_RATIONAL_SYSTEM_REPLAY", "producer status drift")
    require(p54_audit.get("status") == "PASS_INDEPENDENT_P181_TARGET_54DIGIT_LIFT_REPLAY", "p54 audit status drift")
    require(integral_audit.get("status") == "PASS_INDEPENDENT_P181_INTEGRAL_LIFT_SYSTEM_REPLAY", "integral audit status drift")
    require(p54_audit["bound_hashes"]["x54"] == digest(X54), "p54 endpoint drift")
    require(integral_audit["bound_hashes"]["integral_system"] == digest(INTEGRAL), "integral system drift")
    raw_pairs = json.loads(PAIRS.read_text(encoding="ascii"))
    common = json.loads(COMMON.read_text(encoding="ascii"))
    require(len(raw_pairs) == COLUMNS and len(common["integer_numerators"]) == COLUMNS, "certificate dimensions drift")
    pairs = [(int(pair[0]), int(pair[1])) for pair in raw_pairs]
    denominator = int(common["denominator"])
    numerators = [int(value) for value in common["integer_numerators"]]
    require(denominator > 0 and math.gcd(denominator, P) == 1, "global denominator normalization drift")
    normalization_mismatches = 0
    encoding_mismatches = 0
    for integer, (numerator, local_denominator) in zip(numerators, pairs, strict=True):
        normalization_mismatches += local_denominator <= 0 or math.gcd(abs(numerator), local_denominator) != 1 or denominator % local_denominator != 0
        encoding_mismatches += integer != numerator * (denominator // local_denominator)
    require(normalization_mismatches == encoding_mismatches == 0, "certificate encoding mismatch")
    residues = [int(value) for value in json.loads(X54.read_text(encoding="utf-8"))]
    modulus = P**54
    pair_reduction_mismatches = sum((residue * local_denominator - numerator) % modulus != 0 for residue, (numerator, local_denominator) in zip(residues, pairs, strict=True))
    common_reduction_mismatches = sum(integer % modulus * pow(denominator, -1, modulus) % modulus != residue for integer, residue in zip(numerators, residues, strict=True))
    require(pair_reduction_mismatches == common_reduction_mismatches == 0, "certificate modular reduction mismatch")
    offsets, indices, values, rhs = read_integral()
    mismatches = 0
    residual_digest = hashlib.sha256()
    maximum_absolute_residual = 0
    for row in range(ROWS):
        total = sum(values[position] * numerators[indices[position]] for position in range(offsets[row], offsets[row + 1]))
        residual = total - denominator * rhs[row]
        mismatches += residual != 0
        maximum_absolute_residual = max(maximum_absolute_residual, abs(residual))
        residual_digest.update(f"{residual}\n".encode("ascii"))
    require(mismatches == 0, "independent exact target replay mismatch")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 120 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-target-exact-rational-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_TARGET_EXACT_RATIONAL_SYSTEM_SOLUTION",
        "bound_hashes": {"integral_system": digest(INTEGRAL), "pairs": digest(PAIRS), "common_denominator_vector": digest(COMMON), "producer": digest(PRODUCER), "p54_residues": digest(X54), "p54_independent_audit": digest(P54_AUDIT), "integral_system_independent_audit": digest(INTEGRAL_AUDIT)},
        "certificate_checks": {"coordinate_count": COLUMNS, "support_count": sum(numerator != 0 for numerator, _denominator in pairs), "global_denominator_bit_length": denominator.bit_length(), "normalization_mismatch_count": normalization_mismatches, "encoding_mismatch_count": encoding_mismatches, "pair_reduction_mismatch_count": pair_reduction_mismatches, "common_reduction_mismatch_count": common_reduction_mismatches},
        "exact_replay": {"row_comparisons": ROWS, "mismatch_count": mismatches, "maximum_absolute_residual": maximum_absolute_residual, "residual_stream_sha256": residual_digest.hexdigest()},
        "resources": resources,
        "declarations": {"solver_not_executed": True, "p_adic_lifter_not_imported_or_executed": True, "producer_not_imported_or_executed": True, "certificate_replay_reimplemented": True},
        "claim_boundary": "This PASS independently certifies the exact rational target-system solution. Independent source-to-polynomial reconstruction remains separate; no saturation, secant, nullcone, or HC4 theorem follows.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
