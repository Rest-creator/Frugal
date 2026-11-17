# IGM / IEM Interface Spec (V1)

## IGM (Improvement Generation Mechanism)

**Input:** a `Finding` record `{id, source_tool, type (false_negative|false_positive|ineffective_investigation|proactive_gap), evidence_refs, created_at}`.

**Allowed actions:**
- Read: findings, current tool configs/rules (read-only mount), past
  candidate + evaluation history (for context on what's already been tried).
- Write: a new `Candidate` record into `candidates/` only —
  `{id, finding_id, target_tool, diff_or_new_artifact, rationale, created_at}`.

**Forbidden:** writing to live tool config, writing/reading protected
benchmark store, approving or deploying anything, editing adaptive test
suite directly (it may *propose* a new adaptive test as a `Candidate`-shaped
object of type `adaptive_test_proposal`, which still routes through human
review before IEM ever runs against it).

**Credentials:** its own Anthropic API key / service account, its own DB
role (`igm_role`: SELECT on findings/history, INSERT on candidates only).

## IEM (Improvement Evaluation Mechanism)

**Input:** a `Candidate` record.

**Process:**
1. Verify protected benchmark store hash against known-good manifest. Fail
   closed on mismatch — do not evaluate.
2. Run scenario harness: candidate vs. current tool, identical inputs, for
   every applicable protected benchmark + applicable adaptive test +
   regression suite.
3. Compute metrics: detection effectiveness, false positive/negative rate,
   reliability/consistency across repeated runs, execution time/resource
   use, regression pass/fail.
4. Emit a `Verdict` record.

**Verdict schema:**
```
{
  candidate_id,
  benchmark_results: [{test_id, pass, metrics}],
  adaptive_results: [{test_id, pass, metrics}],
  regression_results: [{test_id, pass}],
  resource_metrics: {exec_time_ms, cpu, mem},
  verdict: "approved_for_human_review" | "rejected",
  rejection_reason: string | null,
  evidence_refs: [...],   // raw harness output, logs
  evaluated_at
}
```

**Forbidden:** modifying the candidate, modifying protected benchmarks,
deploying, generating new candidates. Its own pass/fail must trace to
`benchmark_results`/`regression_results` entries — any evaluator LLM call is
for *summarizing* `rationale` text, not deciding `verdict`.

**Credentials:** separate Anthropic API key/service account, separate DB
role (`iem_role`: SELECT on candidates + protected benchmark store, INSERT
on verdicts only).

## Deploy actor

**Input:** a `Verdict` with `verdict = approved_for_human_review` plus a
`HumanApproval` record `{verdict_id, approved_by, approved_at, notes}`.

**Action:** applies the candidate's diff/artifact to live tool config,
writes a `VersionLedger` entry (old config ref, new config ref, verdict_id,
approval_id, rollback command), restarts/reloads the affected tool.

**Credentials:** separate DB role (`deploy_role`: SELECT on verdicts +
approvals, INSERT/UPDATE on live config + version ledger only). No
generation or evaluation privileges.

## Rollback

Every `VersionLedger` entry stores enough to revert the affected tool to its
prior config in one action. Rollback is a deploy-actor-only operation,
logged the same way as a forward deployment.
