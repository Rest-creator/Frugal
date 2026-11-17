#!/bin/bash
# Same distributed-SSH scenario as seed_distributed_ssh.sh, but observed by
# Suricata (network layer) instead of the log-based baseline detector.
# Proves Suricata independently detects the distributed attack via
# connection-volume thresholding, without needing to read the (encrypted)
# SSH session content.
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../compose" && pwd)"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../suricata/output" && pwd)"

echo "== Starting victim + Suricata (sharing victim's network namespace) =="
docker compose -f "$COMPOSE_DIR/docker-compose.yml" up -d --build victim suricata
sleep 4

echo "== Running attackers (3 IPs, 3 attempts each) =="
docker compose -f "$COMPOSE_DIR/docker-compose.yml" up --build attacker1 attacker2 attacker3
sleep 2

echo "== Suricata alerts =="
if [ -f "$OUT_DIR/fast.log" ]; then
  cat "$OUT_DIR/fast.log"
else
  echo "(no fast.log found)"
fi

echo
echo "== Distinct source IPs Suricata observed hitting victim:22 =="
python3 - "$OUT_DIR/eve.json" <<'PYEOF'
import json
import sys

ips = set()
with open(sys.argv[1]) as f:
    for line in f:
        ev = json.loads(line)
        if ev.get("dest_ip") == "10.211.55.10" and ev.get("dest_port") == 22 and "src_ip" in ev:
            ips.add(ev["src_ip"])
print(sorted(ips))
PYEOF

echo
echo "== Tearing down =="
docker compose -f "$COMPOSE_DIR/docker-compose.yml" down -v
