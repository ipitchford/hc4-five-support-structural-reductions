#!/usr/bin/env python3
"""Independently audit the exact/modular p173 fourth-colon lift interface."""

from __future__ import annotations

import hashlib
import json
import resource
import struct
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 173
ROWS = 85_688
COLUMNS = 36_587
NONZEROS = 1_487_624
SOURCE = CAMPAIGN / "artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
INTEGRAL = SOURCE / "A_Z_b_Z_fixed_gauge_p173.i64csr"
MODULAR = SOURCE / "A_Z_mod173_fixed_gauge.csr"
SOLUTION = SOURCE / "solution_mod173.u8"
PRODUCER = SOURCE / "integral-system.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-integral-system-independent-audit.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI173", "integral magic mismatch")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "integral dimensions mismatch")
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


def parse_modular() -> tuple[list[int], list[int], bytes]:
    payload = MODULAR.read_bytes()
    require(payload[:8] == b"HC4AC173", "modular magic mismatch")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "modular dimensions mismatch")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = payload[cursor:cursor + nonzeros]
    cursor += nonzeros
    require(cursor == len(payload), "modular trailing bytes")
    return offsets, indices, values


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "independent audit output already exists")
    producer = json.loads(PRODUCER.read_text(encoding="ascii"))
    require(producer.get("status") == "PASS_FOURTH_COLON_P173_FIXED_GAUGE_INTEGRAL_LIFT_SYSTEM", "producer status drift")
    require(producer["outputs"][INTEGRAL.name]["sha256"] == digest(INTEGRAL), "producer integral hash drift")
    require(producer["outputs"][MODULAR.name]["sha256"] == digest(MODULAR), "producer modular hash drift")
    require(producer["outputs"][SOLUTION.name]["sha256"] == digest(SOLUTION), "producer solution hash drift")

    offsets, indices, values, rhs = parse_integral()
    modular_offsets, modular_indices, modular_values = parse_modular()
    require(offsets == modular_offsets, "offset reduction mismatch")
    require(indices == modular_indices, "index reduction mismatch")
    coefficient_reduction_mismatches = sum(value % P != modular for value, modular in zip(values, modular_values, strict=True))
    zero_modular_entries = sum(modular == 0 for modular in modular_values)
    require(coefficient_reduction_mismatches == zero_modular_entries == 0, "coefficient reduction mismatch")
    require(offsets[0] == 0 and offsets[-1] == NONZEROS, "offset boundary mismatch")
    require(all(left <= right for left, right in zip(offsets, offsets[1:])), "offset monotonicity mismatch")
    require(all(index < COLUMNS for index in indices), "column out of range")
    for row in range(ROWS):
        row_indices = indices[offsets[row]:offsets[row + 1]]
        require(all(left < right for left, right in zip(row_indices, row_indices[1:])), f"column ordering mismatch at row {row}")

    solution = list(SOLUTION.read_bytes())
    require(len(solution) == COLUMNS and all(value < P for value in solution), "solution stream mismatch")
    replay_mismatches = 0
    residual_digest = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            (values[position] % P) * solution[indices[position]]
            for position in range(offsets[row], offsets[row + 1])
        ) % P
        residual = (total - rhs[row]) % P
        replay_mismatches += residual != 0
        residual_digest.update(bytes([residual]))
    require(replay_mismatches == 0, "digit-zero replay mismatch")

    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < 120 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.fourth-colon-p173-integral-system-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P173_FOURTH_COLON_INTEGRAL_SYSTEM_REPLAY",
        "bound_hashes": {
            "integral_system": digest(INTEGRAL),
            "modular_csr": digest(MODULAR),
            "digit_zero": digest(SOLUTION),
            "producer": digest(PRODUCER),
        },
        "dimensions": {"rows": ROWS, "columns": COLUMNS, "nonzeros": NONZEROS},
        "checks": {
            "coefficient_reduction_mismatches": coefficient_reduction_mismatches,
            "zero_modular_entries": zero_modular_entries,
            "digit_zero_replay_mismatches": replay_mismatches,
            "residual_stream_sha256": residual_digest.hexdigest(),
        },
        "resources": resources,
        "declarations": {
            "builder_not_imported_or_executed": True,
            "solver_not_executed": True,
            "exact_and_modular_formats_parsed_separately": True,
        },
        "claim_boundary": (
            "This PASS independently certifies the fixed-gauge integer/modular interface and digit-zero replay. "
            "It adds no p-adic digit and proves no rational target membership, polynomial identity, colon equality, "
            "saturation, nullcone containment, or HC4 theorem."
        ),
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
