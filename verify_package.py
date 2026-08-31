#!/usr/bin/env python3
"""Fail-closed integrity and semantic verifier for the HC4 candidate release."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SELECTED = [46, 47, 57, 66, 68, 102, 155, 547, 763, 965, 966, 1261, 1269, 1499, 1699, 1711]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(relative: str) -> dict:
    path = ROOT / relative
    require(path.is_file(), f"missing {relative}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FAIL: invalid JSON {relative}: {exc}") from exc


def verify_manifest() -> None:
    manifest = ROOT / "MANIFEST.sha256"
    if not manifest.exists():
        return
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError as exc:
            raise SystemExit(f"FAIL: malformed manifest line {line_number}") from exc
        path = ROOT / relative
        require(path.is_file(), f"manifest target missing: {relative}")
        require(sha256(path) == expected, f"manifest hash mismatch: {relative}")


def verify_core() -> None:
    claims = load("CLAIMS.json")
    require(claims.get("schema") == "evidence-press/claims/v1", "claim schema drift")
    require([claim.get("id") for claim in claims.get("claims", [])] == ["C1", "C2", "C3", "C4", "C5", "C6", "C7"], "claim IDs drift")

    required_statuses = {
        "receipts/five-support-theorem-audit.json": "PASS",
        "receipts/nullcone-tangent-all-31-generators.json": "PASS_EXACT_TANGENT_ALL_31_GENERATORS_RADICAL_CONTAINMENT",
        "receipts/hsop-j2-secant-r10-colon-identity-qq-reconstruction.json": "PASS_EXACT_QQ_COLON_IDENTITY",
        "receipts/hsop-j2-secant-r10-second-colon-identity-qq-reconstruction.json": "PASS_EXACT_QQ_SECOND_COLON_IDENTITY",
        "receipts/hsop-j2-secant-r10-p181-target-exact-polynomial-identity-audit.json": "PASS_INDEPENDENT_P181_TARGET_EXACT_POLYNOMIAL_IDENTITY",
        "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json": "PASS_EXACT_2053_KOSZUL_SYZYGIES_INDEPENDENT_OVER_QQ",
        "receipts/hsop-j2-secant-r10-residual-114-p181-72digit-terminal.json": "PASS_P181_72DIGIT_EXACT_RESIDUAL_114_RATIONAL_CHART",
        "receipts/hsop-j2-secant-r10-fourth-colon-p173-96digit-extension-independent-audit.json": "PASS_INDEPENDENT_P173_FOURTH_COLON_96DIGIT_LIFT_REPLAY",
    }
    for relative, expected in required_statuses.items():
        require(load(relative).get("status") == expected, f"status drift: {relative}")

    source = load("UPSTREAM_SOURCE.json")
    require(source.get("repository") == "https://github.com/royvanrijn/jacobian-research.git", "upstream repository drift")
    require(source.get("commit") == "3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9", "upstream commit drift")

    terminal_path = "receipts/hsop-j2-secant-r10-fourth-colon-c16-kernel-batch-terminal.json"
    terminal = load(terminal_path)
    require(terminal.get("status") == "PASS_FOURTH_COLON_C16_EXACT_RATIONAL_KERNEL_BATCH", "terminal status drift")
    require(terminal.get("selected_global_coordinates") == SELECTED, "selected-column drift")
    require(terminal.get("dimensions") == {"rows": 85688, "pivot_columns": 36587, "selected_free_columns": 16, "pivot_nonzeros": 1487624, "selected_source_nonzeros": 208}, "matrix dimensions drift")

    reconstruction = load("artifacts/fourth-colon-p173-c16-interface-v1/p4-reconstruction.json")
    checks = reconstruction.get("checks", {})
    require(reconstruction.get("status") == "PASS_FOURTH_COLON_P173_C16_EXACT_RATIONAL_KERNEL_BATCH", "reconstruction status drift")
    require(reconstruction.get("modulus") == 173 ** 4, "reconstruction modulus drift")
    require(checks.get("resolved_coordinates") == 36587 * 16, "resolved-coordinate count drift")
    require(checks.get("unresolved_coordinates") == 0, "unresolved rational coordinates")
    require(checks.get("p4_replay_mismatches") == 0, "p4 replay mismatch")
    require(checks.get("exact_replay_mismatches") == 0, "exact replay mismatch")
    require(checks.get("exact_nonzero_support_by_column") == [36] + [21] * 15, "support profile drift")

    candidates_path = ROOT / "artifacts/fourth-colon-p173-c16-interface-v1/rational-candidates.json"
    require(sha256(candidates_path) == terminal["p4_reconstruction"]["candidates_sha256"], "candidate hash drift")
    audit_path = ROOT / "receipts/hsop-j2-secant-r10-fourth-colon-c16-rational-syzygies-independent-audit.json"
    require(sha256(audit_path) == terminal["independent_direct_polynomial_audit"]["receipt_sha256"], "semantic-audit hash drift")
    audit = load(str(audit_path.relative_to(ROOT)))
    require(audit.get("checks", {}).get("polynomial_mismatches") == 0, "recorded polynomial mismatch")
    require(audit.get("checks", {}).get("residual_term_counts") == [0] * 16, "recorded residual term")

    pdf = ROOT / "paper.pdf"
    require(pdf.read_bytes()[:5] == b"%PDF-", "paper.pdf is not a PDF")
    verify_manifest()


def verify_semantic() -> None:
    script = ROOT / "scripts/audit_p173_fourth_colon_c16_rational_syzygies.py"
    candidates = ROOT / "artifacts/fourth-colon-p173-c16-interface-v1/rational-candidates.json"
    with tempfile.TemporaryDirectory(prefix="hc4-c16-audit-") as temporary:
        output = Path(temporary) / "audit.json"
        command = ["sage", "-python", str(script), "--candidates", str(candidates), "--output", str(output)]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if completed.returncode:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise SystemExit("FAIL: semantic C16 replay")
        result = json.loads(output.read_text(encoding="ascii"))
        require(result.get("checks", {}).get("polynomial_mismatches") == 0, "semantic C16 mismatch")
        print(result["status"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic-c16", action="store_true", help="run the Sage direct-polynomial replay")
    args = parser.parse_args()
    verify_core()
    print("PASS_RELEASE_VERIFICATION")
    if args.semantic_c16:
        verify_semantic()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
