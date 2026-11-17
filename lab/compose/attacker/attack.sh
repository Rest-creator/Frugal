#!/bin/bash
# Attempts N failed SSH logins against TARGET_USER@TARGET_HOST, pausing
# briefly between attempts. Each attacker container has its own IP on the
# lab network, so this simulates one source in a distributed brute-force.
set -u

TARGET_HOST="${TARGET_HOST:-victim}"
TARGET_USER="${TARGET_USER:-labuser}"
ATTEMPTS="${ATTEMPTS:-3}"
SLEEP_SECS="${SLEEP_SECS:-2}"
ATTACKER_ID="${ATTACKER_ID:-unknown}"

echo "[attacker-${ATTACKER_ID}] starting: ${ATTEMPTS} attempts against ${TARGET_USER}@${TARGET_HOST}"

for i in $(seq 1 "$ATTEMPTS"); do
  sshpass -p "WrongPassword$i" ssh \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=5 \
    -o LogLevel=ERROR \
    "${TARGET_USER}@${TARGET_HOST}" "echo should-not-reach-here" 2>&1 | sed "s/^/[attacker-${ATTACKER_ID}] /"
  sleep "$SLEEP_SECS"
done

echo "[attacker-${ATTACKER_ID}] done"
