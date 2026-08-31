#!/usr/bin/env -S sage -python
"""Independent byte-level and backend audit of the target-blind p181 rank PASS."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import struct
from pathlib import Path

import numpy as np
import scipy.sparse as sparse
import sage.matrix.matrix_modn_sparse as sparse_module
from sage.env import SAGE_VERSION


CAMPAIGN = Path(__file__).resolve().parents[1]
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-terminal-v2.json"
BENCHMARK = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/benchmark.json"
CSR = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr"
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-implementation-freeze-v2.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-v2-independent-audit.json"
EXPECTED = {
    "freeze_sha256": "2510d05c50ba745ab3d64bdb8bcd6fdcc971444c3ba344f1120b549d16bd3c48",
    "terminal_sha256": "7b3da03bd0325b8a64340c9195632b85b6df7e33efc428f330e1698ec202aba9",
    "benchmark_sha256": "6a28f331c768a2fba46a32acacf181897a9522ce01428c3f9e4e2ca6c50480b9",
    "csr_sha256": "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef",
    "rows": 85_651,
    "columns": 35_881,
    "nonzeros": 1_354_540,
    "prefixes": [4_096, 8_192, 16_384, 35_881],
    "matvec_hashes": [
        "5404a496c2668b61e3720198e8f00f0bb329cfff250a69f0f9e636d61cbd0447",
        "60ac686620ad86e851d744cbb216447ee2b87c3619a2c8283483cc8505050f0f",
        "262ca1484c903c296c06eb90ed01a0ce6ad397995356e6c7fcc5f2158d0665a5",
        "14ef77d44353f9414241e6328afe7ab1a35280dac855dd1dc2a861aec41b989b",
    ],
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_csr():
    payload = CSR.read_bytes()
    require(payload[:8] == b"HC4AC181", "CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (EXPECTED["rows"], EXPECTED["columns"], EXPECTED["nonzeros"]), "CSR header drift")
    offset = 32
    indptr = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=offset).astype(np.int64)
    offset += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=offset).astype(np.int64)
    offset += 4 * nonzeros
    data = np.frombuffer(payload, dtype=np.uint8, count=nonzeros, offset=offset).astype(np.int64)
    offset += nonzeros
    require(offset == len(payload), "CSR trailing or missing bytes")
    require(indptr[0] == 0 and indptr[-1] == nonzeros and np.all(indptr[1:] >= indptr[:-1]), "CSR offsets invalid")
    require(np.all(indices >= 0) and np.all(indices < columns), "CSR column out of range")
    require(np.all(data > 0) and np.all(data < 181), "CSR residue out of range")
    for row in range(rows):
        segment = indices[indptr[row]:indptr[row + 1]]
        require(len(segment) < 2 or np.all(segment[1:] > segment[:-1]), f"CSR row {row} not strictly ordered")
    return indptr, indices, data


def independent_matvec_hash(indptr, indices, data, width: int) -> str:
    mask = indices < width
    padded_mask = np.concatenate((mask.astype(np.int64), np.zeros(1, dtype=np.int64)))
    per_row = np.add.reduceat(padded_mask, indptr[:-1])
    # reduceat needs correction for empty rows; padding makes a terminal empty
    # row a valid zero-valued reduction start.
    per_row[indptr[1:] == indptr[:-1]] = 0
    prefix_indptr = np.empty_like(indptr)
    prefix_indptr[0] = 0
    np.cumsum(per_row, out=prefix_indptr[1:])
    prefix_indices = indices[mask]
    prefix_data = data[mask]
    matrix = sparse.csr_matrix((prefix_data, prefix_indices, prefix_indptr), shape=(EXPECTED["rows"], width), dtype=np.int64)
    digest = hashlib.sha256()
    columns = np.arange(1, width + 1, dtype=np.int64)
    for repetition in range(16):
        probe = (((repetition + 1) * columns + 17) % 181).astype(np.int64)
        product = np.asarray(matrix.dot(probe) % 181, dtype=np.uint8)
        digest.update(product.tobytes())
    return digest.hexdigest()


def audit_import_boundary(paths: list[Path]) -> dict[str, list[str]]:
    result = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        forbidden = [name for name in imports if "third_colon_identity_sparse_macaulay" in name or "dixon" in name]
        require(not forbidden, f"forbidden target/Dixon import in {path.name}: {forbidden}")
        result[str(path.relative_to(CAMPAIGN))] = imports
    return result


def audit_backend() -> dict[str, object]:
    source_path = Path("/Users/admin/.local/share/o01d0-passagemath/lib/python3.14/site-packages/sage/matrix/matrix_modn_sparse_linbox.pyx")
    require(source_path.is_file(), "pinned Sage LinBox wrapper source missing")
    source = source_path.read_text(encoding="utf-8")
    match = re.search(r"def _rank_det_linbox\(Matrix_modn_sparse self\):(?P<body>.*?)\n\s*return <long> A_rank, self\.base_ring\(\)\(A_det\)", source, flags=re.DOTALL)
    require(match is not None, "could not isolate Sage LinBox rank wrapper")
    body = match.group("body")
    checks = {
        "sage_version_10_9": SAGE_VERSION == "10.9",
        "uses_modular_uint64": "givaro.Modular_uint64" in body,
        "uses_sparse_modular_matrix": "SparseMatrix_Modular_uint64" in body,
        "uses_gauss_domain": "GaussDomain_Modular_uint64" in body,
        "calls_in_place_linear_pivoting": "dom.InPlaceLinearPivoting" in body,
        "does_not_request_blackbox": "METHOD_BLACKBOX" not in body,
        "does_not_request_wiedemann": "METHOD_WIEDEMANN" not in body,
    }
    require(all(checks.values()), "exact backend audit failed")
    binary = Path(sparse_module.__file__).resolve()
    return {"checks": checks, "dispatch": "GaussDomain_Modular_uint64.InPlaceLinearPivoting", "rank_algorithm_class": "exact sparse modular Gaussian elimination", "wrapper_source_sha256": file_hash(source_path), "binary_sha256": file_hash(binary)}


def main() -> int:
    require(not OUTPUT.exists(), "audit receipt already exists")
    observed_hashes = {"freeze_sha256": file_hash(FREEZE), "terminal_sha256": file_hash(TERMINAL), "benchmark_sha256": file_hash(BENCHMARK), "csr_sha256": file_hash(CSR)}
    for key, value in observed_hashes.items():
        require(value == EXPECTED[key], f"{key} drift")
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    require(terminal.get("status") == benchmark.get("status") == "PASS_ACTUAL_COEFFICIENT_LINBOX_FULL_COLUMN_RANK_SCALING", "PASS status drift")
    cases = benchmark["cases"]
    require([case["columns"] for case in cases] == EXPECTED["prefixes"], "prefix sequence drift")
    require(all(case["linbox_rank"] == case["columns"] and case["full_column_rank"] is True for case in cases), "rank result drift")
    telemetry = terminal["telemetry"]["external_time"]
    require(telemetry["real_seconds"] <= 600 and telemetry["maximum_rss_bytes"] <= 3_758_096_384 and telemetry["process_swaps"] == 0, "resource gate drift")
    require(all(benchmark["declarations"].values()) and all(terminal["declarations"].values()), "target-blind declaration drift")
    indptr, indices, data = read_csr()
    matvec = []
    for width, expected_hash in zip(EXPECTED["prefixes"], EXPECTED["matvec_hashes"], strict=True):
        observed = independent_matvec_hash(indptr, indices, data, width)
        require(observed == expected_hash, f"independent matvec hash mismatch at {width}")
        matvec.append({"columns": width, "sha256": observed})
    imports = audit_import_boundary([CAMPAIGN / "scripts/benchmark_p181_target_blind_linbox_rank.py", CAMPAIGN / "scripts/benchmark_p181_target_blind_linbox_rank_v2.py"])
    backend = audit_backend()
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-linbox-rank-audit.v2",
        "status": "PASS_INDEPENDENT_ACTUAL_COEFFICIENT_LINBOX_RANK_SCALING_AUDIT",
        "bound_hashes": observed_hashes,
        "csr_checks": {"rows": EXPECTED["rows"], "columns": EXPECTED["columns"], "nonzeros": EXPECTED["nonzeros"], "strictly_ordered_rows": True, "nonzero_residues_mod181": True},
        "independent_matvec_replays": matvec,
        "rank_results": [{"columns": case["columns"], "rank": case["linbox_rank"]} for case in cases],
        "resource_gate": telemetry,
        "backend_audit": backend,
        "import_boundary": imports,
        "declarations": {"no_rhs_read": True, "no_target_membership_test": True, "no_augmented_rank": True, "no_solve": True, "no_digit": True},
        "claim_boundary": "This audit confirms artifact integrity, independent matvec replay, registered resource compliance, and exact modular-rank backend dispatch. It does not independently recompute the four ranks and proves no target membership, QQ identity, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
