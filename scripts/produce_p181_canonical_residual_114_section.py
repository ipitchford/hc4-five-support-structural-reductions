#!/usr/bin/env python3
"""Run the frozen RHS builder, 114-RHS solver, and section verifier."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
PASS = "PASS_P181_CANONICAL_RESIDUAL_114_MODULAR_KERNEL_SECTION"


def file_hash(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_stage(command: list[str], stdout_path: Path, stderr_path: Path):
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

    builder = run_stage(
        [
            "/Users/admin/.local/bin/sage",
            "-python",
            str(CAMPAIGN / "scripts/build_p181_canonical_residual_114_rhs.py"),
            "--output-dir",
            str(output / "rhs"),
        ],
        output / "builder.stdout.txt",
        output / "builder.stderr.txt",
    )
    if builder.returncode != 0:
        result = {"status": "FAIL_P181_CANONICAL_RESIDUAL_114_RHS_BUILD", "builder_return_code": builder.returncode}
    else:
        driver = run_stage(
            [
                str(CAMPAIGN / "artifacts/bin/linbox_p181_canonical_residual_114_section_driver"),
                "--csr",
                str(CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"),
                "--rhs",
                str(output / "rhs/minus_A_S_row_major.u8"),
                "--solution-output",
                str(output / "pivot_section_row_major.u8"),
            ],
            output / "driver.stdout.txt",
            output / "driver.stderr.txt",
        )
        driver_lines = [line for line in driver.stdout.splitlines() if line.strip()]
        driver_record = json.loads(driver_lines[0]) if len(driver_lines) == 1 else None
        if driver.returncode == 4 and driver_record is not None:
            result = {"status": driver_record.get("status"), "driver_return_code": driver.returncode, "driver": driver_record}
        elif driver.returncode != 0 or driver_record is None:
            result = {"status": "FAIL_P181_CANONICAL_RESIDUAL_114_DRIVER", "driver_return_code": driver.returncode, "driver": driver_record}
        else:
            verifier = run_stage(
                [
                    "/Users/admin/.local/bin/sage",
                    "-python",
                    str(CAMPAIGN / "scripts/verify_p181_canonical_residual_114_section.py"),
                    "--artifact-dir",
                    str(output),
                ],
                output / "verifier.stdout.txt",
                output / "verifier.stderr.txt",
            )
            section_path = output / "section.json"
            section = json.loads(section_path.read_text(encoding="utf-8")) if section_path.exists() else None
            if verifier.returncode == 0 and section is not None and section.get("status") == PASS:
                result = {"status": PASS, "builder_return_code": builder.returncode, "driver_return_code": driver.returncode, "verifier_return_code": verifier.returncode, "driver": driver_record, "section_sha256": file_hash(section_path)}
            else:
                result = {"status": "FAIL_P181_CANONICAL_RESIDUAL_114_VERIFICATION", "verifier_return_code": verifier.returncode, "section_status": section.get("status") if section else None}
    result["claim_boundary"] = "A PASS proves only the canonical residual-114 section and full encoded kernel decomposition over GF(181). It does not lift residual syzygies to QQ, prove QQ target membership, a colon, saturation, secant closure, nullcone containment, or HC4."
    result_path = output / "producer.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": result["status"], "receipt": str(result_path), "sha256": file_hash(result_path)}))
    return 0 if result["status"] == PASS else 4 if str(result["status"]).startswith("STOP_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
