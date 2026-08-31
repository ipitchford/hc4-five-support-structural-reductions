#!/usr/bin/env python3
"""Fail-closed Singular subprocess runner with process-group timeouts."""

from __future__ import annotations

import os
import resource
import signal
import subprocess
import time


def run_singular_process(source: str, timeout: int) -> dict[str, object]:
    """Run Singular and terminate its whole process group on timeout.

    ``RUSAGE_CHILDREN`` is recorded for continuity, but may omit CPU and RSS of
    delegated worker descendants.  Wall time is the authoritative cost metric.
    """

    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    process = subprocess.Popen(
        ["Singular", "-q"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    process_group_terminated = False
    forced_kill = False
    try:
        stdout, stderr = process.communicate(input=source, timeout=timeout)
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
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "stdout": stdout,
        "stderr": stderr,
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
    }
