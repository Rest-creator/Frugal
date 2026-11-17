#!/usr/bin/env python3
"""Baseline SSH brute-force detector — V1's starting tool.

Flags an IP as an attacker if it has >= THRESHOLD failed login attempts
against a single account. This is exactly the limitation described in
Docs/Research V1.md Section 2A: it catches a single IP hammering one
account, but misses the same account being hit by several IPs each
staying under the per-IP threshold.

This file is the pristine reference artifact — it is never overwritten by
deploy_actor. The deploy actor's actual live/mutable copy lives at
./live.py (gitignored; seeded from this file on first deploy). See
Docs/DECISIONS_LOG.md ADR-008.

Usage: detect.py <path-to-auth.log> [threshold]
"""
import re
import sys
from collections import defaultdict

FAILED_RE = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\d+\.\d+\.\d+\.\d+)"
)


def analyze(log_path: str, threshold: int):
    per_ip = defaultdict(lambda: defaultdict(int))  # ip -> user -> count
    with open(log_path) as f:
        for line in f:
            m = FAILED_RE.search(line)
            if m:
                per_ip[m.group("ip")][m.group("user")] += 1

    alerts = []
    for ip, users in per_ip.items():
        for user, count in users.items():
            if count >= threshold:
                alerts.append({"ip": ip, "user": user, "failed_attempts": count})

    return {"per_ip_failed_counts": per_ip, "alerts": alerts}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: detect.py <path-to-auth.log> [threshold]")
        sys.exit(1)

    log_path = sys.argv[1]
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    result = analyze(log_path, threshold)

    print(f"Threshold: {threshold} failed attempts from the same IP against the same user\n")
    print("Per-IP failed attempt counts:")
    for ip, users in result["per_ip_failed_counts"].items():
        for user, count in users.items():
            print(f"  {ip} -> {user}: {count}")

    print("\nAlerts (per-IP threshold exceeded):")
    if result["alerts"]:
        for a in result["alerts"]:
            print(f"  ALERT: {a['ip']} exceeded threshold against {a['user']} ({a['failed_attempts']} attempts)")
    else:
        print("  (none) -- this is the expected miss: a distributed attack stays under the per-IP threshold.")
