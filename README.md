# Frugal

AI-driven cybersecurity defence system with recursive, tool-level
self-improvement. See `Docs/Research V1.md` for the concept, `ARCHITECTURE.md`
for the V1 design, `Docs/DECISIONS_LOG.md` for ADRs, and
`Docs/IGM-IEM-SPEC.md` for the IGM/IEM/deploy-actor interface contract.

## Status

Sprint 1 in progress.

- Lab: isolated Docker Compose lab up; `lab/scenarios/seed_distributed_ssh.sh`
  run end-to-end (3 attacker IPs, 9 failed logins against one account; the
  baseline per-IP detector correctly fails to alert, producing
  `candidates/FINDING-001-*`).
- IEM (partial): `iem/integrity_check.py` verifies `benchmarks/protected/`
  against a sealed `manifest.json` (sha256 per file) and **fails closed** —
  proven against hash-tampering, an untracked extra file, and a missing
  file, each exercised and confirmed to refuse evaluation. `iem/run_evaluation.py`
  refuses to run at all if integrity fails, and otherwise runs the one
  protected benchmark (`PROT-001-distributed-ssh-bruteforce`) against a
  candidate detector and emits an evidence-backed Verdict record (see
  Docs/IGM-IEM-SPEC.md). Run against the known-bad baseline detector, it
  correctly rejects it with the harness output as evidence — not a bare
  opinion.
- IGM (partial): `igm/generate_candidate.py` reads `FINDING-001`, produces
  `candidates/CAND-001-distributed-ssh-bruteforce/` (a new detector adding
  account-wide correlation across distinct source IPs, on top of the
  unchanged per-IP check, plus a `candidate.json` rationale record). Run
  through `iem/run_evaluation.py`, it is correctly **approved_for_human_review**
  — confirmed by actual run, not asserted. A direct check against a
  synthetic single-IP log confirms the original per-IP detection still
  fires (no regression).
- Deploy actor + human-approval gate: `deploy_actor/human_approval.py`
  writes the only HumanApproval record, and refuses to approve any verdict
  IEM didn't itself mark `approved_for_human_review` (tested: tried to
  approve a rejected verdict, refused). `deploy_actor/deploy.py` requires
  BOTH an approved verdict AND a matching approval record and refuses
  otherwise (tested: ran deploy before approval existed, blocked with exit
  1). On success it backs up the live tool, writes a `version_ledger.jsonl`
  entry, and copies the candidate into place — **never onto the pristine
  reference tool itself**, but onto a gitignored sibling `live.py`
  (seeded from the reference on first deploy; see ADR-008). A prior
  version wrote directly onto `lab/tools/baseline-ssh-detector/detect.py`
  and that mutated state got committed as if it were the pristine
  baseline, breaking the scenario for a fresh clone — caught and fixed
  while standing the repo up on `mywealth-vm`.
  `deploy_actor/rollback.py`
  restores the backup from a ledger entry — tested end to end: deployed
  CAND-001, confirmed the live detector now alerts on the fixture, rolled
  back, confirmed it misses again (old behavior restored), then
  re-deployed to leave the lab in its improved end-state.
- Orchestrator (partial): `orchestrator/run_cycle.py` drives the Finding
  -> IGM -> IEM -> (human approval, out of band) -> Deploy state machine
  one step per pass, persisted in `orchestrator/state.json` (a JSON file
  standing in for the Postgres `jobs` table — documented V1 simplification,
  same schema either way). `orchestrator/loop.py` wraps it on an interval.
  Critically: the orchestrator never writes an approval itself — it only
  checks whether one already exists. Proven across repeated cycles: it
  advanced new -> igm_done -> awaiting_approval, then **held** at
  awaiting_approval on repeated passes with no approval file present, and
  only deployed on the pass immediately after a human ran
  `human_approval.py` themselves. (An attempt to have the AI assistant run
  that approval step on the user's behalf was correctly refused by the
  session's own auto-mode classifier as undermining the human-approval
  control — the user ran it themselves.)
- IGM (LLM-backed, built but NOT yet exercised against a real model): a
  second generator, `igm/generate_candidate_llm.py`, calls the Anthropic
  Messages API directly via stdlib `urllib` (no `anthropic` package — this
  dev environment has no `pip`). Same read/write contract as the
  deterministic generator. It is wired to refuse rather than fabricate a
  candidate if `ANTHROPIC_API_KEY` is unset — proven: ran it with no key
  set, it printed a clear refusal and exited non-zero, producing no
  candidate file. It has not yet been run against a live API call (no key
  was available in this environment this session), so "LLM-backed IGM
  works end to end" is **not yet proven**, only that it fails safely when
  it can't run — do not treat this as done until it's been run once with
  a real key and its output has gone through `iem/run_evaluation.py` like
  any other candidate.
- Suricata (proven): `lab/compose/docker-compose.yml`'s `suricata`
  service shares the victim's network namespace (ADR-006) and runs
  `lab/suricata/rules/local.rules` (a connection-volume threshold rule, a
  genuinely different detection surface from the log-based detector,
  since SSH traffic is encrypted and the content can't be read). Run via
  `lab/scenarios/seed_distributed_ssh_suricata.sh`: confirmed Suricata saw
  SSH connections from all 3 distinct attacker IPs and correctly fired one
  alert once their combined connection volume to the victim crossed the
  threshold — i.e. it independently detects the same distributed attack,
  without needing IGM's account-correlation fix at all, because its
  threshold already tracks by destination rather than by source.
- OpenVAS and Wazuh's full stack (indexer + dashboard) deliberately
  **deferred to a dedicated VM**, by explicit user decision — see
  ADR-007. OpenVAS's feed sync routinely takes 1-3+ hours on first run;
  Wazuh's indexer alone typically wants 4GB+ RAM against the 6.4GB
  available on this dev machine at the time of the decision. Starting
  either here would have produced an unverifiable "might be working"
  state, which this project has avoided everywhere else.
- Not yet implemented: adaptive-test proposal flow, Postgres-backed DB
  roles (current separation of duties is enforced by which script may
  write which file, not DB grants — documented limitation).

## Layout

- `orchestrator/` — job-loop service (FastAPI + Postgres-backed queue).
- `igm/` — Improvement Generation Mechanism service. Generate-only.
- `iem/` — Improvement Evaluation Mechanism service. Evaluate-only.
- `deploy_actor/` — separate deploy/rollback service. No generation/eval rights.
- `benchmarks/protected/` — hash-sealed protected test suite. Human-edit only.
- `benchmarks/adaptive/` — adaptive test suite (proposals land here only
  after human review of an `adaptive_test_proposal` candidate).
- `scenario_harness/` — deterministic old-vs-candidate replay runner.
- `candidates/` — IGM's staging area for proposed tool/rule changes.
- `lab/` — isolated Docker Compose lab environment + monitoring tools
  (Wazuh, Suricata, auditd, OpenVAS, Atomic Red Team).

## Lab usage

```
./lab/scenarios/seed_distributed_ssh.sh   # build, attack, detect, teardown is manual
docker compose -f lab/compose/docker-compose.yml down -v   # teardown
```

Full Wazuh/Suricata/OpenVAS integration is deferred — the baseline detector
here is a minimal stand-in just big enough to produce a real Finding for
IGM to work against. Adding Wazuh et al. is tracked as a follow-up, not
silently dropped.

## IEM usage

```
python3 iem/integrity_check.py                               # fail-closed gate
python3 iem/run_evaluation.py <candidate_detector.py> <id>    # verdict as JSON
python3 iem/seal_manifest.py                                  # human-run only, re-seals manifest.json after a reviewed change to benchmarks/protected/
```

## IGM usage

```
python3 igm/generate_candidate.py FINDING-001-distributed-ssh-bruteforce
# writes candidates/CAND-001-distributed-ssh-bruteforce/{detect.py,candidate.json}
```

## Deploy actor / human approval usage

```
python3 deploy_actor/human_approval.py <verdict_id> <approved_by> [notes]
python3 deploy_actor/deploy.py <verdict_id>      # blocked without a matching approval
python3 deploy_actor/rollback.py <deploy_id>     # restores the pre-deploy backup
```

## Orchestrator usage

```
python3 orchestrator/run_cycle.py       # one pass; safe to run repeatedly
python3 orchestrator/loop.py [seconds]  # polls run_cycle() on an interval
```

## LLM-backed IGM usage (requires ANTHROPIC_API_KEY; not yet run against a real key)

```
export ANTHROPIC_API_KEY=sk-ant-...
python3 igm/generate_candidate_llm.py FINDING-001-distributed-ssh-bruteforce
# writes candidates/CAND-LLM-<hash>/{detect.py,candidate.json}
# then evaluate it exactly like any other candidate:
python3 iem/run_evaluation.py candidates/CAND-LLM-<hash>/detect.py CAND-LLM-<hash>
```

## Suricata usage

```
./lab/scenarios/seed_distributed_ssh_suricata.sh
# prints fast.log alerts + the distinct source IPs Suricata observed,
# then tears the lab down. Full eve.json in lab/suricata/output/.
```

## Next steps

1-6. Done — lab, scenario harness, IEM integrity + evaluation, IGM's first
candidate, the deploy actor / human-approval gate, and the orchestrator's
job loop are all implemented and each exercised at least once (see Status
above), not just coded.

7. Run `igm/generate_candidate_llm.py` against a real `ANTHROPIC_API_KEY`
   and push its output through `iem/run_evaluation.py` at least once —
   the code exists and fails safely without a key, but "LLM-backed IGM
   actually works" is not proven yet (see Status above).
8. ~~Fold in Suricata as a real monitoring/detection layer.~~ Done — see
   Status above.
9. On a dedicated VM sized for them (per ADR-007): stand up OpenVAS and
   Wazuh's full stack (manager + indexer + dashboard), and prove each the
   same way Suricata was proven here (real scenario, real alert observed)
   before marking either done.
10. Move the filesystem-based separation of duties and job state onto real
    Postgres (DB roles per ARCHITECTURE.md §3; `orchestrator/state.json`'s
    schema maps directly to a `jobs` table).
