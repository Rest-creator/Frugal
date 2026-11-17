# Frugal — Decisions Log (ADR-style)

## ADR-001: IGM and IEM are separate services with separate credentials
**Date:** 2026-11-17
**Decision:** IGM and IEM run as distinct processes/service identities with
distinct DB roles and distinct LLM API credentials, even though both call
the same provider. Neither can perform the other's role, and neither can
deploy to production.
**Why:** The improvement pipeline is Frugal's highest-risk attack surface —
an AI proposing changes to its own defensive tooling must not be able to
also certify or apply those changes. Least privilege / separation of duties.
**Status:** Accepted.

## ADR-002: Protected benchmarks are stored outside IGM/IEM write access
**Date:** 2026-11-17
**Decision:** The protected evaluation suite is a separate, hash-verified
store. IGM has no write credential to it. IEM verifies a hash against a
known-good manifest before every evaluation run and fails closed on mismatch.
Changes to it require a human-authored, human-reviewed commit.
**Why:** Prevents the subject under test (IGM, indirectly) from being able
to weaken the standard it is judged against.
**Status:** Accepted.

## ADR-003: Rule/script-based detection tools only for V1
**Date:** 2026-11-17
**Decision:** V1's assembled security tools (Wazuh, Suricata, auditd,
OpenVAS, Atomic Red Team) are chosen because their detection logic is
rule/text-based, not opaque ML models.
**Why:** Keeps IGM's candidate diffs human-inspectable and keeps IEM's
regression testing tractable. ML-model retraining is out of scope for V1.
**Status:** Accepted.

## ADR-004: IEM verdicts must be evidence-backed structured records, not
freeform LLM judgments
**Date:** 2026-11-17
**Decision:** Every IEM verdict is a structured record referencing concrete
benchmark/adaptive/regression execution results. Any LLM component in IEM
may summarize but does not generate the pass/fail itself.
**Why:** Avoids the "ungrounded output" failure mode for LLM-backed
evaluators, and keeps the evaluation loop auditable for drift across cycles.
**Status:** Accepted.

## ADR-005: Human approval gate before any production deployment
**Date:** 2026-11-17
**Decision:** A fourth actor (deploy) requires human sign-off recorded
against an approved verdict before any candidate reaches live tool config.
**Why:** Mandatory secure-design control for V1, not merely a scope
preference — matches both the research doc's stated V1 scope and
security-by-design review.
**Status:** Accepted.

## ADR-006: Suricata deployed via shared network namespace, not host bridge capture
**Date:** 2026-11-17
**Decision:** Suricata runs with `network_mode: "service:victim"` (sharing
the victim container's network namespace) rather than capturing on the
Docker bridge interface from the host.
**Why:** Host-level packet capture (`tcpdump`/Suricata on `br-*`) requires
`sudo`, which this dev environment does not have configured for
non-interactive use. Sharing the protected host's own network namespace is
also a standard host-based NIDS deployment pattern, not merely a
workaround — Suricata sees exactly the traffic the victim host sees.
**Status:** Accepted.

## ADR-007: OpenVAS and the full Wazuh stack (indexer + dashboard) deferred to a dedicated VM
**Date:** 2026-11-17
**Decision:** V1's lab integrates Suricata now. OpenVAS/Greenbone (NVT
feed sync routinely takes 1-3+ hours and pulls several GB on first run)
and Wazuh's full stack (the OpenSearch-based indexer alone typically wants
4GB+ RAM) are explicitly deferred, not attempted on the current dev
machine (6.4GB RAM available at decision time).
**Why:** User decision, made explicitly rather than silently skipped: the
heavier parts of V1's monitoring stack need a VM sized for them, and
starting a multi-hour feed sync or a resource-starved Wazuh stack on this
machine would produce an unverifiable "might be working" state — exactly
the Potemkin-tooling failure mode this project has avoided everywhere
else. Development of these two components moves to a VM with adequate
compute once provisioned.
**Status:** Accepted. Follow-up: stand up OpenVAS and full Wazuh
(manager + indexer + dashboard) on that VM and prove each the same way
Suricata was proven here (real scenario run, real alert observed).
