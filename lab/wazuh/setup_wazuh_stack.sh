#!/bin/bash
# Stands up Wazuh's single-node stack (manager + indexer + dashboard) using
# Wazuh's own official wazuh-docker deployment, pinned to v4.12.0.
#
# Prerequisite this script does NOT set for you (requires root, and this
# repo doesn't assume passwordless sudo): the host's vm.max_map_count must
# be >= 262144 for the OpenSearch-based indexer. Run once, as a human:
#   sudo sysctl -w vm.max_map_count=262144
#   echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-wazuh.conf
#
# Usage: lab/wazuh/setup_wazuh_stack.sh [clone_dir]
set -euo pipefail

CLONE_DIR="${1:-$HOME/Projects/wazuh-docker}"
WAZUH_TAG="v4.12.0"

if [ "$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)" -lt 262144 ]; then
  echo "REFUSING TO START: vm.max_map_count is below 262144 (OpenSearch requirement)." >&2
  echo "Run: sudo sysctl -w vm.max_map_count=262144" >&2
  exit 1
fi

if [ ! -d "$CLONE_DIR/.git" ]; then
  echo "== Cloning wazuh-docker $WAZUH_TAG =="
  git clone https://github.com/wazuh/wazuh-docker.git -b "$WAZUH_TAG" --depth 1 "$CLONE_DIR"
else
  echo "== wazuh-docker already present at $CLONE_DIR =="
fi

cd "$CLONE_DIR/single-node"

# Not checking the certs directory's contents directly: the generator
# container locks it down to a uid the invoking user can't `ls` (a plain
# `ls -A` on it returns Permission denied, which an earlier version of
# this script misread as "empty" and regenerated certs needlessly on
# every re-run). Checking for an already-running manager is a reliable
# enough proxy for "certs already exist and are in use."
if docker ps --format '{{.Names}}' | grep -q '^single-node-wazuh.manager-1$'; then
  echo "== Stack already running, skipping cert generation =="
else
  echo "== Generating indexer SSL certs =="
  docker compose -f generate-indexer-certs.yml run --rm generator
fi

echo "== Starting Wazuh single-node stack =="
docker compose up -d

echo "== Waiting for indexer cluster health =="
for i in $(seq 1 30); do
  status=$(docker exec single-node-wazuh.indexer-1 curl -s -k -u admin:SecretPassword https://localhost:9200/_cluster/health 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
  if [ "$status" = "green" ] || [ "$status" = "yellow" ]; then
    echo "Indexer cluster status: $status"
    break
  fi
  sleep 5
done

echo "== Done. Manager: single-node-wazuh.manager-1, Indexer: single-node-wazuh.indexer-1, Dashboard: single-node-wazuh.dashboard-1 (https://<host>:443) =="
