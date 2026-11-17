# Frugal V1 — Architecture

Status: Draft (Sprint 0 — pre-implementation). See `Docs/Research V1.md` for the
original concept and `Docs/DECISIONS_LOG.md` for ADRs.

## 1. Guiding constraint

Frugal's own improvement pipeline (IGM → IEM → deploy) is the highest-risk
attack surface in this system: it is a mechanism that proposes and (if
approved) applies changes to the security tooling defending the
infrastructure. Every architectural choice below exists to keep that
pipeline auditable, separated, and non-self-certifying. Treat all IGM output
as **untrusted input**, never as trusted code, all the way through IEM.

## 2. Components

```
                     PROTECTED LAB ENVIRONMENT
                              |
                    Security Monitoring Tools
                   (Wazuh, Suricata, auditd, OpenVAS)
                              |
                        Findings / Events
                              |
                              v
                    +-------------------+
                    |   ORCHESTRATOR    |  (FastAPI, Postgres-backed job table)
                    +-------------------+
                      |              |
                      v              v
               +-----------+   +-----------+
               |    IGM    |   |    IEM    |
               | generate  |   | evaluate  |
               |   only    |   |   only    |
               +-----------+   +-----------+
                      |              ^
                      v              |
               candidates/       scenario harness
               (staged, not      + protected benchmarks
                live config)     (integrity-sealed)
                                      |
                                      v
                               verdict + evidence
                               (structured, logged)
                                      |
                                      v
                            HUMAN APPROVAL GATE
                                      |
                                      v
                          DEPLOY ACTOR (separate identity)
                                      |
                                      v
                       live tool config + version/rollback ledger
```

## 3. Separation of duties (hard requirement, not convention)

Three distinct service identities, distinct credentials, distinct filesystem/DB
permissions — no shared role:

| Actor | Can read | Can write | Cannot do |
|---|---|---|---|
| **IGM** | findings, current tool configs/rules, past evaluation history | `candidates/` staging area only | write to live tool config, write to protected benchmark store, self-approve |
| **IEM** | `candidates/`, protected benchmarks, adaptive test suite, scenario harness | evaluation verdicts/evidence log | modify candidates, modify protected benchmarks, deploy |
| **Deploy actor** | approved verdicts + human sign-off record | live tool config, version ledger | generate candidates, author or alter evaluation criteria |

This maps directly to least-privilege/separation-of-duties guidance (Software
Security Engineering guide) and is why IGM and IEM are separate services with
separate credentials, not two prompts in one process.

## 4. Protected benchmark integrity

The protected evaluation suite (Section 2B of the research doc) is the
reference IGM is judged against. It must be:
- stored outside IGM's write access entirely (separate repo/store, IGM has no
  credential to it),
- content-hashed/signed, with any change requiring human-authored commit +
  review — never an IGM- or IEM-proposed edit,
- loaded by IEM at evaluation time with a hash check against the known-good
  manifest; mismatch = evaluation hard-fails closed.

Adaptive tests may be proposed by Frugal (per the research doc) but still
land in a human-reviewed PR before being added to the suite IEM runs against
— "Frugal proposes a new adaptive test" is itself an IGM-shaped action and
goes through the same approval gate, not a silent self-expansion of its own
test suite.

## 5. Grounded, auditable evaluation (not a bare LLM opinion)

IEM's verdict is not "the model says this looks better." It must be:
- a structured record: `{candidate_id, benchmark_results[], adaptive_results[],
  regression_results[], resource_metrics, verdict, evidence_refs}`,
- backed by actual execution of the scenario harness (old tool vs. candidate,
  same inputs) — the LLM component of IEM (if any) may summarize/explain, but
  pass/fail is derived from harness output, not generated text,
- logged in full for every cycle, including rejections, so drift in
  acceptance criteria across cycles is detectable (this is the LLM
  behavioral-contract-drift risk from repeated-cycle systems — log enough to
  audit it after the fact).

## 6. Stack

- **Language/runtime:** Python 3.12, FastAPI for the orchestrator/API layer.
- **State:** PostgreSQL — findings, candidates, evaluation results, version +
  rollback ledger, approval records. One schema per actor's write scope
  (enforced via DB roles, not just app-level checks).
- **LLM backend:** Anthropic Claude API — IGM and IEM each use separate API
  keys/service accounts even though they share a provider, so credential
  compromise of one doesn't grant the other's privileges.
- **Sandbox/scenario runner:** Docker-isolated replay environment, deterministic
  scripts (not LLM-authored at run time) that feed identical inputs to the
  current tool and the candidate and diff detection output.
- **Monitoring/detection tools assembled for V1:**
  - `auditd` + `journald`/`rsyslog` — host auth/event logging (the SSH example
    in the research doc).
  - Wazuh (or OSSEC) — host IDS, rule-based so IGM's diffs stay inspectable.
  - Suricata — network IDS, community + custom rules.
  - OpenVAS/Greenbone or Trivy — vulnerability scanning (feeds proactive
    trigger).
  - Atomic Red Team / Caldera — authorized attack simulation in the isolated
    lab only, for proactive weakness discovery.
  - Wazuh's OpenSearch/dashboard stack doubles as the findings source IGM
    reads from.
- **Why rule/text-based detection tools:** IGM's V1 scope is generating/
  modifying tools, rules, and scripts — not retraining opaque ML models.
  Rule-based tools keep every candidate diff human-reviewable and keep IEM's
  regression testing tractable.

## 7. Sprint-1 gate (no Potemkin tooling)

Before V1 is considered "started" (per SDLC guide's greenfield gate), the
following must be wired AND actually exercised in CI, not just configured:
- IEM's scenario harness runs a real old-vs-candidate comparison against at
  least one seeded scenario.
- A protected-benchmark integrity check actually fails closed on a tampered
  file (test this deliberately).
- The human-approval gate actually blocks deployment absent sign-off (test
  this deliberately, don't assume the code path works).

## 8. Explicit non-goals for V1

- No modification of Frugal's own source code/architecture by IGM.
- No autonomous production deployment without human sign-off.
- No ML/black-box detector retraining — rule/script-level improvements only.
- No internet-facing deployment — isolated lab network only.
