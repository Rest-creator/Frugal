#!/usr/bin/env python3
"""Orchestrator continuous loop (V1). Runs run_cycle() on an interval until
interrupted. This is a single-process polling loop standing in for a real
queue consumer (see ARCHITECTURE.md's Postgres-backed job table) — an
explicit, documented V1 simplification, not a silent substitute.

Usage: loop.py [interval_seconds]
"""
import sys
import time

from run_cycle import run_cycle

if __name__ == "__main__":
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(f"Orchestrator loop starting (interval={interval}s). Ctrl-C to stop.")
    try:
        while True:
            run_cycle()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nOrchestrator loop stopped.")
