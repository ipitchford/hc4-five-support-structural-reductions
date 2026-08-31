#!/usr/bin/env python3
"""Independent exact replay of the p181 extension from 12 to 16 digits."""

from __future__ import annotations

import hashlib
import json
import resource
import time
from pathlib import Path

from audit_p181_third_colon_12digit_extension_independent import (
    CAMPAIGN,
    COLUMNS,
    INTEGRAL,
    P,
    ROWS,
    file_hash,
    matvec,
    read_integral,
    reconstruct,
    require,
)


ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-16digit-extension-v1"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-16digit-extension.json"
X12 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-12digit-extension-v1/X_mod_181_power_12.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-16digit-extension-independent-audit.json"


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "16-digit audit already exists")
    producer = json.loads((ARTIFACT / "extension.json").read_text(encoding="utf-8"))
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    require(producer.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_16DIGIT_EXTENSION", "producer PASS drift")
    require(terminal.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_16DIGIT_EXTENSION", "terminal PASS drift")
    offsets, indices, values, rhs = read_integral()
    x = [int(value) for value in json.loads(X12.read_text(encoding="utf-8"))]
    require(len(x) == COLUMNS, "X12 length drift")
    modulus = P**12
    product = matvec(offsets, indices, values, x)
    q = []
    starting_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        starting_mismatches += int(residual % modulus != 0)
        q.append(residual // modulus)
    require(starting_mismatches == 0, "X12 divisibility replay failed")
    digit_audits = []
    snapshots: dict[int, list[int]] = {}
    for digit_index in range(12, 16):
        expected_rhs = bytes(value % P for value in q)
        rhs_path = ARTIFACT / f"correction_rhs_digit_{digit_index}.u8"
        digit_path = ARTIFACT / f"digit_{digit_index}.u8"
        require(rhs_path.read_bytes() == expected_rhs, f"correction RHS mismatch at digit {digit_index}")
        digit = list(digit_path.read_bytes())
        product_digit = matvec(offsets, indices, values, digit)
        next_q = []
        mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - product_digit[row]
            mismatches += int(numerator % P != 0)
            next_q.append(numerator // P)
        require(mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
        q = next_q
        digit_audits.append({"digit_index": digit_index, "rhs_sha256": file_hash(rhs_path), "digit_sha256": file_hash(digit_path), "divisibility_mismatches": mismatches})
        if digit_index + 1 in (14, 16):
            snapshots[digit_index + 1] = list(x)
    require(modulus == P**16, "terminal modulus drift")
    expected_x16 = [int(value) for value in json.loads((ARTIFACT / "X_mod_181_power_16.json").read_text(encoding="utf-8"))]
    require(x == expected_x16, "X16 serialization mismatch")
    final_product = matvec(offsets, indices, values, x)
    terminal_mismatches = sum(rhs[row] - final_product[row] != modulus * q[row] for row in range(ROWS))
    require(terminal_mismatches == 0, "terminal exact invariant failed")
    rr_audits: dict[str, object] = {}
    for digits in (14, 16):
        labels = bytes(reconstruct(value, P**digits) is not None for value in snapshots[digits])
        labels_path = ARTIFACT / f"equal_height_labels_{digits}.u8"
        require(labels == labels_path.read_bytes(), f"labels drift at {digits}")
        accepted = sum(labels)
        require(accepted == producer["rr_snapshots"][str(digits)]["accepted"], f"accepted count drift at {digits}")
        rr_audits[str(digits)] = {"accepted": accepted, "rejected": COLUMNS - accepted, "label_stream_sha256": hashlib.sha256(labels).hexdigest()}
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-16digit-extension-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_16DIGIT_EXTENSION_REPLAY",
        "bound_hashes": {"producer": file_hash(ARTIFACT / "extension.json"), "terminal": file_hash(TERMINAL), "integral": file_hash(INTEGRAL), "X12": file_hash(X12), "X16": file_hash(ARTIFACT / "X_mod_181_power_16.json")},
        "checks": {"starting_divisibility_mismatches": starting_mismatches, "correction_count": len(digit_audits), "terminal_modulus": str(modulus), "terminal_integer_invariant_mismatches": terminal_mismatches},
        "digit_audits": digit_audits,
        "rr_audits": rr_audits,
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"producer_not_imported_or_executed": True, "linbox_not_called": True, "cached_q12_not_read": True, "no_seventeenth_digit": True},
        "claim_boundary": "This PASS independently certifies the finite extension through 181^16 and its reconstruction labels. It is not a QQ identity or any colon, saturation, secant, nullcone, or HC4 theorem.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
