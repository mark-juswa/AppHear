# External artifacts and continuation limitations

GitHub contains the application, runtime/parity assets, research code/configs, governed metadata/manifests,
selected final Keras models, final evaluations, summary histories and dated reports. See
`evidence/team_handoff_20261009/import_inventory.json` for copied paths, original paths, byte counts and SHA256.
Selected Keras archives live under packages/research_checkpoints instead of generated runs; research runners
retain their original relative run paths and are not silently redirected by this handoff.

## Not in GitHub — preserve and transfer separately if required

| Artifact | Original location / continuation requirement |
|---|---|
| Foundation1024 TRAIN+256DEV source/raw/features | F:/ASL DATASET/5. Apphear3/datasets/fingerspelling/foundation_01; retain receipts and verify pinned manifest/Adapter/source hashes |
| 3072 additions+256DEV-B materialization | I:/AppHearData/FSboard_TRAIN4096_01; train_additions,dev_b,execution; do not treat just manifests as prepared features |
| Original RGB and visual/crop/embedding archives | F: datasets/fingerspelling visual/residual directories; raw-v1/source-frame alignment remains required |
| Full optimizer state/alternate candidates | F: runs/*/checkpoints and best_candidates; selected models copied, optimizer continuation is NOT bundled |
| Full epoch predictions/raw event logs/logits | F: runs/*/epochs and artifacts/*; 1GB+ full epoch records summarized, each source SHA retained in histories |
| Old Android export/rollback APKs | F: artifacts/...; private configuration/APKs remain local, not a public release |
| Device recordings/phone_pull_*/private diagnostics | Keep local; do not publish user context/camera captures without separate consent |
| Source ZIP | D:/Downloads/sample_word_batch_v1_optimized.zip, SHA7a85dcb35332e1763e1137cf69f4577491ec5869b8f5cc4fc81fb4eec2104b70; all203chosen GLBs are already included |
| Supabase/Gemini/ElevenLabs credentials | Ignored local Gradle/environment; never in Git or APK shared publicly |

I: storage is hard-coded in some research runners, including model/fingerspelling_train4096.py. Absolute paths in
old config/evidence are original-machine provenance, not portable defaults. Before resuming research, agree on
local storage mapping, reproduce original layout or add a separately tested parameterization, provision data,
verify MD5/SHA/raw/schema/Adapter lineage, and run the relevant preflight. Do not launch downloads/extraction
or training merely to test checkout completeness. TEST payload remains sealed. DEV-B must not become a tuning loop.

The original F: research checkout has unrelated dirty/untracked Android edits, phone exports and scratch files.
They remain intact and were not merged into the app. The imported234nonconflicting fingerspelling source files
are recorded exactly. Existing tracked WORD research/history on the October9 ancestor remains in Git; no
unreviewed research Android code was promoted. Local archival completeness is not the same as product readiness.

Animation assets are provided by the supervisor; their authorship/license clearance for redistribution was not
independently established by technical playback tests. Existing decoder licenses/notices remain intact. Likewise
FSboard source RGB/license acquisition is separate: no corpus videos were uploaded by this handoff.
