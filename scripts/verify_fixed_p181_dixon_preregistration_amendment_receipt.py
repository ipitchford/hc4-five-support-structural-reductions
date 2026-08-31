#!/usr/bin/env python3
"""Second non-importing verification of the Dixon amendment audit receipt."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
SOURCE_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-dixon-p181-"
    "preregistration-amendment-01-audit.json"
)
OUTPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-dixon-p181-"
    "preregistration-amendment-01-second-verification.json"
)
ORIGINAL = CAMPAIGN / "research" / (
    "THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION.md"
)
AMENDMENT = CAMPAIGN / "research" / (
    "THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_"
    "PREREGISTRATION_AMENDMENT_01.md"
)
PRIMARY_ARTIFACT = CAMPAIGN / "artifacts" / (
    "j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
)
PRIMARY_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compact_hash(values: list[int]) -> str:
    return digest(
        json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode(
            "ascii"
        )
    )


def main() -> int:
    source_bytes = SOURCE_RECEIPT.read_bytes()
    source = json.loads(source_bytes)
    require(
        source["status"] == "PASS_PREIMPLEMENTATION_SPEC_AMENDMENT_AUDIT",
        "source audit is not PASS",
    )

    original_text = ORIGINAL.read_text(encoding="utf-8")
    amendment_text = AMENDMENT.read_text(encoding="utf-8")
    documents = source["documents"]
    require(file_digest(ORIGINAL) == documents["original"]["sha256"], "original drift")
    require(file_digest(AMENDMENT) == documents["amendment"]["sha256"], "amendment drift")
    require(documents["original"]["sha256"] in amendment_text, "amendment lost original binding")

    checked_files = {}
    for relative, record in source["bound_files"].items():
        require(relative in original_text, f"path not text-bound: {relative}")
        require(record["sha256"] in original_text, f"hash not text-bound: {relative}")
        path = CAMPAIGN / relative
        observed = file_digest(path)
        require(observed == record["sha256"], f"live drift: {relative}")
        require(path.stat().st_size == record["byte_count"], f"size drift: {relative}")
        checked_files[relative] = observed
    require(len(checked_files) == 21, "expected 21 independently checked files")

    artifact = json.loads(PRIMARY_ARTIFACT.read_text(encoding="utf-8"))
    primary_receipt = json.loads(PRIMARY_RECEIPT.read_text(encoding="utf-8"))
    arrays = {
        "pivot_unknown_indices": list(map(int, artifact["pivot_unknown_indices"])),
        "free_unknown_indices": list(map(int, artifact["free_unknown_indices"])),
        "coordinate_vector": list(map(int, artifact["coordinate_vector"])),
    }
    independently_recomputed_hashes = {}
    for name, values in arrays.items():
        observed = compact_hash(values)
        expected = source["legacy_hash_domain_checks"][name][
            "legacy_compact_json_sha256"
        ]
        require(observed == expected, f"legacy compact hash mismatch: {name}")
        if name == "coordinate_vector":
            raw = bytes(values)
        else:
            raw = b"".join(struct.pack("<I", value) for value in values)
        raw_hash = digest(raw)
        require(raw_hash != observed, f"binary domain collapsed: {name}")
        require(
            raw_hash
            == source["legacy_hash_domain_checks"][name]["binary_payload_sha256"],
            f"binary payload mismatch: {name}",
        )
        independently_recomputed_hashes[name] = {
            "legacy_compact_json_sha256": observed,
            "binary_payload_sha256": raw_hash,
        }

    pivots = arrays["pivot_unknown_indices"]
    free = arrays["free_unknown_indices"]
    vector = arrays["coordinate_vector"]
    require(len(pivots) == 35_881 and len(free) == 2_167, "gauge lengths changed")
    require(sorted(pivots + free) == list(range(38_048)), "gauge coverage changed")
    require(not set(pivots).intersection(free), "gauge overlap")
    require(all(vector[index] == 0 for index in free), "free coordinate became nonzero")

    expected_dimensions = source["dimensions"]
    for key, value in primary_receipt["dimensions"].items():
        require(expected_dimensions[key] == value, f"dimension mismatch: {key}")
    require(expected_dimensions["C_piv"] == len(pivots), "C_piv dimension mismatch")
    require(expected_dimensions["F"] == len(free), "F dimension mismatch")

    modulus = pow(181, 8)
    require(str(modulus) == source["terminal_modulus"]["decimal"], "modulus mismatch")
    require(modulus.bit_length() == source["terminal_modulus"]["bit_length"], "bit length mismatch")

    time_path = CAMPAIGN / source["historical_time_file"]["path"]
    require(
        file_digest(time_path) == source["historical_time_file"]["sha256"],
        "historical telemetry drift",
    )

    existing = [
        relative
        for relative in source["prospective_output_absence"]["checked_paths"]
        if (CAMPAIGN / relative).exists()
    ]
    require(not existing, f"prospective output appeared before verification: {existing}")

    payload = {
        "schema": (
            "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
            "preregistration-amendment-second-verification.v1"
        ),
        "status": "PASS_SECOND_IMPLEMENTATION_SPEC_AMENDMENT_VERIFICATION",
        "source_receipt": {
            "path": str(SOURCE_RECEIPT.relative_to(CAMPAIGN)),
            "sha256": digest(source_bytes),
        },
        "documents": {
            "original_sha256": file_digest(ORIGINAL),
            "amendment_sha256": file_digest(AMENDMENT),
        },
        "checked_bound_file_count": len(checked_files),
        "checked_bound_file_hashes": checked_files,
        "independently_recomputed_hash_domains": independently_recomputed_hashes,
        "gauge_partition": {
            "pivot_count": len(pivots),
            "free_count": len(free),
            "coverage": True,
            "free_coordinates_zero": True,
        },
        "dimensions": expected_dimensions,
        "terminal_modulus": str(modulus),
        "prospective_outputs_absent": True,
        "source": {
            "path": str(Path(__file__).resolve().relative_to(CAMPAIGN)),
            "sha256": file_digest(Path(__file__).resolve()),
            "python": sys.version,
        },
        "claim_boundary": (
            "This separate implementation verifies only the preimplementation "
            "specification audit. It does not execute the Dixon pilot or prove "
            "any p-adic, QQ, ideal, colon, saturation, secant, nullcone, or HC4 "
            "statement."
        ),
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
