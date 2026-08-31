#!/usr/bin/env python3
"""External resource and promotion gates for both fixed-p181 pilot phases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE_RELATIVE = Path("receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v3.json")
FACTOR_INDEX_RELATIVE = Path("receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v3.json")
TERMINAL_RELATIVE = Path("receipts/hsop-j2-secant-r10-third-colon-dixon-p181-8digit-terminal-v3.json")
FREEZE_SCHEMA = "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-implementation-freeze.v3"
FACTOR_INDEX_SCHEMA = "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-factorization-freeze.v3"
REQUIRED_CANONICAL_PATH_KEYS = {
    "phase1_bundle",
    "phase1_telemetry",
    "factorization_freeze_index",
    "producer_bundle",
    "independent_bundle",
    "phase2_telemetry",
    "terminal_receipt",
    "quarantine_root",
    "staging_root",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_exclusive_json(path: Path, payload: dict[str, object]) -> None:
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_directory(path.parent)


def tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): file_hash(item)
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def process_table() -> dict[int, tuple[int, str]]:
    completed = subprocess.run(
        ["/bin/ps", "-axo", "pid=,ppid=,command="],
        text=True,
        capture_output=True,
        check=True,
    )
    table = {}
    for line in completed.stdout.splitlines():
        match = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)", line)
        if match:
            table[int(match.group(1))] = (int(match.group(2)), match.group(3))
    return table


def descendants(root: int, table: dict[int, tuple[int, str]]) -> set[int]:
    result = set()
    frontier = {root}
    while frontier:
        new = {pid for pid, (parent, _command) in table.items() if parent in frontier and pid not in result}
        result.update(new)
        frontier = new
    return result


def assert_no_other_algebra_processes(script_names: set[str]) -> None:
    offenders = []
    for pid, (_parent, command) in process_table().items():
        if pid == os.getpid():
            continue
        if any(name in command for name in script_names):
            offenders.append({"pid": pid, "command": command})
    require(not offenders, f"another registered algebra process is alive: {offenders}")


def parse_time_file(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    first = re.search(r"^\s*([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys\s*$", text, re.MULTILINE)
    rss = re.findall(r"^\s*(\d+)\s+maximum resident set size\s*$", text, re.MULTILINE)
    swap_lines = re.findall(r"^\s*(\d+)\s+swaps\s*$", text, re.MULTILINE)
    require(first is not None and len(rss) == 1 and len(swap_lines) == 1, "external time telemetry is incomplete or ambiguous")
    require(swap_lines[0] == "0", "external process reported nonzero swaps")
    return {
        "real_seconds": float(first.group(1)),
        "user_seconds": float(first.group(2)),
        "system_seconds": float(first.group(3)),
        "maximum_rss_bytes": int(rss[0]),
        "process_swaps": 0,
        "literal_zero_swap_line_count": 1,
        "raw_sha256": file_hash(path),
        "raw_text": text,
    }


def run_child(
    *,
    label: str,
    command: list[str],
    target_script_name: str,
    telemetry_dir: Path,
    time_executable: str,
    timeout_executable: str,
    timeout_seconds: float,
    maximum_rss: int,
    require_seen: bool,
) -> dict[str, object]:
    time_path = telemetry_dir / f"{label}.time.txt"
    stdout_path = telemetry_dir / f"{label}.stdout.txt"
    stderr_path = telemetry_dir / f"{label}.stderr.txt"
    full_command = [
        time_executable,
        "-l",
        "-o",
        str(time_path),
        timeout_executable,
        "-s",
        "TERM",
        "-k",
        "10s",
        f"{max(1, int(timeout_seconds))}s",
        *command,
    ]
    maximum_algebra_descendants = 0
    samples = 0
    with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
        process = subprocess.Popen(full_command, cwd=CAMPAIGN, stdout=stdout_handle, stderr=stderr_handle)
        try:
            while process.poll() is None:
                table = process_table()
                child_pids = descendants(process.pid, table)
                algebra = []
                for pid in child_pids:
                    command_text = table[pid][1]
                    executable = Path(command_text.split(maxsplit=1)[0]).name if command_text else ""
                    if target_script_name in command_text and (
                        executable == "sage" or executable.startswith("python")
                    ):
                        algebra.append(pid)
                maximum_algebra_descendants = max(maximum_algebra_descendants, len(algebra))
                require(len(algebra) <= 1, f"multiple algebra descendants during {label}")
                samples += 1
                time.sleep(0.20)
            return_code = process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    require(time_path.is_file(), f"{label} produced no /usr/bin/time file")
    telemetry = parse_time_file(time_path)
    telemetry.update(
        {
            "label": label,
            "command": full_command,
            "return_code": return_code,
            "stdout_sha256": file_hash(stdout_path),
            "stderr_sha256": file_hash(stderr_path),
            "maximum_concurrent_algebra_descendants": maximum_algebra_descendants,
            "ancestry_sample_count": samples,
        }
    )
    require(return_code == 0, f"{label} exited {return_code}")
    require(telemetry["maximum_rss_bytes"] <= maximum_rss, f"{label} exceeded RSS gate")
    if require_seen:
        require(maximum_algebra_descendants == 1, f"{label} algebra child was never observed")
    return telemetry


def promote_directory(source: Path, destination: Path) -> None:
    require(source.is_dir(), f"promotion source missing: {source}")
    require(not destination.exists(), f"promotion destination exists: {destination}")
    require(source.stat().st_dev == destination.parent.stat().st_dev, "promotion is not same-filesystem")
    os.rename(source, destination)
    fsync_directory(destination.parent)


def quarantine(
    paths: list[Path], phase: str, run_id: str, error: Exception, quarantine_root: Path
) -> Path:
    root = quarantine_root / f"third-colon-fixed-p181-dixon-{phase}-{run_id}"
    root.mkdir(parents=True, exist_ok=False)
    retained = {}
    for path in paths:
        if not path.exists():
            continue
        destination = root / path.name
        os.rename(path, destination)
        retained[path.name] = tree_hashes(destination) if destination.is_dir() else {path.name: file_hash(destination)}
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-quarantine.v1",
        "status": "NOT_EVIDENCE",
        "phase": phase,
        "run_id": run_id,
        "error_type": type(error).__name__,
        "error": str(error),
        "retained_hashes": retained,
        "declarations": {"cannot_feed_later_run": True, "no_canonical_pass_survives": True},
    }
    write_exclusive_json(root / "NOT_EVIDENCE.json", payload)
    return root


def load_implementation() -> tuple[Path, dict[str, object]]:
    path = CAMPAIGN / FREEZE_RELATIVE
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(payload.get("schema") == FREEZE_SCHEMA and payload.get("status") == "PASS_IMPLEMENTATION_FREEZE", "implementation freeze invalid")
    relative = str(Path(__file__).resolve().relative_to(CAMPAIGN))
    require(payload["implementation_sources"].get(relative) == file_hash(Path(__file__).resolve()), "wrapper source differs from freeze")
    for relative, expected in payload["documents"].items():
        require(file_hash(CAMPAIGN / relative) == expected, f"document drift: {relative}")
    for relative, expected in payload["algebra_and_historical_sources"].items():
        require(file_hash(CAMPAIGN / relative) == expected, f"bound source drift: {relative}")
    for relative, expected in payload["implementation_sources"].items():
        require(file_hash(CAMPAIGN / relative) == expected, f"implementation drift: {relative}")
    return path, payload


def phase1(run_id: str) -> dict[str, object]:
    implementation_path, implementation = load_implementation()
    policy = implementation["policy"]
    paths = implementation["canonical_paths"]
    require(set(paths) == REQUIRED_CANONICAL_PATH_KEYS, "canonical path interface drift")
    bundle = CAMPAIGN / paths["phase1_bundle"]
    index_path = CAMPAIGN / paths["factorization_freeze_index"]
    telemetry_final = CAMPAIGN / paths["phase1_telemetry"]
    require(not bundle.exists() and not index_path.exists() and not telemetry_final.exists(), "Phase-I canonical output already exists")
    staging_root = CAMPAIGN / paths["staging_root"]
    quarantine_root = CAMPAIGN / paths["quarantine_root"]
    staging = staging_root / f"third-colon-fixed-p181-dixon-phase1-v3-{run_id}"
    telemetry = staging_root / f"third-colon-fixed-p181-dixon-phase1-telemetry-v3-{run_id}"
    telemetry.mkdir(parents=True, exist_ok=False)
    touched = [staging, telemetry, bundle, telemetry_final, index_path]
    phase_started = time.perf_counter()
    script_names = {
        "preprocess_fixed_p181_dixon_integer_system.py",
        "factor_fixed_p181_dixon_coefficients.py",
        "produce_fixed_p181_dixon_8digit_pilot.py",
        "replay_fixed_p181_dixon_8digit_independent.py",
    }
    try:
        assert_no_other_algebra_processes(script_names)
        tools = implementation["toolchain"]
        preprocessor = CAMPAIGN / "scripts/preprocess_fixed_p181_dixon_integer_system.py"
        factorizer = CAMPAIGN / "scripts/factor_fixed_p181_dixon_coefficients.py"
        pre = run_child(
            label="preprocessor",
            command=[tools["sage_executable"], "-python", str(preprocessor), "--staging-dir", str(staging), "--implementation-freeze", str(implementation_path)],
            target_script_name=preprocessor.name,
            telemetry_dir=telemetry,
            time_executable=tools["external_time_executable"],
            timeout_executable=tools["gtimeout_executable"],
            timeout_seconds=policy["phase1_total_wall_seconds_maximum"] - (time.perf_counter() - phase_started),
            maximum_rss=policy["phase1_child_rss_bytes_maximum"],
            require_seen=False,
        )
        factor = run_child(
            label="factorizer",
            command=[tools["python_executable"], str(factorizer), "--staging-dir", str(staging), "--implementation-freeze", str(implementation_path)],
            target_script_name=factorizer.name,
            telemetry_dir=telemetry,
            time_executable=tools["external_time_executable"],
            timeout_executable=tools["gtimeout_executable"],
            timeout_seconds=policy["phase1_total_wall_seconds_maximum"] - (time.perf_counter() - phase_started),
            maximum_rss=policy["phase1_child_rss_bytes_maximum"],
            require_seen=False,
        )
        expected = {"integer-system.bin", "integer-system.json", "factorization.bin", "factorization.json"}
        require({item.name for item in staging.iterdir()} == expected, "staged Phase-I file set drift")
        integer_receipt = json.loads((staging / "integer-system.json").read_text(encoding="utf-8"))
        factor_receipt = json.loads((staging / "factorization.json").read_text(encoding="utf-8"))
        require(integer_receipt.get("status") == "PASS_STAGED_CANONICAL_INTEGER_SYSTEM", "integer preprocessing did not pass")
        require(factor_receipt.get("status") == "PASS_STAGED_COEFFICIENT_ONLY_FACTORIZATION", "coefficient factorization did not pass")
        require(factor_receipt["declarations"].get("factorizer_b_payload_not_loaded") is True, "factorizer read exclusion absent")
        files_before_manifest = tree_hashes(staging)
        manifest = {
            "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-phase1-bundle.v1",
            "status": "PASS_PHASE1_BUNDLE_STAGED",
            "implementation_freeze_sha256": file_hash(implementation_path),
            "files": files_before_manifest,
            "declarations": {"coefficient_only": True, "no_arithmetic_modulo_181_squared": True},
        }
        write_exclusive_json(staging / "bundle-manifest.json", manifest)
        require(len(list(staging.iterdir())) == 5, "Phase-I bundle must contain exactly five files")
        for item in staging.iterdir():
            with item.open("rb") as handle:
                os.fsync(handle.fileno())
        fsync_directory(staging)
        require(time.perf_counter() - phase_started < policy["phase1_total_wall_seconds_maximum"], "Phase-I wall gate failed before promotion")
        promote_directory(telemetry, telemetry_final)
        promote_directory(staging, bundle)
        bundle_files = tree_hashes(bundle)
        telemetry_files = tree_hashes(telemetry_final)
        elapsed_before_index = time.perf_counter() - phase_started
        require(elapsed_before_index < policy["phase1_total_wall_seconds_maximum"], "Phase-I wall gate failed before index")
        index = {
            "schema": FACTOR_INDEX_SCHEMA,
            "status": "PASS_FACTORIZATION_FREEZE",
            "implementation_freeze": {"path": str(FREEZE_RELATIVE), "sha256": file_hash(implementation_path)},
            "bundle": {"path": str(bundle.relative_to(CAMPAIGN)), "files": bundle_files},
            "external_telemetry": {"path": str(telemetry_final.relative_to(CAMPAIGN)), "files": telemetry_files, "preprocessor": pre, "factorizer": factor},
            "physical_wall_seconds_before_index_fsync": elapsed_before_index,
            "declarations": {"coefficient_only": True, "factorizer_b_payload_not_loaded": True, "no_arithmetic_modulo_181_squared": True, "at_most_one_algebra_child": True},
            "claim_boundary": "This PASS freezes only a deterministic full-rank coefficient trace modulo 181. It computes no Dixon digit or QQ, colon, saturation, secant, nullcone, or HC4 result.",
        }
        write_exclusive_json(index_path, index)
        total = time.perf_counter() - phase_started
        if total > policy["phase1_total_wall_seconds_maximum"]:
            raise TimeoutError(f"Phase-I total physical wall {total} exceeded gate after index fsync")
        return {"status": index["status"], "factorization_freeze": str(index_path), "physical_wall_seconds": total}
    except Exception as error:
        quarantine_path = quarantine(touched, "phase1", run_id, error, quarantine_root)
        raise RuntimeError(f"Phase I failed closed; quarantine={quarantine_path}: {error}") from error


def validate_phase2_process(receipt_path: Path, binary_path: Path, expected_status: str) -> dict[str, object]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("status") == expected_status, f"process status is not {expected_status}")
    require(receipt["container"]["sha256"] == file_hash(binary_path), "process binary hash drift")
    require(receipt["declarations"].get("exactly_eight_digits") is True, "eight-digit declaration absent")
    require(receipt["declarations"].get("no_digit_nine") is True, "digit-nine exclusion absent")
    return receipt


def phase2(run_id: str) -> dict[str, object]:
    implementation_path, implementation = load_implementation()
    policy = implementation["policy"]
    paths = implementation["canonical_paths"]
    require(set(paths) == REQUIRED_CANONICAL_PATH_KEYS, "canonical path interface drift")
    index_path = CAMPAIGN / paths["factorization_freeze_index"]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    require(index.get("schema") == FACTOR_INDEX_SCHEMA and index.get("status") == "PASS_FACTORIZATION_FREEZE", "Phase-I freeze absent")
    require(index["implementation_freeze"]["sha256"] == file_hash(implementation_path), "Phase-I freeze chain drift")
    bundle = CAMPAIGN / index["bundle"]["path"]
    for name, expected in index["bundle"]["files"].items():
        require(file_hash(bundle / name) == expected, f"Phase-I frozen file drift: {name}")

    staging_root = CAMPAIGN / paths["staging_root"]
    quarantine_root = CAMPAIGN / paths["quarantine_root"]
    producer_stage = staging_root / f"third-colon-fixed-p181-dixon-producer-v3-{run_id}"
    independent_stage = staging_root / f"third-colon-fixed-p181-dixon-independent-v3-{run_id}"
    telemetry_stage = staging_root / f"third-colon-fixed-p181-dixon-phase2-telemetry-v3-{run_id}"
    producer_final = CAMPAIGN / paths["producer_bundle"]
    independent_final = CAMPAIGN / paths["independent_bundle"]
    telemetry_final = CAMPAIGN / paths["phase2_telemetry"]
    terminal_path = CAMPAIGN / paths["terminal_receipt"]
    touched = [producer_stage, independent_stage, telemetry_stage, producer_final, independent_final, telemetry_final, terminal_path]
    require(not any(path.exists() for path in touched), "Phase-II prospective output already exists")
    telemetry_stage.mkdir(parents=True, exist_ok=False)
    scripts = {
        "preprocess_fixed_p181_dixon_integer_system.py",
        "factor_fixed_p181_dixon_coefficients.py",
        "produce_fixed_p181_dixon_8digit_pilot.py",
        "replay_fixed_p181_dixon_8digit_independent.py",
    }
    try:
        assert_no_other_algebra_processes(scripts)
        tools = implementation["toolchain"]
        producer_source = CAMPAIGN / "scripts/produce_fixed_p181_dixon_8digit_pilot.py"
        independent_source = CAMPAIGN / "scripts/replay_fixed_p181_dixon_8digit_independent.py"
        producer_time = run_child(
            label="producer",
            command=[tools["python_executable"], str(producer_source), "--staging-dir", str(producer_stage), "--implementation-freeze", str(implementation_path), "--factorization-freeze", str(index_path)],
            target_script_name=producer_source.name,
            telemetry_dir=telemetry_stage,
            time_executable=tools["external_time_executable"], timeout_executable=tools["gtimeout_executable"],
            timeout_seconds=policy["phase2_process_wall_seconds_maximum"], maximum_rss=policy["phase2_process_rss_bytes_maximum"], require_seen=True,
        )
        require(producer_time["real_seconds"] <= policy["phase2_process_wall_seconds_maximum"], "producer external wall gate failed")
        producer_receipt = validate_phase2_process(producer_stage / "producer-digits.json", producer_stage / "producer-digits.bin", "PASS_PRODUCER_FIXED_P181_DIXON_8DIGIT_PILOT")
        promote_directory(producer_stage, producer_final)
        independent_time = run_child(
            label="independent",
            command=[tools["sage_executable"], "-python", str(independent_source), "--staging-dir", str(independent_stage), "--implementation-freeze", str(implementation_path), "--factorization-freeze", str(index_path), "--producer-dir", str(producer_final)],
            target_script_name=independent_source.name,
            telemetry_dir=telemetry_stage,
            time_executable=tools["external_time_executable"], timeout_executable=tools["gtimeout_executable"],
            timeout_seconds=policy["phase2_process_wall_seconds_maximum"], maximum_rss=policy["phase2_process_rss_bytes_maximum"], require_seen=True,
        )
        require(independent_time["real_seconds"] <= policy["phase2_process_wall_seconds_maximum"], "independent external wall gate failed")
        independent_receipt = validate_phase2_process(independent_stage / "independent-replay.json", independent_stage / "independent-replay.bin", "PASS_INDEPENDENT_FIXED_P181_DIXON_8DIGIT_PILOT")
        promote_directory(independent_stage, independent_final)
        promote_directory(telemetry_stage, telemetry_final)
        producer_tail = [item["core_digit_seconds"] for item in producer_receipt["digit_telemetry"]]
        independent_tail = [item["core_digit_seconds"] for item in independent_receipt["digit_telemetry"]]
        per_digit = [max(producer_tail[index], independent_tail[index]) for index in range(DIGITS)]
        tail = max(per_digit[4:8])
        projection = 120 * tail
        band = "STRONG_FULL_LIFT_SIGNAL" if projection <= 1_800 else ("INTERMEDIATE_FULL_LIFT_SIGNAL" if projection <= 7_200 else "STOP_THROUGHPUT_SIGNAL")
        terminal = {
            "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-8digit-terminal.v1",
            "status": "PASS_INDEPENDENT_FIXED_P181_DIXON_8DIGIT_PILOT",
            "terminal_band": band,
            "implementation_freeze": {"path": str(FREEZE_RELATIVE), "sha256": file_hash(implementation_path)},
            "factorization_freeze": {"path": str(FACTOR_INDEX_RELATIVE), "sha256": file_hash(index_path)},
            "producer_bundle": {"path": str(producer_final.relative_to(CAMPAIGN)), "files": tree_hashes(producer_final)},
            "independent_bundle": {"path": str(independent_final.relative_to(CAMPAIGN)), "files": tree_hashes(independent_final)},
            "external_telemetry": {"path": str(telemetry_final.relative_to(CAMPAIGN)), "files": tree_hashes(telemetry_final), "producer": producer_time, "independent": independent_time},
            "timing_projection": {"conservative_core_digit_seconds": per_digit, "tail_seconds": tail, "T_120_seconds": projection, "band": band},
            "declarations": {"exactly_eight_digits": True, "no_digit_nine": True, "two_frozen_implementations_agree": True, "finite_p_adic_certificate_only": True},
            "claim_boundary": "This bounded two-implementation PASS is not a rational solution, QQ identity, ideal membership, colon, saturation, secant closure, nullcone containment, or HC4 proof.",
        }
        write_exclusive_json(terminal_path, terminal)
        return {"status": terminal["status"], "terminal_band": band, "terminal_receipt": str(terminal_path)}
    except Exception as error:
        quarantine_path = quarantine(touched, "phase2", run_id, error, quarantine_root)
        raise RuntimeError(f"Phase II failed closed; quarantine={quarantine_path}: {error}") from error


DIGITS = 8


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("phase1", "phase2", "all"), required=True)
    parser.add_argument("--run-id", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{os.getpid()}")
    args = parser.parse_args()
    results = []
    if args.phase in ("phase1", "all"):
        results.append(phase1(args.run_id))
    if args.phase in ("phase2", "all"):
        results.append(phase2(args.run_id))
    print(json.dumps({"status": "PASS_GATED_WRAPPER", "results": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
