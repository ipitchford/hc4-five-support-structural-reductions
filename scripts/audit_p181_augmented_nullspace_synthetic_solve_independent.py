#!/usr/bin/env python3
"""Standard-library audit of the augmented-nullspace synthetic solve PASS."""

from __future__ import annotations

import hashlib
import json
import platform
import resource
import struct
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-v1.json"
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-implementation-freeze.json"
CSR = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr"
DRIVER = CAMPAIGN / "scripts/linbox_augmented_nullspace_mod181_solve_driver.cpp"
WRAPPER = CAMPAIGN / "scripts/run_p181_augmented_nullspace_synthetic_solve_gated.py"
REGISTRATION = CAMPAIGN / "research/THIRD_COLON_P181_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_INDEPENDENT_AUDIT_REGISTRATION.md"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-independent-audit.json"
ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-synthetic-solve-v1"

STAGES = {
    4096: (146642, "b96a4e6c7023bcf352f716803c627f5381b59acd57672b31e5e0aba219b99bcb", 90, 1073741824),
    8192: (301450, "a7ca07d2c1c68216056e685b057e94f54fe9da5714b3473622a649ad449f831c", 150, 1610612736),
    16384: (546088, "d5bfcb5934119b4f29e7254d8cd620b21bc51bda0d17281bd348be2b3a3a609a", 300, 2684354560),
    35881: (1354540, "ebcf2e6338e5eb81ba7b9fd58f8c9366a8b5ddb48c27cef7fcd34e9c27663d28", 600, 3758096384),
}
EXPECTED_HASHES = {
    "terminal": "2e1ba4096dcba2e6ffe985ed37c5010b9e459df585758f1d5e2ec9cdd31370d5",
    "freeze": "592da663afddfe825da03d4982ba8b358ce03f24ab6a5dca409267c4fbea9502",
    "csr": "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef",
    "driver": "339566a8622a9b11fafaf2432e29ba40541689002e01de5d721d8f3d66b7560b",
    "wrapper": "4644b37128cd7e3882fcfcc3e92f98d576097083865abbccf2bcfa0a967ee309",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def read_csr() -> tuple[list[int], memoryview, memoryview]:
    payload = CSR.read_bytes()
    require(payload[:8] == b"HC4AC181", "CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (85651, 35881, 1354540), "CSR header drift")
    offset = 32
    indptr = list(struct.unpack_from(f"<{rows + 1}Q", payload, offset))
    offset += 8 * (rows + 1)
    indices = memoryview(payload)[offset:offset + 4 * nonzeros].cast("I")
    offset += 4 * nonzeros
    data = memoryview(payload)[offset:offset + nonzeros]
    offset += nonzeros
    require(offset == len(payload), "CSR trailing or missing bytes")
    require(indptr[0] == 0 and indptr[-1] == nonzeros, "CSR offset boundary drift")
    require(all(a <= b for a, b in zip(indptr, indptr[1:])), "CSR offsets not monotone")
    require(all(0 < value < 181 for value in data), "CSR value outside nonzero GF(181) residues")
    for row in range(rows):
        start, stop = indptr[row], indptr[row + 1]
        require(all(indices[pos - 1] < indices[pos] for pos in range(start + 1, stop)), f"CSR row {row} not ordered")
    return indptr, indices, data


def expected_vector(width: int) -> bytes:
    return bytes((((column + 1) * 37 + 11) % 180) + 1 for column in range(width))


def replay(indptr: list[int], indices: memoryview, data: memoryview, vector: bytes, width: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    prefix_nonzeros = 0
    row_values = bytearray(len(indptr) - 1)
    for row in range(len(row_values)):
        total = 0
        for position in range(indptr[row], indptr[row + 1]):
            column = indices[position]
            if column >= width:
                break
            total += data[position] * vector[column]
            prefix_nonzeros += 1
        row_values[row] = total % 181
    digest.update(row_values)
    return digest.hexdigest(), prefix_nonzeros


def audit_source_boundary() -> dict[str, object]:
    texts = {"driver": DRIVER.read_text(encoding="utf-8"), "wrapper": WRAPPER.read_text(encoding="utf-8")}
    forbidden = (
        "j2-secant-r10-third-colon-kernel-qq-candidate",
        "j2-secant-r10-third-colon-identity-extended",
        "--rhs",
        "external_rhs",
        "181^2",
        "32761",
    )
    findings = {name: [token for token in forbidden if token in text] for name, text in texts.items()}
    require(not any(findings.values()), f"target-bearing source token found: {findings}")
    return {
        "forbidden_tokens": list(forbidden),
        "findings": findings,
        "driver_has_no_rhs_argument": "--rhs" not in texts["driver"],
        "wrapper_invokes_only_csr_columns_and_solution_output": all(token in texts["wrapper"] for token in ("--csr", "--columns", "--solution-output")),
    }


def main() -> int:
    started = time.perf_counter()
    initial_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    require(not OUTPUT.exists(), "independent audit output already exists")
    observed_hashes = {
        "terminal": file_hash(TERMINAL),
        "freeze": file_hash(FREEZE),
        "csr": file_hash(CSR),
        "driver": file_hash(DRIVER),
        "wrapper": file_hash(WRAPPER),
        "registration": file_hash(REGISTRATION),
    }
    for key, expected in EXPECTED_HASHES.items():
        require(observed_hashes[key] == expected, f"bound hash drift: {key}")
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    require(terminal.get("status") == "PASS_ACTUAL_COEFFICIENT_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_SCALING", "terminal PASS drift")
    require([record.get("columns") for record in terminal.get("stages", [])] == list(STAGES), "stage order drift")
    source_boundary = audit_source_boundary()
    indptr, indices, data = read_csr()
    stage_audits = []
    for record in terminal["stages"]:
        width = record["columns"]
        expected_nonzeros, expected_hash, wall_cap, rss_cap = STAGES[width]
        solution_path = ARTIFACT / f"solution-{width}.u8"
        solution = solution_path.read_bytes()
        expected = expected_vector(width)
        require(solution == expected, f"coordinatewise known-vector mismatch at width {width}")
        require(file_hash(solution_path) == expected_hash, f"solution hash mismatch at width {width}")
        rhs_hash, observed_nonzeros = replay(indptr, indices, data, solution, width)
        require(observed_nonzeros == expected_nonzeros, f"prefix nonzero mismatch at width {width}")
        external = record["telemetry"]["external_time"]
        require(record["status"] == "PASS", f"stage status drift at width {width}")
        require(record["driver"]["replay_mismatches"] == 0 and record["driver"]["known_solution_mismatches"] == 0, f"producer replay drift at width {width}")
        require(0 < int(record["driver"]["last_null_coordinate"]) < 181, f"zero/invalid last null coordinate at width {width}")
        require(external["real_seconds"] <= wall_cap and external["maximum_rss_bytes"] <= rss_cap and external["process_swaps"] == 0, f"resource gate drift at width {width}")
        stage_audits.append({
            "columns": width,
            "coefficient_nonzeros": observed_nonzeros,
            "coordinatewise_solution_matches_formula": True,
            "solution_sha256": expected_hash,
            "independent_rhs_sha256": rhs_hash,
            "all_rows_replayed": len(indptr) - 1,
            "resource_gate": external,
        })
    final_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    wall = time.perf_counter() - started
    rss = max_rss_bytes()
    require(wall <= 120.0 and rss <= 512_000_000 and final_swaps - initial_swaps == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-independent-audit.v1",
        "status": "PASS_INDEPENDENT_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_REPLAY",
        "bound_hashes": observed_hashes,
        "csr_checks": {"rows": 85651, "columns": 35881, "nonzeros": 1354540, "ordered_rows": True, "nonzero_residues_mod181": True},
        "stage_audits": stage_audits,
        "source_boundary": source_boundary,
        "resources": {"wall_seconds": wall, "maximum_rss_bytes": rss, "process_swap_delta": final_swaps - initial_swaps, "wall_cap_seconds": 120.0, "rss_cap_bytes": 512000000},
        "declarations": {"producer_not_imported_or_executed": True, "linbox_not_called": True, "target_rhs_not_read": True, "third_candidate_not_read": True, "no_target_membership_test": True, "no_mod181_squared": True},
        "claim_boundary": "This audit independently certifies artifact integrity, the deterministic synthetic vector, four all-row matrix-vector replays, registered resource compliance, and target-exclusion source boundaries. It does not independently reimplement sparse echelonization and proves no target membership, QQ identity, p-adic digit, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
