#!/usr/bin/env python3
"""Externally gate, quarantine, and promote the residual-114 exact chart."""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


WALL_CAP_SECONDS = 180.0
RSS_CAP_BYTES = 1_000_000_000
PRODUCER_RELATIVE = (
    "scripts/produce_j2_secant_r10_third_colon_residual_114_two_prime_exact_chart.py"
)
FINAL_ARTIFACT_RELATIVE = (
    "artifacts/j2-secant-r10-third-colon-residual-114-two-prime-exact-chart.json"
)
FINAL_RECEIPT_RELATIVE = (
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart.json"
)
TELEMETRY_RELATIVE = (
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart-"
    "external-telemetry.json"
)
FAILURE_RELATIVE = (
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart-"
    "failed.json"
)
PASS_STATUS = "PASS_RESIDUAL_114_TWO_PRIME_EXACT_RATIONAL_CHART"


class GateFailure(RuntimeError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    )


def write_new_json(path: Path, value: object, *, compact: bool) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite wrapper output: {path}")
    text = (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        if compact
        else json.dumps(value, indent=2, sort_keys=True) + "\n"
    )
    with path.open("x", encoding="ascii") as handle:
        handle.write(text)


def parse_ps_rows():
    output = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,command="], text=True, encoding="utf-8"
    )
    rows = []
    for line in output.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid = int(parts[0])
            parent_pid = int(parts[1])
        except ValueError:
            continue
        rows.append((pid, parent_pid, parts[2]))
    return rows


def command_executable(arguments: str):
    try:
        words = shlex.split(arguments, posix=True)
    except ValueError:
        words = arguments.split()
    if not words:
        return "", ""
    executable = words[0].lower()
    return executable, Path(executable).name


def is_python_or_sage_runtime(arguments: str) -> bool:
    executable, executable_name = command_executable(arguments)
    return "python" in executable_name or "sage" in executable


def recognized_algebra_processes(producer_name: str, root_pid: int | None = None):
    producer = []
    other = []
    own_pid = os.getpid()
    rows = parse_ps_rows()
    parent_by_pid = {pid: parent_pid for pid, parent_pid, _arguments in rows}
    wrapper_ancestors = {own_pid}
    ancestor_pid = parent_by_pid.get(own_pid)
    while ancestor_pid is not None and ancestor_pid not in wrapper_ancestors:
        wrapper_ancestors.add(ancestor_pid)
        ancestor_pid = parent_by_pid.get(ancestor_pid)
    descendants = set()
    if root_pid is not None:
        frontier = {root_pid}
        while frontier:
            children = {
                pid
                for pid, parent_pid, _arguments in rows
                if parent_pid in frontier and pid not in descendants
            }
            descendants.update(children)
            frontier = children
        descendants.add(root_pid)
        candidate_pids = {
            pid
            for pid, _parent_pid, arguments in rows
            if pid in descendants
            and producer_name in arguments
            and is_python_or_sage_runtime(arguments)
        }
        candidate_parents = {
            parent_pid
            for pid, parent_pid, _arguments in rows
            if pid in candidate_pids and parent_pid in candidate_pids
        }
        deepest_candidates = candidate_pids - candidate_parents
    else:
        deepest_candidates = {
            pid
            for pid, _parent_pid, arguments in rows
            if pid not in wrapper_ancestors
            and producer_name in arguments
            and is_python_or_sage_runtime(arguments)
        }
    for pid, _parent_pid, arguments in rows:
        if pid in wrapper_ancestors:
            continue
        lowered = arguments.lower()
        executable, executable_name = command_executable(arguments)
        if pid in deepest_candidates:
            producer.append({"pid": pid, "command": arguments})
            continue
        if root_pid is not None and pid in candidate_pids - deepest_candidates:
            continue
        if root_pid is not None and pid in descendants:
            if executable_name in {"singular", "msolve", "magma"} or (
                "python" in executable_name or "sage" in executable
            ):
                other.append({"pid": pid, "command": arguments})
            continue
        if executable_name in {"singular", "msolve", "magma"}:
            other.append({"pid": pid, "command": arguments})
            continue
        if "sage" in executable and "-python" in lowered and ".py" in lowered:
            other.append({"pid": pid, "command": arguments})
    return producer, other


def parse_time_l(stderr_text: str):
    real_matches = re.findall(
        r"(?m)^\s*([0-9]+(?:\.[0-9]+)?)\s+real\b", stderr_text
    )
    rss_matches = re.findall(
        r"(?m)^\s*([0-9]+)\s+maximum resident set size\s*$", stderr_text
    )
    swap_matches = re.findall(r"(?m)^\s*([0-9]+)\s+swaps\s*$", stderr_text)
    swap_lines_raw = [
        line for line in stderr_text.splitlines() if re.fullmatch(r"\s*\d+\s+swaps\s*", line)
    ]
    swap_lines = [" ".join(line.split()) for line in swap_lines_raw]
    return {
        "real_seconds": None if len(real_matches) != 1 else float(real_matches[0]),
        "maximum_rss_native_bytes": None
        if len(rss_matches) != 1
        else int(rss_matches[0]),
        "process_swaps": None if len(swap_matches) != 1 else int(swap_matches[0]),
        "process_swap_lines_stripped": swap_lines,
        "process_swap_lines_raw": swap_lines_raw,
        "real_line_count": len(real_matches),
        "maximum_rss_line_count": len(rss_matches),
        "process_swap_line_count": len(swap_matches),
    }


def run_quarantined(campaign: Path, quarantine: Path, producer_path: Path):
    candidate_artifact = quarantine / "candidate-artifact.json"
    candidate_receipt = quarantine / "candidate-receipt.json"
    candidate_failure = quarantine / "candidate-failure.json"
    stdout_path = quarantine / "stdout.txt"
    stderr_path = quarantine / "stderr.txt"
    command = [
        "/opt/homebrew/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "180s",
        "/usr/bin/time",
        "-l",
        "/Users/admin/.local/bin/sage",
        "-python",
        str(producer_path),
        "--artifact-output",
        str(candidate_artifact),
        "--receipt-output",
        str(candidate_receipt),
        "--failure-output",
        str(candidate_failure),
    ]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONHASHSEED"] = "0"

    preexisting_producer, preexisting_other = recognized_algebra_processes(
        producer_path.name
    )
    if preexisting_producer or preexisting_other:
        raise GateFailure(
            "recognized algebra process exists before gated launch",
            {
                "preexisting_producer_processes": preexisting_producer,
                "preexisting_other_algebra_processes": preexisting_other,
            },
        )

    producer_histogram = collections.Counter()
    other_histogram = collections.Counter()
    total_histogram = collections.Counter()
    max_producer = max_other = max_total = 0
    monitor_samples = 0
    wrapper_started = time.perf_counter()
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=campaign,
            env=environment,
            stdout=stdout_handle,
            stderr=stderr_handle,
            shell=False,
        )
        while process.poll() is None:
            producer_processes, other_processes = recognized_algebra_processes(
                producer_path.name, process.pid
            )
            producer_count = len(producer_processes)
            other_count = len(other_processes)
            total_count = producer_count + other_count
            producer_histogram[producer_count] += 1
            other_histogram[other_count] += 1
            total_histogram[total_count] += 1
            max_producer = max(max_producer, producer_count)
            max_other = max(max_other, other_count)
            max_total = max(max_total, total_count)
            monitor_samples += 1
            if max_total > 1:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                break
            time.sleep(0.1)
        return_code = process.wait()
    wrapper_elapsed = time.perf_counter() - wrapper_started
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_time_l(stderr_text)
    algebra = {
        "declared_algebra_process_count": 1,
        "monitor_sample_count": monitor_samples,
        "producer_process_count_histogram": {
            str(key): value for key, value in sorted(producer_histogram.items())
        },
        "other_algebra_process_count_histogram": {
            str(key): value for key, value in sorted(other_histogram.items())
        },
        "total_algebra_process_count_histogram": {
            str(key): value for key, value in sorted(total_histogram.items())
        },
        "maximum_producer_algebra_process_count": max_producer,
        "maximum_other_algebra_process_count": max_other,
        "maximum_total_algebra_process_count": max_total,
        "observed_exactly_one_producer_process": producer_histogram[1] > 0,
    }
    gates = {
        "exit_status_zero": return_code == 0,
        "external_real_line_present_once": parsed["real_line_count"] == 1,
        "external_wall_within_180_seconds": parsed["real_seconds"] is not None
        and parsed["real_seconds"] <= WALL_CAP_SECONDS,
        "external_maximum_rss_line_present_once": parsed["maximum_rss_line_count"]
        == 1,
        "external_maximum_rss_within_1000000000_bytes": parsed[
            "maximum_rss_native_bytes"
        ]
        is not None
        and parsed["maximum_rss_native_bytes"] <= RSS_CAP_BYTES,
        "literal_external_swap_line_present_once": parsed["process_swap_line_count"]
        == 1,
        "literal_external_process_swaps_zero": parsed["process_swaps"] == 0
        and parsed["process_swap_lines_stripped"] == ["0 swaps"],
        "one_algebra_process_observed": max_producer == 1
        and max_other == 0
        and max_total == 1
        and producer_histogram[1] > 0,
        "candidate_artifact_exists": candidate_artifact.is_file(),
        "candidate_receipt_exists": candidate_receipt.is_file(),
        "candidate_failure_absent": not candidate_failure.exists(),
    }
    execution = {
        "command": shlex.join(command),
        "exit_status": return_code,
        "wrapper_observed_elapsed_seconds": wrapper_elapsed,
        "external_time_l": parsed,
        "algebra_process_monitor": algebra,
        "stdout_sha256": sha256_bytes(stdout_path.read_bytes()),
        "stderr_sha256": sha256_bytes(stderr_path.read_bytes()),
        "stdout": stdout_text,
        "stderr": stderr_text,
        "gates": gates,
        "candidate_paths": {
            "artifact": str(candidate_artifact),
            "receipt": str(candidate_receipt),
            "failure": str(candidate_failure),
        },
    }
    return execution, candidate_artifact, candidate_receipt, candidate_failure


def validate_and_prepare_promoted(
    campaign: Path,
    wrapper_path: Path,
    producer_path: Path,
    quarantine: Path,
    execution: dict,
    candidate_artifact_path: Path,
    candidate_receipt_path: Path,
):
    if not all(execution["gates"].values()):
        raise GateFailure("one or more external/quarantine gates failed", execution)
    candidate_artifact_hash = sha256_bytes(candidate_artifact_path.read_bytes())
    candidate_receipt_hash = sha256_bytes(candidate_receipt_path.read_bytes())
    artifact = json.loads(candidate_artifact_path.read_text(encoding="ascii"))
    receipt = json.loads(candidate_receipt_path.read_text(encoding="ascii"))
    if (
        artifact.get("status")
        != "PASS_QUARANTINED_RESIDUAL_114_TWO_PRIME_EXACT_RATIONAL_CHART"
        or artifact.get("promotion_state")
        != "quarantined_pending_external_resource_gate"
        or receipt.get("status")
        != "PASS_QUARANTINED_RESIDUAL_114_TWO_PRIME_EXACT_RATIONAL_CHART"
        or receipt.get("promotion_state")
        != "quarantined_pending_external_resource_gate"
        or receipt.get("quarantined_artifact", {}).get("sha256")
        != candidate_artifact_hash
        or not all(artifact.get("checks", {}).values())
        or not all(receipt.get("checks", {}).values())
        or receipt.get("internal_resources", {}).get("initial_process_swaps") != 0
        or receipt.get("internal_resources", {}).get("final_process_swaps") != 0
    ):
        raise GateFailure(
            "quarantined producer payload failed semantic validation",
            {
                "candidate_artifact_sha256": candidate_artifact_hash,
                "candidate_receipt_sha256": candidate_receipt_hash,
            },
        )

    gate_summary = {
        "external_wall_seconds": execution["external_time_l"]["real_seconds"],
        "external_maximum_rss_native_bytes": execution["external_time_l"][
            "maximum_rss_native_bytes"
        ],
        "literal_external_process_swaps": execution["external_time_l"][
            "process_swaps"
        ],
        "literal_external_process_swap_line": execution["external_time_l"][
            "process_swap_lines_stripped"
        ][0],
        "maximum_total_algebra_process_count": execution[
            "algebra_process_monitor"
        ]["maximum_total_algebra_process_count"],
        "all_external_gates_pass": True,
        "command": execution["command"],
    }
    artifact["status"] = PASS_STATUS
    artifact["promotion_state"] = "promoted_after_external_resource_gate_pass"
    artifact["external_resource_gate"] = gate_summary
    artifact["producer_quarantine_binding"] = {
        "artifact_sha256": candidate_artifact_hash,
        "receipt_sha256": candidate_receipt_hash,
    }
    artifact["checks"]["external_resource_gate_pass"] = True

    promoted_artifact_path = quarantine / "promoted-artifact.json"
    write_new_json(promoted_artifact_path, artifact, compact=True)
    promoted_artifact_hash = sha256_bytes(promoted_artifact_path.read_bytes())

    receipt["status"] = PASS_STATUS
    receipt["promotion_state"] = "promoted_after_external_resource_gate_pass"
    receipt["external_resource_gate"] = gate_summary
    receipt["producer_quarantine_binding"] = {
        "artifact_sha256": candidate_artifact_hash,
        "receipt_sha256": candidate_receipt_hash,
    }
    receipt["promoted_artifact"] = {
        "path": FINAL_ARTIFACT_RELATIVE,
        "sha256": promoted_artifact_hash,
        "byte_count": promoted_artifact_path.stat().st_size,
    }
    receipt["promotion_wrapper"] = {
        "path": str(wrapper_path.relative_to(campaign)),
        "sha256": sha256_bytes(wrapper_path.read_bytes()),
        "producer_path": str(producer_path.relative_to(campaign)),
        "producer_sha256": sha256_bytes(producer_path.read_bytes()),
        "artifact_promoted_last": True,
    }
    receipt["checks"]["external_resource_gate_pass"] = True
    promoted_receipt_path = quarantine / "promoted-receipt.json"
    write_new_json(promoted_receipt_path, receipt, compact=False)
    promoted_receipt_hash = sha256_bytes(promoted_receipt_path.read_bytes())

    telemetry = {
        "schema": "hc4.third-colon-residual-114-two-prime-exact-chart-external-telemetry.v1",
        "status": "PASS_EXTERNAL_RESOURCE_GATED_RESIDUAL_114_TWO_PRIME_EXACT_CHART",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "caps": {
            "wall_seconds": WALL_CAP_SECONDS,
            "maximum_rss_bytes": RSS_CAP_BYTES,
            "literal_process_swaps": 0,
            "algebra_process_count": 1,
        },
        "command": execution["command"],
        "external_telemetry": execution["external_time_l"],
        "exit_status": execution["exit_status"],
        "wrapper_observed_elapsed_seconds": execution[
            "wrapper_observed_elapsed_seconds"
        ],
        "algebra_process_monitor": execution["algebra_process_monitor"],
        "gates": execution["gates"],
        "streams": {
            "stdout_sha256": execution["stdout_sha256"],
            "stderr_sha256": execution["stderr_sha256"],
            "stdout": execution["stdout"],
            "stderr": execution["stderr"],
        },
        "producer": {
            "path": str(producer_path.relative_to(campaign)),
            "sha256": sha256_bytes(producer_path.read_bytes()),
        },
        "wrapper": {
            "path": str(wrapper_path.relative_to(campaign)),
            "sha256": sha256_bytes(wrapper_path.read_bytes()),
        },
        "quarantined_payloads": {
            "artifact_sha256": candidate_artifact_hash,
            "receipt_sha256": candidate_receipt_hash,
        },
        "promoted_outputs": {
            "artifact": {
                "path": FINAL_ARTIFACT_RELATIVE,
                "sha256": promoted_artifact_hash,
            },
            "receipt": {
                "path": FINAL_RECEIPT_RELATIVE,
                "sha256": promoted_receipt_hash,
            },
        },
        "claim_boundary": artifact["claim_boundary"],
    }
    promoted_telemetry_path = quarantine / "promoted-telemetry.json"
    write_new_json(promoted_telemetry_path, telemetry, compact=False)
    return (
        promoted_artifact_path,
        promoted_receipt_path,
        promoted_telemetry_path,
        telemetry,
    )


def link_new(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite final output: {destination}")
    os.link(source, destination)


def failure_payload(
    campaign: Path,
    wrapper_path: Path,
    producer_path: Path,
    error: Exception,
    execution: dict | None,
    candidate_failure_path: Path | None,
):
    producer_failure = None
    if candidate_failure_path is not None and candidate_failure_path.is_file():
        try:
            producer_failure = json.loads(
                candidate_failure_path.read_text(encoding="ascii")
            )
        except Exception as parse_error:
            producer_failure = {
                "parse_error": str(parse_error),
                "sha256": sha256_bytes(candidate_failure_path.read_bytes()),
            }
    details = error.details if isinstance(error, GateFailure) else None
    telemetry = {
        "schema": "hc4.third-colon-residual-114-two-prime-exact-chart-external-telemetry.v1",
        "status": "FAIL_CLOSED_EXTERNAL_RESOURCE_GATE_RESIDUAL_114_TWO_PRIME_EXACT_CHART",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "caps": {
            "wall_seconds": WALL_CAP_SECONDS,
            "maximum_rss_bytes": RSS_CAP_BYTES,
            "literal_process_swaps": 0,
            "algebra_process_count": 1,
        },
        "error_type": type(error).__name__,
        "error": str(error),
        "details": details,
        "execution": execution,
        "producer_failure": producer_failure,
        "producer": {
            "path": str(producer_path.relative_to(campaign)),
            "sha256": sha256_bytes(producer_path.read_bytes()),
        },
        "wrapper": {
            "path": str(wrapper_path.relative_to(campaign)),
            "sha256": sha256_bytes(wrapper_path.read_bytes()),
        },
        "pass_artifact_survives": False,
    }
    failure = {
        "schema": "hc4.third-colon-residual-114-two-prime-exact-chart-wrapper-failure.v1",
        "status": "FAIL_CLOSED_RESIDUAL_114_TWO_PRIME_EXACT_CHART",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "error_type": type(error).__name__,
        "error": str(error),
        "details": details,
        "producer_failure": producer_failure,
        "external_telemetry_path": TELEMETRY_RELATIVE,
        "pass_artifact_survives": False,
        "claim_boundary": (
            "No exact rational quotient chart, target multiplier, QQ membership, colon, saturation, secant-chart, nullcone, or HC4 conclusion is licensed by this failed externally gated route."
        ),
    }
    return telemetry, failure


def main() -> int:
    wrapper_path = Path(__file__).resolve()
    campaign = wrapper_path.parent.parent
    producer_path = campaign / PRODUCER_RELATIVE
    final_artifact = campaign / FINAL_ARTIFACT_RELATIVE
    final_receipt = campaign / FINAL_RECEIPT_RELATIVE
    final_telemetry = campaign / TELEMETRY_RELATIVE
    final_failure = campaign / FAILURE_RELATIVE
    final_paths = (final_artifact, final_receipt, final_telemetry, final_failure)
    created_final_paths = []
    quarantine_path = None
    execution = None
    candidate_failure = None
    try:
        if any(path.exists() for path in final_paths):
            existing = [str(path) for path in final_paths if path.exists()]
            raise FileExistsError(f"refusing to overwrite existing extension output: {existing}")
        quarantine_path = Path(
            tempfile.mkdtemp(
                prefix=".residual-114-two-prime-exact-chart-quarantine-",
                dir=campaign / "artifacts",
            )
        )
        execution, candidate_artifact, candidate_receipt, candidate_failure = run_quarantined(
            campaign, quarantine_path, producer_path
        )
        (
            promoted_artifact,
            promoted_receipt,
            promoted_telemetry,
            telemetry,
        ) = validate_and_prepare_promoted(
            campaign,
            wrapper_path,
            producer_path,
            quarantine_path,
            execution,
            candidate_artifact,
            candidate_receipt,
        )

        for source, destination in (
            (promoted_telemetry, final_telemetry),
            (promoted_receipt, final_receipt),
            (promoted_artifact, final_artifact),
        ):
            link_new(source, destination)
            created_final_paths.append(destination)
        expected = telemetry["promoted_outputs"]
        if (
            sha256_bytes(final_artifact.read_bytes())
            != expected["artifact"]["sha256"]
            or sha256_bytes(final_receipt.read_bytes())
            != expected["receipt"]["sha256"]
            or json.loads(final_artifact.read_text(encoding="ascii")).get("status")
            != PASS_STATUS
        ):
            raise GateFailure("post-promotion hash/status readback failed")
        print(
            json.dumps(
                {
                    "status": PASS_STATUS,
                    "artifact": FINAL_ARTIFACT_RELATIVE,
                    "artifact_sha256": expected["artifact"]["sha256"],
                    "receipt": FINAL_RECEIPT_RELATIVE,
                    "receipt_sha256": expected["receipt"]["sha256"],
                    "telemetry": TELEMETRY_RELATIVE,
                    "external_real_seconds": execution["external_time_l"][
                        "real_seconds"
                    ],
                    "external_maximum_rss_native_bytes": execution[
                        "external_time_l"
                    ]["maximum_rss_native_bytes"],
                    "literal_external_process_swaps": execution[
                        "external_time_l"
                    ]["process_swaps"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        for path in reversed(created_final_paths):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        telemetry, failure = failure_payload(
            campaign,
            wrapper_path,
            producer_path,
            error,
            execution,
            candidate_failure,
        )
        try:
            write_new_json(final_telemetry, telemetry, compact=False)
            write_new_json(final_failure, failure, compact=False)
        except Exception as write_error:
            print(f"failure/telemetry freeze also failed: {write_error}", file=sys.stderr)
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        if quarantine_path is not None:
            shutil.rmtree(quarantine_path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
