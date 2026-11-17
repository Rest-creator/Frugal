#!/bin/bash
# Seeds the distributed-SSH-brute-force scenario end to end:
# 1. Bring up the lab (victim + 3 attackers on distinct IPs).
# 2. Let the attackers run their failed-login attempts.
# 3. Pull the victim's auth log out of the shared volume.
# 4. Run the baseline detector against it and show it misses the attack.
#
# Run from the repo root: ./lab/scenarios/seed_distributed_ssh.sh
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../compose" && pwd)"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../logs" && pwd)"
mkdir -p "$OUT_DIR"

echo "== Building and starting lab =="
docker compose -f "$COMPOSE_DIR/docker-compose.yml" up -d --build victim

echo "== Waiting for sshd to be ready =="
sleep 3

echo "== Running attackers (3 IPs, 3 attempts each) =="
docker compose -f "$COMPOSE_DIR/docker-compose.yml" up --build attacker1 attacker2 attacker3

echo "== Capturing victim sshd log =="
# sshd runs with -e (log to stderr) and no syslog daemon in this minimal
# image, so the container's own stderr/stdout is the log source of record.
docker logs frugal-victim > "$OUT_DIR/victim-auth.log" 2>&1

echo "== Captured log: $OUT_DIR/victim-auth.log =="
echo "== Running baseline detector (threshold=5, per IP) =="
python3 "$(dirname "${BASH_SOURCE[0]}")/../tools/baseline-ssh-detector/detect.py" "$OUT_DIR/victim-auth.log" 5

echo
echo "This is Finding #1 for Frugal: the baseline detector alerts per-IP only,"
echo "so 3 attackers x 3 attempts each (9 total against one account) produces"
echo "no alert. This is the exact IGM input described in Docs/Research V1.md."
