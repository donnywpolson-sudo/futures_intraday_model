Continue from CODEX_HANDOFF.md.

Goal: pursue the newly registered target hypothesis `<HYPOTHESIS_ID>` through the next safe gated research step without repeating the target/policy mismatch seen in `opening_range_acceptance_continuation_30m_v1`.

Rules:
- First verify repo path, git status, `CODEX_HANDOFF.md`,
  `manifests/target_hypotheses/registry.json`, and
  `manifests/target_hypotheses/trial_statuses.jsonl`.
- Confirm `<HYPOTHESIS_ID>` is `CANDIDATE`, has `wfa_allowed=false`, has no discovery evidence yet, and has explicit `next_allowed_actions`.
- Do not run discovery, confirmation, locked smoke, WFA/modeling, Phase 8, promotion, proof scans, provider actions, staging, commit, push, paper, or live execution without explicit bounded approval.
- Do not call a candidate "good", "tradable", "rescued", or "ready" from target smoke alone.

Target-policy contract gate:
- Before implementing Phase 9 smoke code, write down the target-policy contract for `<HYPOTHESIS_ID>` in the implementation notes, handoff, or proposed approval packet.
- The contract must state:
  - target payoff basis: fixed-horizon exit, path favorable excursion, first-touch TP/SL, expected net ticks/dollars, or another explicit basis;
  - intended entry rule;
  - intended exit/capture rule;
  - horizon and session handling;
  - cost/min-profit threshold source;
  - compatible policy evaluation basis;
  - incompatible policy evaluation basis.
- If the target label is path-based, do not treat fixed-exit PnL as decisive economic approval or rejection by itself. Path-based labels need first-touch/path-capture or otherwise policy-aligned economics.
- Target, model, and executable policy must describe the same trade before any downstream economic conclusion is accepted.

First allowed work:
- Implement only the source/tests needed for the registered candidate's Phase 9 smoke.
- Reuse existing Phase 9 harness patterns where applicable.
- Preserve causal semantics: event eligibility, target direction, labels, features, costs, and filters must use only information available at the event timestamp.
- Add focused tests for event eligibility, no future leakage, event/class distribution, horizon/session handling, duplicate-overlap controls, registry/status behavior, and target-policy contract metadata.

Do-not-overclaim target smoke:
- Discovery, confirmation, and locked target smoke can prove only target construction, ranking behavior, class/event balance, duplicate-overlap controls, and fold stability for the target-smoke scope.
- Target smoke does not prove model quality, executable policy quality, tradability, live readiness, or economic edge.
- Any pass summary must say what was tested and what was not tested.

Future downstream evidence gates:
- Before accepting WFA/model or Phase 8 evidence, require policy-aligned reports that include:
  - gross PnL before costs;
  - costed net PnL;
  - fold-level positive/negative counts;
  - trade count and trade rate/selectivity;
  - cost per trade in dollars and ticks;
  - MFE, MAE, and giveback when trades and bars exist;
  - first-touch or otherwise policy-aligned feasibility when the target is path-based;
  - clear diagnostic-only flags when evidence is not decisive.
- Treat high directional accuracy, top-fraction target-smoke net, or large MFE as learning evidence only until a compatible executable policy survives costs and folds.
- If gross PnL is already flat or negative before costs, do not blame costs alone.

Validation:
- Run only focused tests for touched harness/registry/contract code.
- Run `python -m json.tool manifests\target_hypotheses\registry.json`.
- Run `python -m scripts.validation.check_coordination_docs`.
- Run `git diff --check` for touched tracked files.

Candidate failure autopsy gate:
- This is a late continuation gate only. Do not run it during the first source/tests-only Phase 9 smoke implementation boundary.
- If later downstream evidence exists and the candidate failed economically, run a failure autopsy before proposing or applying a `RETIRED` registry/status disposition.
- Required evidence before the autopsy: Phase 9 smoke reports, WFA manifest/report, Phase 8 single-target policy diagnostics/summary/trades, `configs/costs.yaml`, materialized bars, and first-touch feasibility evidence if available.
- Use this command template only after the required evidence exists and the bounded autopsy run is explicitly approved:
  ```powershell
  python -m scripts.phase8_model_selection.candidate_failure_autopsy --hypothesis-id <HYPOTHESIS_ID> --run <RUN_ID> --market ES
  ```
- `--allow-overwrite` is forbidden unless separately approved after reviewing the existing outputs.
- Expected outputs are ignored JSON at `reports/candidate_failure_autopsy/<HYPOTHESIS_ID>/<RUN_ID>/failure_autopsy.json` and durable markdown at `docs/<HYPOTHESIS_ID>_failure_autopsy.md`.
- If required evidence is missing, report the blocker and do not invent failure statistics, explanations, or retirement rationale.
- The autopsy is diagnostic only. It does not approve tuning, WFA/model reruns, TP/SL selection, rescue work, promotion, registry mutation, staging, commit, push, paper trading, or live trading.

Rescue-feasibility gate:
- If the autopsy shows a target/policy mismatch or failed economics, do not draft v2 immediately.
- First require a separately approved rescue-feasibility audit that checks whether any pre-trade, fold-stable, policy-aligned salvage signal exists.
- Oracle/path-upper-bound evidence can explain learning value, but it is not tradable proof.
- Do not draft v2 if the only positive evidence is an oracle upper bound, ambiguous OHLC ordering, or isolated buckets from one weak pre-trade family.
- Any v2 must have a new explicit target-policy contract and separate bounded approval before WFA/modeling.

Stop condition:
- Stop after source/tests pass and produce a bounded discovery-smoke approval plan.
- The bounded plan must include exact command, scope, discovery folds, timeout/stop budget, expected ignored reports, forbidden actions, and pass/fail stop conditions.
- If only source/tests exist, do not run the autopsy; produce the bounded discovery-smoke plan as before.
- If downstream policy evidence exists later and the candidate failed, stop before `RETIRED` disposition until the failure autopsy has been run and reviewed.
- If autopsy outputs already exist, stop unless overwrite is explicitly approved.
- Do not execute the discovery smoke, failure autopsy, rescue-feasibility audit, or any later gated command unless I explicitly approve the bounded command after seeing the plan.