#!/usr/bin/env python3
"""Audit the append-only failure-magic clarification before implementation."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
DOCUMENTS = {
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION.md": (
        "dcba29bf2b3396fcbfd2999aad09a363c2fc852e4fb04c142cb1e1636c5ad6cc"
    ),
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_01.md": (
        "5bff2bd3844744f854c2757aee4b8bf09d227ae487ba1b43f55682a009f5d08c"
    ),
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_02.md": (
        "dd07f5e0e6ca139383905bedae9b382304bcf2cf52ce74d0c496e30e32dc5def"
    ),
}
PROSPECTIVE = [
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1.json",
    "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v1",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v1.json",
]
OUTPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-dixon-p181-"
    "preregistration-amendment-02-audit.json"
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for relative, expected in DOCUMENTS.items():
        if file_hash(CAMPAIGN / relative) != expected:
            raise ValueError(f"document drift: {relative}")
    amendment = (CAMPAIGN / next(reversed(DOCUMENTS))).read_text(encoding="utf-8")
    magic = b"HC4FAIL1"
    if len(magic) != 8 or "HC4FAIL1" not in amendment:
        raise ValueError("failure magic is not exactly eight bytes")
    pass_stream = magic + struct.pack("<I", 0)
    if len(pass_stream) != 12:
        raise AssertionError("PASS failure stream is not 12 bytes")
    existing = [relative for relative in PROSPECTIVE if (CAMPAIGN / relative).exists()]
    if existing:
        raise ValueError(f"prospective output already exists: {existing}")
    payload = {
        "schema": (
            "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
            "preregistration-amendment-02-audit.v1"
        ),
        "status": "PASS_PREIMPLEMENTATION_AMENDMENT_02_AUDIT",
        "document_hashes": DOCUMENTS,
        "failure_magic_ascii": magic.decode("ascii"),
        "failure_magic_byte_count": len(magic),
        "pass_failure_stream_hex": pass_stream.hex(),
        "pass_failure_stream_byte_count": len(pass_stream),
        "prospective_paths_checked": PROSPECTIVE,
        "prospective_paths_existing": existing,
        "source": {
            "path": str(Path(__file__).resolve().relative_to(CAMPAIGN)),
            "sha256": file_hash(Path(__file__).resolve()),
        },
        "claim_boundary": (
            "This PASS verifies only the append-only failure-stream magic "
            "clarification before implementation. It computes no algebra, "
            "Dixon digit, p-adic or QQ identity, colon, saturation, secant "
            "closure, nullcone containment, or HC4 result."
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
