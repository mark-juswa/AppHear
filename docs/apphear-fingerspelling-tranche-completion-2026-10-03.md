# AppHear fingerspelling tranche completion — 2026-10-03

Reviewed the user-run completion, final validation, failure inventory and CTC-view reports.
This review reads recorded full-validation evidence; it does not rerun bulk extraction or
claim a second full feature/hash recomputation. Manifest SHA was independently checked,
current adapter identity matches, and manifest TRAIN/DEV signer sets are disjoint.
Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.

- TRAIN: 1,024 sequences / 117 signers; DAUN 512, MacKenzie 512.
- DEV: 256 sequences / 15 signers; governed official DEV policy retained.
- Pending: 0; unresolved failures: 0; recorded structural errors: 0.
- Frozen manifest/adapter identities unchanged; input `[T,405]`.
- All 1,280 native views CTC-feasible. Phone views: 19 TRAIN + 2 DEV infeasible;
  all retained and flagged. Native fitting remains the fixed first-run policy;
  phone-view DEV decoding is evaluated separately, without impossible views entering loss.
- TRAIN J/Z/repeated-letter sequences: 318/270/425; DEV: 59/52/109.
- TEST payload access: false in recorded validation. No new payload was accessed here.
- Reflection remains the accepted research limitation; no flip or provenance upgrade.

The two prior network failures are resolved. This establishes readiness for one research
baseline, not accuracy or deployment readiness. No optimizer step, training checkpoint,
Android/WORD/Context Assist modification or acquisition was performed by this review.
Training run directory does not yet exist. Future epoch/optimizer/restore evidence is pending.

Next user-run command (separate from preparation):

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_ctc --dataset 'datasets/fingerspelling/foundation_01' --run-dir 'runs/fingerspelling_ctc_baseline_01'
```

Rerun the same command to resume committed epochs. Return `completion.json`,
`run_identity.json`, `metrics.jsonl`, `committed_epoch.json` and relevant epoch reports from
`runs/fingerspelling_ctc_baseline_01`; include `failure.json`/terminal errors if interrupted.
No automatic training launch.

FINGERSPELLING_BASELINE_READY_TO_TRAIN
