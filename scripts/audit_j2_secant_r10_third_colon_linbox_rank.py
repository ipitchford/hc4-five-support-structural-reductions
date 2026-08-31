#!/usr/bin/env sage-python
"""Audit the exactness and consistency logic of the p=103 LinBox rank receipt.

The benchmark receipt itself freezes the two computed ranks.  This independent
audit checks its problem hashes and dimensions, inspects the Sage 10.9 Cython
wrapper used for sparse modular rank, and verifies that the wrapper calls
``GaussDomain_Modular_uint64.InPlaceLinearPivoting`` rather than a black-box
or Wiedemann rank estimator.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import sage.matrix.matrix_modn_sparse as sparse_module
from sage.env import SAGE_VERSION


EXPECTED_RANK = 35_880
EXPECTED_NULLITY = 2_167
EXPECTED_ACTIVE_COLUMNS = 38_047
EXPECTED_ACTIVE_ROWS = 85_638
EXPECTED_PRODUCER_SHA256 = "79db511cce6b38c589264d6df8f4c54b12f6e979edf938bc8e1293fa38628b67"
EXPECTED_STRUCTURE_SHA256 = "3fe0f2403b792313ec167f9599eaa8fe00c24efb6741caed46e179c4a9b34c00"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    receipt_path = (
        campaign
        / "receipts/hsop-j2-secant-r10-third-colon-linbox-rank-p103.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    source_path = Path(
        "/Users/admin/.local/share/o01d0-passagemath/lib/python3.14/"
        "site-packages/sage/matrix/matrix_modn_sparse_linbox.pyx"
    )
    if not source_path.is_file():
        raise FileNotFoundError("the pinned Sage 10.9 LinBox wrapper source is missing")
    source = source_path.read_text(encoding="utf-8")
    match = re.search(
        r"def _rank_det_linbox\(Matrix_modn_sparse self\):(?P<body>.*?)\n\s*return <long> A_rank, self\.base_ring\(\)\(A_det\)",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("could not isolate _rank_det_linbox in the Sage source")
    body = match.group("body")
    backend_checks = {
        "sage_version_is_10_9": SAGE_VERSION == "10.9",
        "uses_modular_uint64_field": "givaro.Modular_uint64" in body,
        "uses_sparse_modular_matrix": "SparseMatrix_Modular_uint64" in body,
        "uses_gauss_domain": "GaussDomain_Modular_uint64" in body,
        "calls_in_place_linear_pivoting": "dom.InPlaceLinearPivoting" in body,
        "does_not_request_blackbox_method": "METHOD_BLACKBOX" not in body,
        "does_not_request_wiedemann_method": "METHOD_WIEDEMANN" not in body,
    }
    receipt_checks = {
        "schema_match": receipt.get("schema")
        == "hc4.decimic-j2-secant-r10-third-colon-linbox-rank-benchmark.v1",
        "status_match": receipt.get("status")
        == "PASS_LINBOX_MODULAR_MEMBERSHIP_RANK_EQUALITY",
        "characteristic_is_103": receipt.get("characteristic") == 103,
        "coefficient_rank_match": receipt.get("coefficient_rank") == EXPECTED_RANK,
        "augmented_rank_match": receipt.get("augmented_rank") == EXPECTED_RANK,
        "ranks_equal": receipt.get("ranks_equal") is True,
        "active_column_count_match": receipt["component_pruning"]["column_count"]
        == EXPECTED_ACTIVE_COLUMNS,
        "active_row_count_match": receipt["component_pruning"]["row_count"]
        == EXPECTED_ACTIVE_ROWS,
        "nullity_identity": EXPECTED_ACTIVE_COLUMNS - EXPECTED_RANK
        == receipt.get("nullity_after_isolated_coordinate_removal")
        == EXPECTED_NULLITY,
        "isolated_coordinate_match": receipt["component_pruning"]["isolated_unknown"]
        == 2220,
        "isolated_row_count_match": receipt["component_pruning"]["isolated_row_count"]
        == 13,
        "producer_hash_match": receipt["inputs"]["producer_sha256"]
        == EXPECTED_PRODUCER_SHA256,
        "structure_hash_match": receipt["inputs"]["structure_receipt_sha256"]
        == EXPECTED_STRUCTURE_SHA256,
    }
    passed = all(backend_checks.values()) and all(receipt_checks.values())
    binary_path = Path(sparse_module.__file__).resolve()
    result = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-linbox-rank-audit.v1",
        "status": (
            "PASS_EXACT_MODULAR_MEMBERSHIP_RANK_AUDIT"
            if passed
            else "FAIL_MODULAR_MEMBERSHIP_RANK_AUDIT"
        ),
        "assurance": "independent receipt consistency and Sage LinBox wrapper source audit",
        "characteristic": 103,
        "mathematical_decision": {
            "coefficient_rank": receipt.get("coefficient_rank"),
            "augmented_rank": receipt.get("augmented_rank"),
            "ranks_equal": receipt.get("ranks_equal"),
            "conclusion": (
                "M*h3 belongs to the image of the displayed p=103 Macaulay map"
                if passed
                else "no audited conclusion"
            ),
            "logic": "A*x=b is consistent over a field iff rank(A)=rank([A|b]).",
        },
        "receipt_checks": receipt_checks,
        "backend_checks": backend_checks,
        "backend_audit": {
            "sage_version": SAGE_VERSION,
            "matrix_modn_sparse_binary_path": str(binary_path),
            "matrix_modn_sparse_binary_sha256": sha256(binary_path),
            "reference_wrapper_source_path": str(source_path),
            "reference_wrapper_source_sha256": sha256(source_path),
            "isolated_function_body_sha256": hashlib.sha256(
                body.encode("utf-8")
            ).hexdigest(),
            "dispatch": "GaussDomain_Modular_uint64.InPlaceLinearPivoting",
            "rank_algorithm_class": "exact sparse modular Gaussian elimination",
        },
        "input": {
            "path": str(receipt_path.relative_to(campaign)),
            "sha256": sha256(receipt_path),
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
        },
        "claim_boundary": (
            "A PASS audits exact modular membership at p=103 through rank equality. "
            "It does not recover an explicit multiplier vector, prove a QQ identity, "
            "compute a colon or saturation, close the secant chart, or establish HC4."
        ),
    }
    output_path = (
        campaign
        / "receipts/hsop-j2-secant-r10-third-colon-linbox-rank-p103-independent-audit.json"
    )
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
