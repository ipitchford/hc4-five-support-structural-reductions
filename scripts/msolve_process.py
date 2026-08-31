#!/usr/bin/env python3
"""Fail-closed msolve subprocess runner with process-group timeouts."""

from __future__ import annotations

import os
import resource
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from collections.abc import Sequence


def run_msolve_process(
    source: str,
    timeout: int,
    threads: int = 1,
    verbose: int = 1,
    extra_args: Sequence[str] = (),
) -> dict[str, object]:
    """Run msolve on a temporary input and retain exact output and telemetry."""

    if verbose not in (0, 1, 2):
        raise ValueError("msolve verbosity must be 0, 1, or 2")

    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="hc4-msolve-") as directory_name:
        directory = Path(directory_name)
        input_path = directory / "system.ms"
        output_path = directory / "result.out"
        input_path.write_text(source, encoding="ascii")
        command = [
                "msolve",
                "-f",
                str(input_path),
                "-o",
                str(output_path),
                "-t",
                str(threads),
                "-v",
                str(verbose),
                "--random-seed",
                "0",
                *extra_args,
            ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        process_group_terminated = False
        forced_kill = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            process_group_terminated = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=1.0)
            except subprocess.TimeoutExpired:
                forced_kill = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
        output = output_path.read_text(encoding="ascii") if output_path.exists() else ""

    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "stdout": stdout,
        "stderr": stderr,
        "solver_output": output,
        "return_code": None if timed_out else process.returncode,
        "timed_out": timed_out,
        "process_group_terminated": process_group_terminated,
        "forced_group_kill": forced_kill,
        "wall_seconds": time.perf_counter() - started,
        "child_user_seconds_immediate_scope": after.ru_utime - before.ru_utime,
        "child_system_seconds_immediate_scope": after.ru_stime - before.ru_stime,
        "maximum_rss_native_immediate_scope": after.ru_maxrss,
        "resource_accounting": (
            "wall time authoritative; CPU/RSS counters may omit delegated "
            "worker descendants"
        ),
        "extra_args": list(extra_args),
    }
