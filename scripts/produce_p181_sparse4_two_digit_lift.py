#!/usr/bin/env python3
"""Build and run the frozen sparse-four p^2 lift."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, stdout_path, stderr_path):
    completed = subprocess.run(command, cwd=CAMPAIGN, text=True, capture_output=True)
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    integral = output / "integral"
    lift = output / "lift"
    builder = run(
        ["/Users/admin/.local/bin/sage", "-python", str(CAMPAIGN / "scripts/build_p181_sparse4_coefficient_integral_system.py"), "--output-dir", str(integral)],
        output / "builder.stdout.txt", output / "builder.stderr.txt",
    )
    if builder.returncode != 0:
        result = {"status": "FAIL_P181_SPARSE4_INTEGRAL_BUILD", "builder_return_code": builder.returncode}
    else:
        lifted = run(
            ["/usr/bin/python3", str(CAMPAIGN / "scripts/lift_p181_sparse4_to_two_digits.py"), "--integral-dir", str(integral), "--output-dir", str(lift)],
            output / "lift.stdout.txt", output / "lift.stderr.txt",
        )
        lift_receipt = json.loads((lift / "lift.json").read_text(encoding="utf-8")) if (lift / "lift.json").exists() else None
        result = {
            "status": lift_receipt.get("status") if lift_receipt else "FAIL_P181_SPARSE4_TWO_DIGIT_LIFT",
            "builder_return_code": builder.returncode,
            "lift_return_code": lifted.returncode,
            "integral_receipt_sha256": file_hash(integral / "integral-system.json"),
            "lift_receipt_sha256": file_hash(lift / "lift.json") if lift_receipt else None,
        }
    result["claim_boundary"] = "This producer concerns exactly four fixed canonical residual columns through p^2. It proves no general QQ lift, target membership, colon, saturation, secant closure, nullcone containment, or HC4 theorem."
    receipt = output / "producer.json"
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": result["status"], "receipt": str(receipt), "sha256": file_hash(receipt)}))
    return 0 if str(result["status"]).startswith("PASS_") else 4 if str(result["status"]).startswith("STOP_") else 2


if __name__ == "__main__":
    raise SystemExit(main())

