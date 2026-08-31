#!/usr/bin/env python3
"""Audit the fixed-p181 Dixon preregistration and amendment before code exists.

This audit is deliberately algebra-free beyond reading the already-certified
modular artifact.  It binds the historical files, legacy hash domains,
dimensions, exact terminal modulus, and absence of the prospective Phase-I
outputs.  A PASS says only that implementation may now be written against a
determinate specification.
"""

from __future__ import annotations

import hashlib
import json
import resource
import struct
import sys
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
ORIGINAL = CAMPAIGN / "research" / (
    "THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION.md"
)
AMENDMENT = CAMPAIGN / "research" / (
    "THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_"
    "PREREGISTRATION_AMENDMENT_01.md"
)
PASS_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-dixon-p181-"
    "preregistration-amendment-01-audit.json"
)
FAIL_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-dixon-p181-"
    "preregistration-amendment-01-audit-failed.json"
)

ORIGINAL_SHA256 = (
    "dcba29bf2b3396fcbfd2999aad09a363c2fc852e4fb04c142cb1e1636c5ad6cc"
)

BOUND_FILES = {
    "scripts/certify_j2_secant_r10_third_colon_identity_sparse_macaulay.py": (
        "c0e1557c1a18d85af997e24c739d799d58c7d0b655d0662a0215f30e9b42ae74"
    ),
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json": (
        "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.json": (
        "f04bc461e8b15c012c229d1de13eb940316bad35914f12a34ab3fc112b29f14c"
    ),
    "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md": (
        "b203a118b302c50394a0188501e32d12cc077c85fca2b1513bed770f59a112f8"
    ),
    "scripts/normalize_j2_secant_r10_third_colon_koszul_p197_common_minor.py": (
        "fdbed62134385b5412474cd40e70e25a69eea9c5284a6a06dc99ecc121c4d57e"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization.json": (
        "3c2f2ac3b2a0c98bb279e90a1fffe8aea68f8c8c4db85e15ced673d50648946e"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization-independent-audit.json": (
        "674c2757e3dc0f4fdc51e3d4c889a742cac192e74322cc1b5ece70d72ec55ad4"
    ),
    "scripts/census_j2_secant_r10_third_colon_koszul_p197_common_minor_m70.py": (
        "6c09d24f9ef3962b1d677c38b34521be20fb4fb3f13dd34c12f270920beccb44"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-m70-census.json": (
        "7bb84b8e56df2e68fc4989cf22fc538d8660a5888d7ed0a6eac692512e69367c"
    ),
    "research/THIRD_COLON_RESIDUAL_114_QUOTIENT_SCOUT_PREREGISTRATION.md": (
        "112fb4ea3de68c84459422903e0c6f3c4c2902d364b13639f130c2a7f6cebf22"
    ),
    "scripts/scout_j2_secant_r10_third_colon_residual_114_quotient.py": (
        "607706e89e25990ed3ed1bdd5f7d9a972c824b0bff62a33035789860f75f3b81"
    ),
    "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json": (
        "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-scout.json": (
        "652af633649c32af3322b9405eac8d6e60fdaba5668817de6a11330782bc752a"
    ),
    "scripts/audit_j2_secant_r10_third_colon_residual_114_quotient_independent.py": (
        "81ad24d01ae70a0ca2731259753d99a429bd48ae288e77105120dd800009396d"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit.json": (
        "7eba0e65e40abd7eea0065ecd84c3803237fa9cc5c51391f3202b4d300b7185a"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit-external-telemetry.json": (
        "831c4ce5bcd6fdb0451209db1a8b0cbafabeec3e605c3235836c09cd42dac91e"
    ),
    "research/THIRD_COLON_RESIDUAL_114_TWO_PRIME_EXACT_CHART_EXTENSION_PREREGISTRATION.md": (
        "cc01cb96c1738316100bc46eab2c5ce5c8e23402da7b95d2483f0fab80f0ac10"
    ),
    "scripts/produce_j2_secant_r10_third_colon_residual_114_two_prime_exact_chart.py": (
        "7f469224f15b09419c7d092f4a84600ec1532f9e27711454a72e774f118c2f5d"
    ),
    "scripts/run_j2_secant_r10_third_colon_residual_114_two_prime_exact_chart_gated.py": (
        "7fd2f5f21045e8eb7434074057707d489085612b8941b977b1c31581148b3229"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart-failed.json": (
        "1d7f334e55c1229280e2b49e17a22ec74f578dde3ef6144745a81c6884ae9a37"
    ),
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart-external-telemetry.json": (
        "5770d7cc1cd71559bd754951937ff89a664950c25029a2088329cbef3f286d0b"
    ),
}

LEGACY_HASHES = {
    "pivot_unknown_indices": (
        "1da29807a38b0f9eceaf8606b120ea61e0a24605e959f7f2f88e4ed9bb073e1d"
    ),
    "free_unknown_indices": (
        "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1"
    ),
    "coordinate_vector": (
        "9932deed637ea317b4483cad9366e1fd1455be7453bc74a64ce78f04c4f57919"
    ),
}

INTERNAL_HASHES = {
    "row_descriptor_sha256": (
        "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
    ),
    "monomial_stream_sha256": (
        "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614"
    ),
    "generator_stream_sha256": (
        "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
    ),
    "target_sha256": (
        "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e"
    ),
}

TIME_FILE = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.time.txt"
)
TIME_FILE_SHA256 = (
    "67e37fb4b7a8cf22a8f9a37c2757341e9324e9277783728739178ce7babab92d"
)

PROSPECTIVE_PATHS = [
    CAMPAIGN / "receipts" / (
        "hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1.json"
    ),
    CAMPAIGN / "artifacts" / (
        "j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v1"
    ),
    CAMPAIGN / "receipts" / (
        "hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v1.json"
    ),
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compact_json_hash(values: list[int]) -> str:
    payload = json.dumps(
        values, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    return sha256_bytes(payload)


def u32_payload_hash(values: list[int]) -> str:
    return sha256_bytes(b"".join(struct.pack("<I", value) for value in values))


def write_exclusive_json(path: Path, payload: dict[str, object]) -> None:
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()


def run_audit() -> dict[str, object]:
    started = time.perf_counter()

    require(sha256_file(ORIGINAL) == ORIGINAL_SHA256, "original preregistration drift")
    amendment_hash = sha256_file(AMENDMENT)
    amendment_text = AMENDMENT.read_text(encoding="utf-8")
    required_phrases = [
        "legacy compact-JSON hashes",
        "HC4DXN01",
        "pivot_tail_columns",
        "created_before_preprocessing=true",
        "same-filesystem bundle",
        "Each child receives its **own** `/usr/bin/time -l` capture",
        "Legendre's continued-fraction criterion",
        "producer_core_digit_seconds",
    ]
    missing_phrases = [phrase for phrase in required_phrases if phrase not in amendment_text]
    require(not missing_phrases, f"amendment clauses missing: {missing_phrases}")

    bound_results = {}
    for relative, expected in BOUND_FILES.items():
        path = CAMPAIGN / relative
        require(path.is_file(), f"bound file missing: {relative}")
        observed = sha256_file(path)
        require(observed == expected, f"bound file drift: {relative}")
        bound_results[relative] = {
            "sha256": observed,
            "byte_count": path.stat().st_size,
        }

    primary_artifact_path = CAMPAIGN / (
        "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
    )
    primary_receipt_path = CAMPAIGN / (
        "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
    )
    artifact = json.loads(primary_artifact_path.read_text(encoding="utf-8"))
    receipt = json.loads(primary_receipt_path.read_text(encoding="utf-8"))

    pivots = list(map(int, artifact["pivot_unknown_indices"]))
    free = list(map(int, artifact["free_unknown_indices"]))
    vector = list(map(int, artifact["coordinate_vector"]))
    require(len(pivots) == 35_881, "pivot length changed")
    require(len(free) == 2_167, "free length changed")
    require(len(vector) == 38_048, "coordinate vector length changed")
    require(not (set(pivots) & set(free)), "C_piv and F overlap")
    require(sorted(pivots + free) == list(range(38_048)), "C_piv/F coverage changed")
    require(all(vector[index] == 0 for index in free), "x_F is not literal zero")
    require(all(0 <= value < 181 for value in vector), "p181 vector left residue range")

    legacy_results = {}
    for key, values in [
        ("pivot_unknown_indices", pivots),
        ("free_unknown_indices", free),
        ("coordinate_vector", vector),
    ]:
        compact_hash = compact_json_hash(values)
        require(compact_hash == LEGACY_HASHES[key], f"legacy hash drift: {key}")
        if key == "coordinate_vector":
            binary_hash = sha256_bytes(bytes(values))
            binary_encoding = "u8 little-endian payload"
        else:
            binary_hash = u32_payload_hash(values)
            binary_encoding = "u32 little-endian payload"
        require(binary_hash != compact_hash, f"hash domains did not separate: {key}")
        legacy_results[key] = {
            "length": len(values),
            "legacy_compact_json_sha256": compact_hash,
            "binary_payload_encoding": binary_encoding,
            "binary_payload_sha256": binary_hash,
            "hash_domains_distinct": True,
        }

    for key, expected in INTERNAL_HASHES.items():
        require(artifact[key] == expected, f"internal algebra hash drift: {key}")

    dimensions = receipt["dimensions"]
    expected_dimensions = {
        "monomial_equations": 85_651,
        "unknown_multiplier_coordinates": 38_048,
        "matrix_nonzeros": 1_473_071,
        "target_terms": 486,
        "total_generators": 19,
        "normal_cubic_generators": 17,
    }
    require(dimensions == expected_dimensions, "primary dimensions changed")
    require(receipt["status"] == "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY", "primary status changed")

    terminal_modulus = 181**8
    require(terminal_modulus == 1_151_936_657_823_500_641, "181^8 decimal changed")
    require(terminal_modulus.bit_length() == 60, "181^8 bit length changed")
    require(sha256_file(TIME_FILE) == TIME_FILE_SHA256, "historical time file drift")

    premature = [str(path.relative_to(CAMPAIGN)) for path in PROSPECTIVE_PATHS if path.exists()]
    require(not premature, f"prospective output already exists: {premature}")

    finished = time.perf_counter()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "schema": (
            "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
            "preregistration-amendment-audit.v1"
        ),
        "status": "PASS_PREIMPLEMENTATION_SPEC_AMENDMENT_AUDIT",
        "documents": {
            "original": {
                "path": str(ORIGINAL.relative_to(CAMPAIGN)),
                "sha256": ORIGINAL_SHA256,
            },
            "amendment": {
                "path": str(AMENDMENT.relative_to(CAMPAIGN)),
                "sha256": amendment_hash,
            },
        },
        "bound_file_count": len(bound_results),
        "bound_files": bound_results,
        "legacy_hash_domain_checks": legacy_results,
        "internal_algebra_hashes": INTERNAL_HASHES,
        "dimensions": expected_dimensions
        | {"C_piv": len(pivots), "F": len(free)},
        "terminal_modulus": {
            "expression": "181^8",
            "decimal": str(terminal_modulus),
            "bit_length": terminal_modulus.bit_length(),
        },
        "historical_time_file": {
            "path": str(TIME_FILE.relative_to(CAMPAIGN)),
            "sha256": TIME_FILE_SHA256,
        },
        "prospective_output_absence": {
            "checked_paths": [str(path.relative_to(CAMPAIGN)) for path in PROSPECTIVE_PATHS],
            "existing_paths": premature,
            "no_registered_p2_output_observed": True,
        },
        "resources": {
            "wall_seconds": finished - started,
            "maximum_rss_native": usage.ru_maxrss,
        },
        "source": {
            "path": str(Path(__file__).resolve().relative_to(CAMPAIGN)),
            "sha256": sha256_file(Path(__file__).resolve()),
            "python": sys.version,
        },
        "claim_boundary": (
            "This PASS proves only that the original preregistration plus its "
            "pre-p2 amendment is implementation-determinate against the bound "
            "live files. It does not execute preprocessing or factorization, "
            "compute a Dixon digit, prove a p-adic or QQ identity, establish "
            "ideal membership, compute a colon or saturation, close the "
            "secant chart, or establish HC4."
        ),
    }


def main() -> int:
    try:
        payload = run_audit()
        write_exclusive_json(PASS_RECEIPT, payload)
        print(json.dumps({"status": payload["status"], "receipt": str(PASS_RECEIPT)}))
        return 0
    except Exception as exc:  # fail closed with a retained diagnostic
        payload = {
            "schema": (
                "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
                "preregistration-amendment-audit-failure.v1"
            ),
            "status": "FAIL_PREIMPLEMENTATION_SPEC_AMENDMENT_AUDIT",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "original_preregistration_sha256_expected": ORIGINAL_SHA256,
            "claim_boundary": "This failure licenses no Dixon implementation or arithmetic.",
        }
        try:
            write_exclusive_json(FAIL_RECEIPT, payload)
        except FileExistsError:
            pass
        print(json.dumps(payload), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
