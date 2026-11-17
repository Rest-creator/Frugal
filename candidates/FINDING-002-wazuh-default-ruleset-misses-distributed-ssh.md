# Finding #002: Wazuh's default correlation ruleset also misses the distributed SSH brute-force

**Status:** Open (ready for IGM — not yet picked up by any generator)
**Source tool:** Wazuh manager (v4.12.0), default ruleset, running on
`mywealth-vm`
**Type:** false_negative
**Produced by:** `lab/wazuh/enroll_agent.sh` + a manual run of
`docker compose ... up attacker1 attacker2 attacker3` against the
enrolled `victim` agent, 2026-11-17

## Evidence

Scenario: 3 attacker containers (10.211.55.21/22/23), each making 3
failed SSH logins against `labuser@victim` (9 total attempts against one
account). The victim host is enrolled as Wazuh agent `victim`.

Manager's `alerts.json` for this run: 9x rule 5760 ("sshd: authentication
failed", one per attempt, correctly attributed to each attacker's own
source IP), 0x any correlation/brute-force rule (5551, 5710, 5712, 5716,
5720, 5763, ...).

Control comparison, same account, same total attempt count, single
source IP (`ATTEMPTS=10` from one attacker container): triggered rule
5551 ("PAM: Multiple failed logins in a small period of time", level 10)
and rule 5763 ("sshd: brute force trying to get access to the system",
level 10).

## Root cause

Wazuh's default SSH brute-force correlation rules key their
frequency/timeframe thresholds on `srcip` (same as this project's own
original baseline detector in Finding #001). A distributed attack where
each source IP individually stays under that per-source threshold
produces no escalated alert, even though the account-level total is
identical to a pattern that *would* escalate from a single source.

This is the same structural limitation Finding #001 described, now
independently confirmed against a real, independent, production security
tool's own out-of-the-box configuration — not just the hand-written
baseline tool this project built for Sprint 1.

## Expected improvement (for IGM, once it targets Wazuh)

A custom Wazuh correlation rule (or an `<if_matched_sid>`-based composite
rule) that aggregates rule 5760 occurrences **per destination account**
across all `srcip` values within a time window, analogous to CAND-001's
account-wide correlation for the log-based detector. This would live in
the manager's local rules (`/var/ossec/etc/rules/local_rules.xml`), which
is itself a strong candidate for Frugal's deploy_actor pattern: a
rule-file diff IGM proposes, IEM evaluates against a replay of this exact
scenario, and deploy_actor pushes to the manager with rollback via the
version ledger — the same mechanism already proven for CAND-001, just
targeting a different tool.

## Reproduction

```
./lab/wazuh/setup_wazuh_stack.sh ~/Projects/wazuh-docker
./lab/wazuh/enroll_agent.sh frugal-victim victim
docker compose -f lab/compose/docker-compose.yml up --build attacker1 attacker2 attacker3
# then inspect single-node-wazuh.manager-1:/var/ossec/logs/alerts/alerts.json
```
