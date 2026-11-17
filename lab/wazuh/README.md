# Wazuh integration (V1, mywealth-vm)

Per `Docs/DECISIONS_LOG.md` ADR-007, Wazuh's full stack (manager +
indexer + dashboard) was deferred off the primary dev machine to a VM
sized for it. `mywealth-vm` (25 CPU, 41GB RAM) was provisioned and this
is what's actually running there — proven, not just configured.

## One-time host prerequisite (requires root; not automated here)

```
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-wazuh.conf
```

OpenSearch (the indexer) refuses to start below this. `setup_wazuh_stack.sh`
checks for it and refuses to proceed rather than starting a stack that
will fail partway through.

## Usage

```
./lab/wazuh/setup_wazuh_stack.sh ~/Projects/wazuh-docker   # clones wazuh-docker v4.12.0, gens certs, starts the stack
./lab/wazuh/enroll_agent.sh frugal-victim victim           # installs + enrolls the victim container as a Wazuh agent
```

Both scripts are idempotent — safe to re-run; `enroll_agent.sh` removes
any stale agent registered under the same name before re-enrolling.

## What's proven

- Indexer cluster health: GREEN.
- Manager's Filebeat successfully shipping to the indexer.
- Dashboard reachable (302 redirect to its login page).
- Victim container enrolled as agent `victim`, shown `Active` by
  `agent_control -l` on the manager.
- Running the distributed-SSH scenario (3 attacker IPs x 3 attempts each)
  produces real alerts in the manager's `alerts.json`: rule 5760 ("sshd:
  authentication failed") fires per attempt, correctly attributed to each
  attacker's own IP.
- **Finding #002** (see `candidates/FINDING-002-wazuh-default-ruleset-misses-distributed-ssh.md`):
  Wazuh's own default correlation rule (5763, "sshd: brute force...",
  level 10) does NOT escalate for the distributed case (9 total attempts
  across 3 IPs), even though the exact same total from a single IP
  reliably triggers it — confirmed by a direct comparison run (one
  attacker alone sending 10 rapid attempts did trigger rule 5551/5763;
  three attackers sending 3 each, same account, did not trigger any
  correlation rule). This is the same structural gap Finding #001
  described for the hand-written baseline detector, now confirmed against
  a real, independent, production-grade tool's own default ruleset.

## What's NOT yet done

- No custom Wazuh correlation rule has been written for Finding #002 —
  that's IGM/IEM work for a future cycle, analogous to CAND-001 for the
  log-based detector, not done in this pass.
- Dashboard UI itself not exercised interactively (only checked for
  reachability); alert verification here was done via the manager's own
  `alerts.json` and `agent_control`/`manage_agents` CLI tools.
- Wazuh's own vulnerability-detection module (which would overlap with
  OpenVAS) not enabled/explored.
