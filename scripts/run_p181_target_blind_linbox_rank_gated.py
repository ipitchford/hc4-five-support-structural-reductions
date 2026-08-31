#!/usr/bin/env python3
"""Supervise and promote the prospectively frozen target-blind rank benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-implementation-freeze.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def tree_hashes(path: Path) -> dict[str, str]:
    return {str(item.relative_to(path)): file_hash(item) for item in sorted(path.rglob("*")) if item.is_file()}


def process_table() -> dict[int, tuple[int, int, str]]:
    completed = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,rss=,command="], text=True, capture_output=True, check=True)
    result = {}
    for line in completed.stdout.splitlines():
        match = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(.*)", line)
        if match:
            result[int(match.group(1))] = (int(match.group(2)), int(match.group(3)) * 1024, match.group(4))
    return result


def descendants(root: int, table: dict[int, tuple[int, int, str]]) -> set[int]:
    found = set()
    frontier = {root}
    while frontier:
        new = {pid for pid, (parent, _rss, _command) in table.items() if parent in frontier and pid not in found}
        found.update(new)
        frontier = new
    return found


def parse_time(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    timing = re.search(r"^\s*([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys\s*$", text, re.MULTILINE)
    rss = re.findall(r"^\s*(\d+)\s+maximum resident set size\s*$", text, re.MULTILINE)
    swaps = re.findall(r"^\s*(\d+)\s+swaps\s*$", text, re.MULTILINE)
    require(timing is not None and len(rss) == 1 and len(swaps) == 1, "external telemetry incomplete")
    return {
        "real_seconds": float(timing.group(1)),
        "user_seconds": float(timing.group(2)),
        "system_seconds": float(timing.group(3)),
        "maximum_rss_bytes": int(rss[0]),
        "process_swaps": int(swaps[0]),
        "raw_sha256": file_hash(path),
    }


def supervise(command: list[str], telemetry: Path, wall: int, rss_limit: int) -> dict[str, object]:
    telemetry.mkdir(parents=True, exist_ok=False)
    stdout = telemetry / "benchmark.stdout.txt"
    stderr = telemetry / "benchmark.stderr.txt"
    time_path = telemetry / "benchmark.time.txt"
    full = ["/usr/bin/time", "-l", "-o", str(time_path), "/opt/homebrew/bin/gtimeout", "-s", "TERM", "-k", "10s", f"{wall}s", *command]
    peak_sampled = 0
    rss_breach = False
    samples = 0
    with stdout.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen(full, cwd=CAMPAIGN, stdout=out, stderr=err, start_new_session=True)
        while process.poll() is None:
            table = process_table()
            pids = descendants(process.pid, table) | {process.pid}
            sampled = sum(table.get(pid, (0, 0, ""))[1] for pid in pids)
            peak_sampled = max(peak_sampled, sampled)
            samples += 1
            if sampled > rss_limit:
                rss_breach = True
                os.killpg(process.pid, signal.SIGTERM)
                break
            time.sleep(0.20)
        try:
            return_code = process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            return_code = process.wait()
    external = parse_time(time_path) if time_path.exists() else None
    return {
        "command": full,
        "return_code": return_code,
        "sampled_descendant_rss_peak_bytes": peak_sampled,
        "ancestry_samples": samples,
        "rss_breach_killed": rss_breach,
        "external_time": external,
        "stdout_sha256": file_hash(stdout),
        "stderr_sha256": file_hash(stderr),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    args = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    require(freeze.get("status") == "PASS_P181_TARGET_BLIND_LINBOX_IMPLEMENTATION_FREEZE", "freeze absent")
    for relative, expected in freeze["implementation_sources"].items():
        require(file_hash(CAMPAIGN / relative) == expected, f"implementation drift: {relative}")
    for relative, expected in freeze["algebra_and_prior_sources"].items():
        require(file_hash(CAMPAIGN / relative) == expected, f"bound source drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    require(not any(path.exists() for path in outputs.values()), "canonical output already exists")
    staging_root = CAMPAIGN / "artifacts/staging"
    gauge_stage = staging_root / f"p181-target-blind-linbox-gauge-{args.run_id}"
    benchmark_stage = staging_root / f"p181-target-blind-linbox-benchmark-{args.run_id}"
    telemetry_stage = staging_root / f"p181-target-blind-linbox-telemetry-{args.run_id}"
    terminal = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-linbox-terminal.v1",
        "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": file_hash(FREEZE)},
    }
    try:
        subprocess.run(["/usr/bin/python3", str(CAMPAIGN / "scripts/extract_p181_target_blind_linbox_gauge.py"), "--output-dir", str(gauge_stage)], cwd=CAMPAIGN, check=True)
        policy = freeze["policy"]
        telemetry = supervise(
            ["/Users/admin/.local/bin/sage", "-python", str(CAMPAIGN / "scripts/benchmark_p181_target_blind_linbox_rank.py"), "--gauge-dir", str(gauge_stage), "--output-dir", str(benchmark_stage), "--freeze", str(FREEZE)],
            telemetry_stage,
            int(policy["rank_wall_seconds_maximum"]),
            int(policy["rank_rss_bytes_maximum"]),
        )
        receipt_path = benchmark_stage / "benchmark.json"
        benchmark = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else None
        external = telemetry.get("external_time") or {}
        passed = (
            telemetry["return_code"] == 0
            and not telemetry["rss_breach_killed"]
            and external.get("real_seconds", policy["rank_wall_seconds_maximum"] + 1) <= policy["rank_wall_seconds_maximum"]
            and external.get("maximum_rss_bytes", policy["rank_rss_bytes_maximum"] + 1) <= policy["rank_rss_bytes_maximum"]
            and external.get("process_swaps", 1) == 0
            and benchmark is not None
            and benchmark.get("status") == "PASS_ACTUAL_COEFFICIENT_LINBOX_FULL_COLUMN_RANK_SCALING"
        )
        terminal.update({
            "status": "PASS_ACTUAL_COEFFICIENT_LINBOX_FULL_COLUMN_RANK_SCALING" if passed else "STOP_ACTUAL_COEFFICIENT_LINBOX_RESOURCE_OR_RANK_GATE",
            "telemetry": telemetry,
            "benchmark_status": benchmark.get("status") if benchmark else None,
            "completed_cases": benchmark.get("cases", []) if benchmark else json.loads((benchmark_stage / "checkpoint.json").read_text())["completed_cases"] if (benchmark_stage / "checkpoint.json").exists() else [],
            "declarations": {"target_blind": True, "no_rhs": True, "no_augmented_rank": True, "no_solve": True, "no_digit": True},
            "claim_boundary": "A PASS is exact rank/scaling evidence for the actual coefficient map only; no target-membership or HC4 conclusion follows.",
        })
        if not passed:
            raise RuntimeError("registered rank/resource gate did not pass")
        os.rename(gauge_stage, outputs["gauge"])
        os.rename(benchmark_stage, outputs["benchmark"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"gauge": tree_hashes(outputs["gauge"]), "benchmark": tree_hashes(outputs["benchmark"]), "telemetry": tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "terminal": str(outputs["terminal"]), "sha256": file_hash(outputs["terminal"])}))
        return 0
    except Exception as error:
        terminal.setdefault("status", "FAIL_ACTUAL_COEFFICIENT_LINBOX_INTEGRITY")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {str(path.relative_to(CAMPAIGN)): tree_hashes(path) for path in (gauge_stage, benchmark_stage, telemetry_stage) if path.exists()}
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"], "terminal": str(outputs["terminal"])}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
