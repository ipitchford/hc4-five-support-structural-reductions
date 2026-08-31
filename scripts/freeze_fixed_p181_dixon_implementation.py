#!/usr/bin/env python3
"""Create the exclusive pre-Phase-I implementation freeze receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v3.json"
SCHEMA = "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-implementation-freeze.v3"

DOCUMENTS = {
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION.md": "dcba29bf2b3396fcbfd2999aad09a363c2fc852e4fb04c142cb1e1636c5ad6cc",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_01.md": "5bff2bd3844744f854c2757aee4b8bf09d227ae487ba1b43f55682a009f5d08c",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_02.md": "dd07f5e0e6ca139383905bedae9b382304bcf2cf52ce74d0c496e30e32dc5def",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_03.md": "2595d68aed6ed3e968f516386effdb09ede8c1f851bda717dc93f76cd8946b82",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_04.md": "194ebeca8c2270f6287ec7169424bc7a6ad11fe7f263137ffd78844dc9d36273",
}

ALGEBRA_AND_HISTORY = {
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1.json": "8b313ec2354c7afe21a041260a2dbc6bc6b167855a94b14fa21031c9538d1568",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1-failed-audit.json": "913c3ee41dd83084e7da570b468789dca351eb46fe259ff898f7c3152a078163",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v2.json": "710b5f768c1693dc79faf604b8581711cf6d277711acd84ac84206274525699d",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-phase1-v2-terminal.json": "859b47008f61569f77cab502fc46912ff22339144738604a8316f5973b759596",
    "scripts/certify_j2_secant_r10_third_colon_identity_sparse_macaulay.py": "c0e1557c1a18d85af997e24c739d799d58c7d0b655d0662a0215f30e9b42ae74",
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json": "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b",
    "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.json": "f04bc461e8b15c012c229d1de13eb940316bad35914f12a34ab3fc112b29f14c",
    "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md": "b203a118b302c50394a0188501e32d12cc077c85fca2b1513bed770f59a112f8",
    "scripts/normalize_j2_secant_r10_third_colon_koszul_p197_common_minor.py": "fdbed62134385b5412474cd40e70e25a69eea9c5284a6a06dc99ecc121c4d57e",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization.json": "3c2f2ac3b2a0c98bb279e90a1fffe8aea68f8c8c4db85e15ced673d50648946e",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization-independent-audit.json": "674c2757e3dc0f4fdc51e3d4c889a742cac192e74322cc1b5ece70d72ec55ad4",
    "scripts/census_j2_secant_r10_third_colon_koszul_p197_common_minor_m70.py": "6c09d24f9ef3962b1d677c38b34521be20fb4fb3f13dd34c12f270920beccb44",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-m70-census.json": "7bb84b8e56df2e68fc4989cf22fc538d8660a5888d7ed0a6eac692512e69367c",
    "research/THIRD_COLON_RESIDUAL_114_QUOTIENT_SCOUT_PREREGISTRATION.md": "112fb4ea3de68c84459422903e0c6f3c4c2902d364b13639f130c2a7f6cebf22",
    "scripts/scout_j2_secant_r10_third_colon_residual_114_quotient.py": "607706e89e25990ed3ed1bdd5f7d9a972c824b0bff62a33035789860f75f3b81",
    "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json": "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-scout.json": "652af633649c32af3322b9405eac8d6e60fdaba5668817de6a11330782bc752a",
    "scripts/audit_j2_secant_r10_third_colon_residual_114_quotient_independent.py": "81ad24d01ae70a0ca2731259753d99a429bd48ae288e77105120dd800009396d",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit.json": "7eba0e65e40abd7eea0065ecd84c3803237fa9cc5c51391f3202b4d300b7185a",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit-external-telemetry.json": "831c4ce5bcd6fdb0451209db1a8b0cbafabeec3e605c3235836c09cd42dac91e",
    "research/THIRD_COLON_RESIDUAL_114_TWO_PRIME_EXACT_CHART_EXTENSION_PREREGISTRATION.md": "cc01cb96c1738316100bc46eab2c5ce5c8e23402da7b95d2483f0fab80f0ac10",
    "scripts/produce_j2_secant_r10_third_colon_residual_114_two_prime_exact_chart.py": "7f469224f15b09419c7d092f4a84600ec1532f9e27711454a72e774f118c2f5d",
    "scripts/run_j2_secant_r10_third_colon_residual_114_two_prime_exact_chart_gated.py": "7fd2f5f21045e8eb7434074057707d489085612b8941b977b1c31581148b3229",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart-failed.json": "1d7f334e55c1229280e2b49e17a22ec74f578dde3ef6144745a81c6884ae9a37",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart-external-telemetry.json": "5770d7cc1cd71559bd754951937ff89a664950c25029a2088329cbef3f286d0b",
    "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.time.txt": "67e37fb4b7a8cf22a8f9a37c2757341e9324e9277783728739178ce7babab92d",
}

IMPLEMENTATION_SOURCES = [
    "scripts/preprocess_fixed_p181_dixon_integer_system.py",
    "scripts/factor_fixed_p181_dixon_coefficients.py",
    "scripts/produce_fixed_p181_dixon_8digit_pilot.py",
    "scripts/replay_fixed_p181_dixon_8digit_independent.py",
    "scripts/run_fixed_p181_dixon_8digit_gated.py",
    "scripts/fixed_p181_dixon_codec.py",
    "scripts/fixed_p181_dixon_rr.py",
    "scripts/freeze_fixed_p181_dixon_implementation.py",
]

PROSPECTIVE_PATHS = [
    "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v3",
    "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-telemetry-v3",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v3.json",
    "artifacts/j2-secant-r10-third-colon-dixon-p181-producer-8digit-bundle-v3",
    "artifacts/j2-secant-r10-third-colon-dixon-p181-independent-8digit-bundle-v3",
    "artifacts/j2-secant-r10-third-colon-dixon-p181-phase2-telemetry-v3",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-8digit-terminal-v3.json",
]

CANONICAL_PATHS = {
    "phase1_bundle": "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v3",
    "phase1_telemetry": "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-telemetry-v3",
    "factorization_freeze_index": "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v3.json",
    "producer_bundle": "artifacts/j2-secant-r10-third-colon-dixon-p181-producer-8digit-bundle-v3",
    "independent_bundle": "artifacts/j2-secant-r10-third-colon-dixon-p181-independent-8digit-bundle-v3",
    "phase2_telemetry": "artifacts/j2-secant-r10-third-colon-dixon-p181-phase2-telemetry-v3",
    "terminal_receipt": "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-8digit-terminal-v3.json",
    "quarantine_root": "artifacts/quarantine",
    "staging_root": "artifacts/staging",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_hashes(expected: dict[str, str]) -> None:
    for relative, digest in expected.items():
        path = CAMPAIGN / relative
        if not path.is_file() or file_hash(path) != digest:
            raise ValueError(f"bound file missing or changed: {relative}")


def tool_version(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    return (completed.stdout or completed.stderr).strip()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true", required=True)
    parser.parse_args()
    if OUTPUT.exists():
        raise FileExistsError(f"implementation freeze already exists: {OUTPUT}")
    check_hashes(DOCUMENTS)
    check_hashes(ALGEBRA_AND_HISTORY)
    sources = {}
    for relative in IMPLEMENTATION_SOURCES:
        path = CAMPAIGN / relative
        if not path.is_file():
            raise FileNotFoundError(f"implementation source absent: {relative}")
        sources[relative] = file_hash(path)
    existing = [relative for relative in PROSPECTIVE_PATHS if (CAMPAIGN / relative).exists()]
    if existing:
        raise ValueError(f"prospective output predates implementation freeze: {existing}")

    python_path = str(Path(sys.executable).resolve())
    sage_path_raw = shutil.which("sage")
    time_path = Path("/usr/bin/time")
    timeout_path_raw = shutil.which("gtimeout")
    if not sage_path_raw or not timeout_path_raw or not time_path.is_file():
        raise FileNotFoundError("required Sage, gtimeout, or /usr/bin/time is absent")
    sage_path = str(Path(sage_path_raw).resolve())
    timeout_path = str(Path(timeout_path_raw).resolve())

    payload = {
        "schema": SCHEMA,
        "status": "PASS_IMPLEMENTATION_FREEZE",
        "documents": DOCUMENTS,
        "algebra_and_historical_sources": ALGEBRA_AND_HISTORY,
        "implementation_sources": sources,
        "toolchain": {
            "python_executable": python_path,
            "python_version": sys.version,
            "sage_executable": sage_path,
            "sage_version": tool_version([sage_path, "--version"]),
            "external_time_executable": str(time_path),
            "gtimeout_executable": timeout_path,
            "gtimeout_version": tool_version([timeout_path, "--version"]).splitlines()[0],
        },
        "canonical_paths": CANONICAL_PATHS,
        "policy": {
            "characteristic": 181,
            "digits": 8,
            "terminal_modulus_decimal": "1151936657823500641",
            "phase1_total_wall_seconds_maximum": 600,
            "phase1_child_rss_bytes_maximum": 3_500_000_000,
            "phase2_process_wall_seconds_maximum": 180,
            "phase2_process_rss_bytes_maximum": 1_500_000_000,
            "literal_process_swaps_required": 0,
            "maximum_concurrent_algebra_children": 1,
            "rr_regression_maximum_modulus": 512,
            "rr_checkpoints": [4, 6, 8],
            "tail_digit_indices_zero_based": [4, 5, 6, 7],
        },
        "declarations": {
            "created_before_preprocessing": True,
            "no_arithmetic_modulo_181_squared": True,
            "no_p2_artifact_observed": True,
            "all_implementation_sources_complete_before_freeze": True,
        },
        "claim_boundary": (
            "This receipt freezes source, algebra, toolchain, paths, and gates before "
            "Phase I. It computes no coefficient factorization, Dixon digit, p-adic or "
            "QQ identity, ideal membership, colon, saturation, secant closure, nullcone "
            "containment, or HC4 result."
        ),
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=OUTPUT.parent, prefix=OUTPUT.name + ".tmp-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, OUTPUT)
        fsync_directory(OUTPUT.parent)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(json.dumps({"status": payload["status"], "path": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
