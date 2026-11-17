# Finding #001: Baseline SSH detector misses distributed brute-force

**Status:** Open (ready for IGM — IGM not yet implemented)
**Source tool:** `lab/tools/baseline-ssh-detector/detect.py`
**Type:** false_negative
**Produced by:** `lab/scenarios/seed_distributed_ssh.sh`, run 2026-11-17

## Evidence

Scenario: 3 attacker containers (10.211.55.21/22/23), each making 3 failed
SSH login attempts against `labuser@victim` (9 total failed attempts
against one account), captured in `lab/logs/victim-auth.log`.

Detector output (threshold=5, per-IP):
```
Per-IP failed attempt counts:
  10.211.55.23 -> labuser: 3
  10.211.55.21 -> labuser: 3
  10.211.55.22 -> labuser: 3

Alerts (per-IP threshold exceeded):
  (none)
```

## Root cause

`detect.py` only aggregates failed attempts per (ip, user) pair. A
distributed attack where each source IP stays under the per-IP threshold
produces no alert, even though the account-level total (9 attempts) is
clearly anomalous.

## Expected improvement (for IGM, once implemented)

Correlate failed attempts **per account across all source IPs** within a
time window, in addition to (not instead of) the existing per-IP check —
this is the exact improvement described in Docs/Research V1.md §2A.

## Reproduction

```
./lab/scenarios/seed_distributed_ssh.sh
```
