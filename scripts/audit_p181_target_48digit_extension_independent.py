#!/usr/bin/env python3
"""Independent exact replay of the fixed-main target through p^48."""

from __future__ import annotations

import json
import math
import resource
import struct
import time
from pathlib import Path

import audit_p181_target_36digit_extension_independent as base


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
P36_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-target-36digit-extension-v1"
P48_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-target-48digit-extension-v1"
X36 = P36_SOURCE / "X_mod_181_power_36.json"
Q36 = P36_SOURCE / "terminal_q36.i64le"
P36_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-36digit-extension-independent-audit.json"
PRODUCER = P48_SOURCE / "extension.json"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-48digit-extension-terminal.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-48digit-extension-independent-audit.json"


def main() -> int:
    started = time.perf_counter()
    base.require(not OUTPUT.exists(), "p48 independent audit exists")
    prior = json.loads(P36_AUDIT.read_text(encoding="utf-8"))
    producer = json.loads(PRODUCER.read_text(encoding="utf-8"))
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    base.require(prior.get("status") == "PASS_INDEPENDENT_P181_TARGET_36DIGIT_LIFT_REPLAY", "p36 audit status drift")
    base.require(producer.get("status") == terminal.get("status") == "PASS_P181_TARGET_48DIGIT_LIFT", "p48 status drift")
    base.require(prior["bound_hashes"]["x36"] == base.digest(X36) and prior["bound_hashes"]["q36"] == base.digest(Q36), "p36 input drift")
    offsets, indices, values, rhs = base.read_integral()
    x36 = [int(value) for value in json.loads(X36.read_text(encoding="utf-8"))]
    x = list(x36)
    q = [item[0] for item in struct.iter_unpack("<q", Q36.read_bytes())]
    base.require(len(x) == COLUMNS and len(q) == ROWS, "p36 dimensions drift")
    modulus = P**36
    digit_audits = []
    for digit_index in range(36, 48):
        rhs_path = P48_SOURCE / f"correction_rhs_digit_{digit_index:02d}.u8"
        digit_path = P48_SOURCE / f"digit_{digit_index:02d}.u8"
        base.require(rhs_path.read_bytes() == bytes(value % P for value in q), f"correction RHS mismatch at digit {digit_index}")
        digit = list(digit_path.read_bytes())
        base.require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        digit_product = base.matvec(offsets, indices, values, digit)
        next_q = []
        mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - digit_product[row]
            mismatches += numerator % P != 0
            next_q.append(numerator // P)
        base.require(mismatches == 0, f"digit recurrence mismatch at {digit_index}")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
        q = next_q
        digit_audits.append({"digit_index": digit_index, "rhs_sha256": base.digest(rhs_path), "digit_sha256": base.digest(digit_path), "divisibility_mismatches": mismatches})
    base.require(modulus == P**48, "terminal modulus drift")
    saved_x = [int(value) for value in json.loads((P48_SOURCE / "X_mod_181_power_48.json").read_text(encoding="utf-8"))]
    saved_q = [item[0] for item in struct.iter_unpack("<q", (P48_SOURCE / "terminal_q48.i64le").read_bytes())]
    base.require(x == saved_x and q == saved_q, "terminal serialization mismatch")
    final_product = base.matvec(offsets, indices, values, x)
    terminal_mismatches = sum(rhs[row] - final_product[row] != modulus * q[row] for row in range(ROWS))
    base.require(terminal_mismatches == 0, "terminal integer invariant failed")

    census = {"coordinate_count": COLUMNS, "resolved_zero_count": 0, "resolved_nonzero_count": 0, "unresolved_count": 0, "maximum_absolute_numerator": 0, "maximum_denominator": 0}
    stability = {"p36_zero_count": 0, "p36_zero_stable_at_p48": 0, "p36_zero_changed_at_p48": 0, "p36_zero_unresolved_at_p48": 0, "p36_nonzero_count": 0, "p36_nonzero_stable_at_p48": 0, "p36_nonzero_changed_at_p48": 0, "p36_nonzero_unresolved_at_p48": 0}
    for old_value, new_value in zip(x36, x):
        pair36 = base.reconstruct(old_value, P**36)
        pair48 = base.reconstruct(new_value, modulus)
        if pair48 is None:
            census["unresolved_count"] += 1
        elif pair48[0] == 0:
            census["resolved_zero_count"] += 1
        else:
            census["resolved_nonzero_count"] += 1
            census["maximum_absolute_numerator"] = max(census["maximum_absolute_numerator"], abs(pair48[0]))
            census["maximum_denominator"] = max(census["maximum_denominator"], pair48[1])
        if pair36 == (0, 1):
            stability["p36_zero_count"] += 1
            key = "p36_zero_unresolved_at_p48" if pair48 is None else "p36_zero_stable_at_p48" if pair48 == pair36 else "p36_zero_changed_at_p48"
            stability[key] += 1
        elif pair36 is not None:
            stability["p36_nonzero_count"] += 1
            key = "p36_nonzero_unresolved_at_p48" if pair48 is None else "p36_nonzero_stable_at_p48" if pair48 == pair36 else "p36_nonzero_changed_at_p48"
            stability[key] += 1
    census["equal_height_bound"] = math.isqrt((modulus - 1) // 2)
    base.require(census == producer["reconstruction_census"] and stability == producer["p36_to_p48_stability"], "p48 diagnostic mismatch")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    base.require(resources["wall_seconds"] < 120 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-target-48digit-extension-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_TARGET_48DIGIT_LIFT_REPLAY",
        "bound_hashes": {"integral": base.digest(base.INTEGRAL), "x36": base.digest(X36), "q36": base.digest(Q36), "p36_audit": base.digest(P36_AUDIT), "producer": base.digest(PRODUCER), "terminal": base.digest(TERMINAL), "x48": base.digest(P48_SOURCE / "X_mod_181_power_48.json"), "q48": base.digest(P48_SOURCE / "terminal_q48.i64le"), "frozen_helper": base.digest(Path(base.__file__))},
        "lift_checks": {"digit_count": len(digit_audits), "terminal_modulus": str(modulus), "terminal_integer_invariant_mismatches": terminal_mismatches},
        "digit_audits": digit_audits,
        "reconstruction_census": census,
        "p36_to_p48_stability": stability,
        "resources": resources,
        "declarations": {"producer_not_imported_or_executed": True, "driver_not_called": True, "rational_reconstruction_reimplemented": True, "x48_reconstructed_from_x36_and_raw_digits": True, "no_new_digit": True, "target_membership_not_claimed": True},
        "claim_boundary": "This PASS independently certifies the finite fixed-main p48 lift, height census, and p36-to-p48 stability table only. It is not rational target membership or any colon, saturation, secant, nullcone, or HC4 theorem.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": base.digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
