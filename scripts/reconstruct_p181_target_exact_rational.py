#!/usr/bin/env python3
"""Reconstruct and exactly replay the fixed-main p181 third-colon target."""

from __future__ import annotations

import argparse
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
P54_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-target-54digit-extension-v1"
X54 = P54_SOURCE / "X_mod_181_power_54.json"
P54_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-54digit-extension-independent-audit.json"
INTEGRAL_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-integral-lift-system-independent-audit.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def reconstruct(residue: int, modulus: int) -> tuple[int, int] | None:
    residue %= modulus
    if residue == 0:
        return 0, 1
    bound = math.isqrt((modulus - 1) // 2)
    old_r, remainder = modulus, residue
    old_t, coefficient = 0, 1
    while abs(remainder) > bound:
        quotient = old_r // remainder
        old_r, remainder = remainder, old_r - quotient * remainder
        old_t, coefficient = coefficient, old_t - quotient * coefficient
    numerator, denominator = remainder, coefficient
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if denominator <= 0 or abs(numerator) > bound or denominator > bound:
        return None
    if math.gcd(abs(numerator), denominator) != 1 or (residue * denominator - numerator) % modulus:
        return None
    return numerator, denominator


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    p54_audit = json.loads(P54_AUDIT.read_text(encoding="utf-8"))
    integral_audit = json.loads(INTEGRAL_AUDIT.read_text(encoding="utf-8"))
    require(p54_audit.get("status") == "PASS_INDEPENDENT_P181_TARGET_54DIGIT_LIFT_REPLAY", "p54 audit status drift")
    require(integral_audit.get("status") == "PASS_INDEPENDENT_P181_INTEGRAL_LIFT_SYSTEM_REPLAY", "integral audit status drift")
    require(p54_audit["bound_hashes"]["x54"] == digest(X54), "audited p54 endpoint drift")
    require(integral_audit["bound_hashes"]["integral_system"] == digest(INTEGRAL), "audited integral system drift")
    modulus = P**54
    residues = [int(value) for value in json.loads(X54.read_text(encoding="utf-8"))]
    require(len(residues) == COLUMNS, "p54 coordinate count drift")
    pairs = [reconstruct(value, modulus) for value in residues]
    require(all(pair is not None for pair in pairs), "unresolved coordinate")
    rational_pairs = [pair for pair in pairs if pair is not None]
    require(all(denominator > 0 and math.gcd(abs(numerator), denominator) == 1 for numerator, denominator in rational_pairs), "pair normalization drift")
    pair_reduction_mismatches = sum((residue * denominator - numerator) % modulus != 0 for residue, (numerator, denominator) in zip(residues, rational_pairs, strict=True))
    require(pair_reduction_mismatches == 0, "p54 pair reduction mismatch")
    denominator = 1
    for _numerator, local_denominator in rational_pairs:
        denominator = math.lcm(denominator, local_denominator)
    require(math.gcd(denominator, P) == 1, "global denominator is not an 181-unit")
    numerators = [numerator * (denominator // local_denominator) for numerator, local_denominator in rational_pairs]
    encoding_mismatches = sum(integer != numerator * (denominator // local_denominator) for integer, (numerator, local_denominator) in zip(numerators, rational_pairs, strict=True))
    reduction_mismatches = sum(integer % modulus * pow(denominator, -1, modulus) % modulus != residue for integer, residue in zip(numerators, residues, strict=True))
    require(encoding_mismatches == reduction_mismatches == 0, "common-denominator encoding mismatch")

    offsets, indices, values, rhs = read_integral()
    exact_mismatches = 0
    residual_digest = hashlib.sha256()
    maximum_absolute_residual = 0
    for row in range(ROWS):
        total = sum(values[position] * numerators[indices[position]] for position in range(offsets[row], offsets[row + 1]))
        residual = total - denominator * rhs[row]
        exact_mismatches += residual != 0
        maximum_absolute_residual = max(maximum_absolute_residual, abs(residual))
        residual_digest.update(f"{residual}\n".encode("ascii"))
    require(exact_mismatches == 0, "exact rational target replay mismatch")

    pairs_path = output / "rational_target_pairs_local.json"
    vector_path = output / "primitive_common_denominator_vector.json"
    pairs_path.write_text(json.dumps(rational_pairs, separators=(",", ":")) + "\n", encoding="ascii")
    vector_path.write_text(json.dumps({"denominator": denominator, "integer_numerators": numerators}, separators=(",", ":")) + "\n", encoding="ascii")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 300 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-target-exact-rational-replay.v1",
        "status": "PASS_P181_TARGET_EXACT_RATIONAL_SYSTEM_REPLAY",
        "inputs": {"integral_system_sha256": digest(INTEGRAL), "p54_residues_sha256": digest(X54), "p54_independent_audit_sha256": digest(P54_AUDIT), "integral_system_independent_audit_sha256": digest(INTEGRAL_AUDIT)},
        "reconstruction": {"modulus": str(modulus), "equal_height_bound": math.isqrt((modulus - 1) // 2), "coordinate_count": COLUMNS, "unresolved_count": 0, "support_count": sum(numerator != 0 for numerator, _denominator in rational_pairs), "global_denominator": denominator, "global_denominator_bit_length": denominator.bit_length(), "maximum_absolute_numerator": max(abs(numerator) for numerator, _denominator in rational_pairs), "maximum_denominator": max(local_denominator for _numerator, local_denominator in rational_pairs), "pair_reduction_mismatch_count": pair_reduction_mismatches, "common_encoding_mismatch_count": encoding_mismatches, "common_reduction_mismatch_count": reduction_mismatches},
        "exact_replay": {"row_comparisons": ROWS, "mismatch_count": exact_mismatches, "maximum_absolute_residual": maximum_absolute_residual, "residual_stream_sha256": residual_digest.hexdigest()},
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (pairs_path, vector_path)},
        "resources": resources,
        "declarations": {"no_new_p_adic_digit": True, "kernel_gauge_not_adjusted": True, "denominator_model_not_used": True, "fixed_coordinate_support": True},
        "claim_boundary": "This PASS proves exact rational membership in the frozen source-clean fixed-main coefficient system. Independent certificate replay and independent source-to-polynomial interpretation remain separate gates; no saturation, secant, nullcone, or HC4 theorem follows.",
    }
    receipt_path = output / "replay.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
