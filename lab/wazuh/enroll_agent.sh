#!/bin/bash
# Enrolls a running Frugal lab container (e.g. the victim host) as a Wazuh
# agent against the single-node stack set up by setup_wazuh_stack.sh.
#
# Bakes in three fixes discovered the hard way while doing this by hand:
#   1. The agent .deb depends on lsb-release, not pulled in automatically
#      by a minimal container image -- install it first or dpkg -i fails
#      and the postinst (which substitutes the manager address into
#      ossec.conf) never runs.
#   2. Because of (1), WAZUH_MANAGER=... at `dpkg -i` time can silently not
#      take effect; this script fixes the <address> directly regardless.
#   3. Re-running this against a container that was already enrolled under
#      the same name causes "Duplicate agent name" -- remove the stale
#      agent entry on the manager first, keyed by name, before enrolling.
#
# Usage: lab/wazuh/enroll_agent.sh <container_name> [agent_name]
set -euo pipefail

CONTAINER="${1:?usage: enroll_agent.sh <container_name> [agent_name]}"
AGENT_NAME="${2:-$CONTAINER}"
MANAGER_CONTAINER="single-node-wazuh.manager-1"
WAZUH_NET="single-node_default"
WAZUH_VERSION="4.12.0"

echo "== Connecting $CONTAINER to $WAZUH_NET =="
docker network connect "$WAZUH_NET" "$CONTAINER" 2>/dev/null || echo "(already connected)"

echo "== Installing wazuh-agent inside $CONTAINER =="
docker exec "$CONTAINER" bash -c "
  apt-get update -qq
  apt-get install -y -qq curl lsb-release
  test -f /tmp/wazuh-agent.deb || curl -so /tmp/wazuh-agent.deb https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_${WAZUH_VERSION}-1_amd64.deb
  dpkg -i /tmp/wazuh-agent.deb || true
  dpkg --configure -a || true
"

echo "== Pointing agent at wazuh.manager =="
docker exec "$CONTAINER" sed -i 's/<address>MANAGER_IP<\/address>/<address>wazuh.manager<\/address>/' /var/ossec/etc/ossec.conf

echo "== Removing any stale agent named '$AGENT_NAME' on the manager =="
existing_id=$(docker exec "$MANAGER_CONTAINER" /var/ossec/bin/manage_agents -l 2>/dev/null | grep -F "Name: $AGENT_NAME," | sed -n 's/.*ID: \([0-9]*\),.*/\1/p' || true)
if [ -n "$existing_id" ]; then
  echo "Found existing agent ID $existing_id, removing..."
  printf 'R\n%s\ny\n\\q\n' "$existing_id" | docker exec -i "$MANAGER_CONTAINER" /var/ossec/bin/manage_agents >/dev/null 2>&1 || true
fi

echo "== Enrolling $CONTAINER as '$AGENT_NAME' =="
docker exec "$CONTAINER" bash -c "
  rm -f /var/ossec/etc/client.keys
  /usr/bin/env HOSTNAME='$AGENT_NAME' /var/ossec/bin/agent-auth -m wazuh.manager -A '$AGENT_NAME'
  /var/ossec/bin/wazuh-control restart
"

sleep 3
echo "== Agent status on manager =="
docker exec "$MANAGER_CONTAINER" /var/ossec/bin/agent_control -l | grep -F "Name: $AGENT_NAME,"
