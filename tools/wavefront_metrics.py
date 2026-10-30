#!/usr/bin/env python3
"""Validate a serial synchronous benchmark round. Times are monotonic seconds.

Input JSON: {t0, t1, deadline, requests: [{id, phase, started_at,
completed_at, status}]}. phase is warmup or measurement; completed_at may be
null for a pending/timeout request. Invalid rounds retain diagnostic statistics.
This validates accounting, not image correctness, variant execution or PR gates.
"""
import argparse
import json
import math
import statistics
from pathlib import Path


def summarize(round_record):
    t0, t1, deadline = (round_record[name] for name in ("t0", "t1", "deadline"))
    if not all(isinstance(t, (int, float)) and math.isfinite(t)
               for t in (t0, t1, deadline)) or not t0 < t1 <= deadline:
        raise ValueError("invalid measurement window")
    if not math.isclose(t1 - t0, 30.0, abs_tol=1e-6):
        raise ValueError("measurement window must last 30 seconds")
    if not math.isclose(deadline - t1, 2.0, abs_tol=1e-6):
        raise ValueError("tail deadline must be t1 + 2 seconds")

    reasons, cohort, seen, ordered = [], [], set(), []
    for request in round_record["requests"]:
        identity = request["id"]
        if identity in seen:
            raise ValueError("duplicate request id")
        seen.add(identity)
        start, end = request["started_at"], request["completed_at"]
        if not isinstance(start, (int, float)) or not math.isfinite(start):
            raise ValueError("invalid start time")
        if end is not None and (not isinstance(end, (int, float))
                                or not math.isfinite(end) or end < start):
            raise ValueError("invalid completion time")
        phase, status = request["phase"], request["status"]
        if phase not in ("warmup", "measurement"):
            raise ValueError("unknown request phase")
        if status not in ("success", "failure", "cancelled", "timeout", "pending"):
            raise ValueError("unknown request status")
        if status in ("success", "failure", "cancelled") and end is None:
            reasons.append(f"{identity}: terminal status without completion")
        if status != "success":
            reasons.append(f"{identity}: {status}")
        if phase == "warmup":
            if start >= t0 or end is None or end > t0:
                reasons.append(f"{identity}: warmup not drained before measurement")
        else:
            if not t0 <= start < t1:
                reasons.append(f"{identity}: submission outside measurement window")
            else:
                cohort.append(request)
            if end is None or end > deadline:
                reasons.append(f"{identity}: incomplete at tail deadline")
        ordered.append(request)

    ordered.sort(key=lambda r: r["started_at"])
    for left, right in zip(ordered, ordered[1:]):
        if left["completed_at"] is None or right["started_at"] < left["completed_at"]:
            reasons.append(f"{right['id']}: overlapping synchronous calls")

    warmup = [r for r in ordered if r["phase"] == "warmup"]
    if not warmup or t0 - warmup[0]["started_at"] < 5.0:
        reasons.append("missing five-second warmup")
    if len(cohort) < 30:
        reasons.append("fewer than 30 measurement requests")
    successful = [r for r in cohort if r["status"] == "success"
                  and r["completed_at"] is not None and r["completed_at"] <= deadline]
    completed_in_window = sum(r["completed_at"] < t1 for r in successful)
    latencies = sorted(r["completed_at"] - r["started_at"] for r in successful)
    return {
        "valid": not reasons,
        "reasons": reasons,
        "request_count": len(cohort),
        "success_by_deadline": len(successful),
        "success_in_window": completed_in_window,
        "throughput_fps": completed_in_window / (t1 - t0),
        "median_seconds": statistics.median(latencies) if latencies else None,
        "p95_seconds": latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
        "statistics_are_diagnostic_only": bool(reasons),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    arguments = parser.parse_args()
    result = summarize(json.loads(arguments.record.read_text()))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
