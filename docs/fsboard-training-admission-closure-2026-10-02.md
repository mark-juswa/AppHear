# FSBOARD_TRAINING_ADMISSION_CLOSURE

Recorded 2026-10-02. Fixed twelve official v13 TRAIN sources; no new videos, TEST RGB, model training,
Candidate01 tuning, final features, Android changes or alternate dataset search.

**Decision: HOLD.** The host representation supports continuing toward one controlled sequence baseline
with explicit missingness limitations. Historical reflection attribution and fresh current-phone cadence
are still insufficient for training admission. FSboard has not been rejected. No source is marked admitted.

## 1. Repository and governing records — VERIFIED

Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.
Protected WORD baseline: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`, under
`baseline/apphear-s2-r2-integration-complete-2026-09-26` and `codex/recognition-stable-ru-d10`.

Existing modified work was preserved: `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`,
`context/feature-schema.md`, `context/progress-tracker.md`, `memory.md`. Existing untracked work includes
`.codex_tmp/`, AZ/FSboard datasets/reports/config/validators/tests/download tools, the AZ contract,
recognition-upgrade sentinel CSV and the four phone-pull directories. Full inventory is in
`evidence/repository_state.json`. No branch switch/reset/merge/staging/discard occurred. Only new closure
diagnostic artifacts/report/helpers and append-only handoffs were added. The 883-file protected snapshot
has zero mismatches. All 32 previously indexed admission evidence files and its report remain hash-identical.

AZ-0, AZ-1, dataset contract, compatibility gate, fixed download preparation and download verification
remain governing records. This user-authorized closure supersedes the earlier *diagnostic extraction*
restriction for UNKNOWN reflection; it does not authorize admitting unknown sources or changing raw-v1.
The real AZ-1 collection package remains empty and its isolated A–Z + OTHER contract unchanged.

## 2. Fixed source identity and lineage — VERIFIED

Manifest: `fsboard_candidate01_admission_download_manifest.json`, SHA-256
`23f1bf347f016f3ffe208d4dc181038c1d814a00c4c340c0dc669b0db9bcd000`.
Twelve unique TRAIN signer IDs, six DAUN/six MacKenzie, 97,918,150 original bytes. Official filenames,
sizes/MD5s and local SHA-256 all revalidate, with no extra files or identity substitutions. Sources retain
original pixels; only the frozen decoder's orientation rotation is applied. No horizontal flip occurs.

The three prior raw/receipts (selection 6/8/9, 633 frames) were verified and reused without inference.
The remaining nine were extracted once (1,659 frames), totaling **12 raw sequences / 2,292 frames**.
New observations are under `admission_closure_01/observations/`; reused files remain in `admission_check_01/`.
Every new receipt uses `apphear.fsboard.admission_closure_diagnostic_receipt.v1`, with explicit
`reflection_status=UNKNOWN`, `training_admitted=false`, `training_manifest_eligible=false` and
`image_semantics_verified=false`. They pin source/raw/wrapper/model/core-source hashes, decoder, timestamps
and prior probe/review identities. None is an AZ-1 or phrase-CTC training receipt/manifest.

**Important declaration limit:** unchanged raw-v1 still emits `UPRIGHT_UNMIRRORED_SOURCE_RGB`; for these
nine files that string describes the extractor's expected convention, not verified source reflection.
Both raw metadata and receipt carry the unverified diagnostic status. Readers must enforce admission
and receipt guards; schema string alone cannot grant training eligibility. `class_id=-1` is a diagnostic
legacy sentinel, not a model class or OTHER. Intended transcripts are never changed because hands fail.

Pinned assets: DWPose `37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0`;
hand refiner `6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9`.
All four perception Python modules match the prior pins. Frozen `Candidate01Offline.process_rgb` and
`extract_video` are reused; the wrapper only times delegation and adds diagnostic metadata/receipts.
One Candidate01 call per newly decoded frame, no duplicate inference, resampling, interpolation,
forward filling, 258/378/Recognition-V2 feature conversion or word ingest.

## 3. Per-source coverage, cadence and processing — VERIFIED diagnostics

These measure current-frame perception evidence, **not recognition accuracy or corpus-wide usable yield**.
Publisher window means the supplied whole-phrase annotation start/end mapped into the clip, not independently
verified signing/letter boundaries. L/R are DWPose anatomical *slot names*, not established physical-hand identity.

| # | Stratum / signer | Intended phrase | Frames | Any hand frames (%) | Publisher-window hand % | Longest missing run frames / first-to-last ms | L / R observed | Body available frames | Native FPS | Candidate ms p50 / p95 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | DAUN / 1d72 | jade hughes | 121 | 34 (28.1) | 33.0 | 41 / 1330.2 | 24 / 30 | 0 | 30.081 | 52.88 / 56.72 |
| 2 | DAUN / d69c | surprise az | 181 | 103 (56.9) | 75.7 | 32 / 1036.2 | 86 / 99 | 0 | 29.908 | 53.58 / 58.48 |
| 3 | DAUN / 917d | sommer stevens | 121 | 112 (92.6) | 98.5 | 4 / 99.9 | 39 / 109 | 0 | 30.028 | 55.33 / 58.97 |
| 4 | DAUN / 740f | rochelle velez | 181 | 109 (60.2) | 77.0 | 37 / 1203.6 | 107 / 81 | 0 | 29.908 | 53.15 / 57.18 |
| 5 | DAUN / d3ab | octavio hamilton | 91 | 76 (83.5) | 95.7 | 8 / 234.0 | 61 / 76 | 0 | 29.918 | 59.13 / 63.42 |
| 6 | DAUN / c7d4 | kimberlee hammond | 241 | 194 (80.5) | 87.3 | 29 / 931.7 | 191 / 151 | 1 | 30.047 | 52.88 / 55.65 |
| 7 | MacKenzie / 6f68 | love means many things | 121 | 80 (66.1) | 82.1 | 14 / 544.0 | 78 / 52 | 0 | 23.943 | 58.44 / 63.99 |
| 8 | MacKenzie / 03ad | communicate through email | 241 | 174 (72.2) | 88.9 | 42 / 1366.4 | 174 / 62 | 98 | 30.008 | 51.63 / 55.73 |
| 9 | MacKenzie / 4f1e | just like it says on the can | 151 | 134 (88.7) | 99.2 | 10 / 299.7 | 75 / 134 | 0 | 30.028 | 53.88 / 56.45 |
| 10 | MacKenzie / 9d2b | an excellent way to communicate | 301 | 212 (70.4) | 86.2 | 44 / 1438.6 | 161 / 205 | 1 | 29.890 | 58.46 / 66.14 |
| 11 | MacKenzie / fe96 | labor unions know how to organize | 211 | 149 (70.6) | 82.8 | 47 / 1539.0 | 56 / 148 | 0 | 29.890 | 59.02 / 64.48 |
| 12 | MacKenzie / 1f91 | shivering is one way to keep warm | 331 | 307 (92.7) | 99.7 | 22 / 699.3 | 89 / 307 | 182 | 30.028 | 51.38 / 61.28 |

Processing percentiles are **desktop CPU timings**, excluding decode and downstream assembly; they are
not delivered phone FPS. Reused rows retain their original timing run. All source timestamps are genuine
`CONTAINER_POS_MSEC`, finite/strictly chronological and agree with independently decoded FFprobe PTS within
0.001 ms. No repair/fallback occurred. Native source gaps (median/p95/max ms) follow:

| # | Gap median / p95 / maximum ms |
|---|---:|
| 1 | 33.244 / 33.312 / 33.378 |
| 2 | 33.433 / 33.511 / 33.567 |
| 3 | 33.300 / 33.300 / 33.411 |
| 4 | 33.433 / 33.444 / 33.589 |
| 5 | 33.433 / 33.517 / 33.533 |
| 6 | 33.278 / 33.289 / 33.400 |
| 7 | 41.756 / 41.867 / 42.000 |
| 8 | 33.322 / 33.422 / 33.444 |
| 9 | 33.300 / 33.300 / 33.522 |
| 10 | 33.456 / 33.456 / 33.678 |
| 11 | 33.456 / 33.456 / 33.622 |
| 12 | 33.300 / 33.511 / 33.600 |

Stored resolution is 2688×1512 for #1 and 3264×1836 for the other eleven. Existing orientation rotation
yields upright 1512×2688 / 1836×3264. The source frame rates vary (~23.94 Hz for #7, ~29.89–30.08 Hz elsewhere).
Counts/chronology/masks/finite valid geometry/source size/ROI acceptance/body availability all validate.
The frozen 0.5 presence and ≥18 valid-hand-joint rules are unchanged. Partial valid body points remain
available even when bodyAvailable=false; no body or hand block is removed.

## 4. Cross-signer/stratum assessment — INTERPRETATION bounded by this sample

DAUN: 628/936 whole-clip frames (67.1%), publisher-window 77.6%; six independent official signer IDs.
MacKenzie: 1,056/1,356 whole-clip frames (77.9%), publisher-window 90.8%; six independent official signer IDs.
No sampled signer has zero hand observations. Whole-clip rates range 28.1–92.6% DAUN and 66.1–92.7% MacKenzie.
This supports a first representation experiment *conditionally*, not final sufficiency, accuracy or a
corpus rejection threshold. The weak #1 remains selected and inventoried; do not hide it by reselection.

## 5. Missing-hand, proposal/refiner and ROI diagnostics

| # | L/R proposal frames | L/R proposal present but not accepted | Both missing: no proposal / proposal present | Close ROIs / both observed frames |
|---|---:|---:|---:|---:|
| 1 | 104 / 104 | 80 / 74 | 17 / 70 | 20 / 20 |
| 2 | 125 / 134 | 39 / 35 | 47 / 31 | 70 / 82 |
| 3 | 119 / 121 | 80 / 12 | 0 / 9 | 32 / 36 |
| 4 | 175 / 132 | 68 / 51 | 6 / 66 | 71 / 79 |
| 5 | 90 / 91 | 29 / 15 | 0 / 15 | 58 / 61 |
| 6 | 239 / 212 | 48 / 61 | 2 / 45 | 146 / 148 |
| 7 | 106 / 95 | 28 / 43 | 15 / 26 | 50 / 50 |
| 8 | 203 / 241 | 29 / 179 | 0 / 67 | 27 / 62 |
| 9 | 145 / 149 | 70 / 15 | 2 / 15 | 75 / 75 |
| 10 | 256 / 301 | 95 / 96 | 0 / 89 | 128 / 154 |
| 11 | 163 / 177 | 107 / 29 | 2 / 60 | 48 / 55 |
| 12 | 262 / 331 | 173 / 24 | 0 / 24 | 73 / 89 |

Close means ROI-center separation <0.25×smaller side, the prior diagnostic heuristic; it is neither a
new acceptance threshold nor proof of two physical hands. Many simultaneous slot observations show one
visible signing hand; duplication/slot ambiguity is a real future adapter risk, with no dominant-hand
truth inferred. Preserve both slots and masks. Python-only handedness stays diagnostic, outside common input.

All internal runs, edge runs, exact indices/timestamps, publisher-window overlaps, proposal/presence
distributions, body valid-point counts and ROI counts are in `coverage_diagnostics.json`.
Examples grounded in private chronological pixels plus masks:

- #1 has a 41-frame internal gap at 1.595–2.926 s while the signing hand is visibly raised in reviewed
  frames. Proposal-present/nonaccepted evidence dominates its missing frames. This is a substantial
  perception failure during likely content, not all lead-in/release. The root cause is UNKNOWN; no tuning.
- #4 has a long nominally internal gap at 4.280–5.484 s after the hand is visibly lowered in review;
  an internal index run alone does not imply signing-content loss. Likewise terminal gaps in #8/#10/#11
  are largely consistent with release/idle in viewed frames, without proving every missing frame is idle.
- #6's terminal run starts at 7.056 s with the hand still raised in a nearby reviewed frame before release;
  it cannot be wholly dismissed as idle. #7 also has missing evidence around hand entry and mid-attempt.
- #3/#5/#9/#12 retain strong publisher-window evidence despite intermittent gaps. #2/#4/#11 (Z prompts)
  and #3/#4/#6/#7/#8/#10 (repeat prompts) retain meaningful sequences, not total collapse.

Proposal-present but nonaccepted and completely missing proposals are distinct recorded outcomes.
Masks cannot distinguish occlusion, blur, proposal geometry or refiner-domain causes by themselves.

## 6. Reflection/version investigation — scoped facts and remaining attribution gap

The public Git history starts at `6bce19ab33cc9bc49671bdf221956c82c8999ed8`, 2023-06-08; cleaned code/tag
v1.2 is `1ac8af67117323e6093515544a784f0f25c81095`, 2023-06-10. Tag v1.3 is
`6c81b7d29eba6b367f384d1248da36a5fd20b0de`, 2023-09-13. Both build files say versionCode 7;
versionName changes 1.2→1.3, so versionCode alone cannot identify a historical build. The source's
`@since October 4, 2021` is a provenance comment, not recoverable 2021 source/APK identity.
[Pinned public source](https://github.com/Accessible-Technology-in-Sign/RecordTheseHands/tree/1ac8af67117323e6093515544a784f0f25c81095).

In these 2023 snapshots, `createRecordingSurface`, `setRecordingParameters`, `initializeCamera` and
`startRecording` select front Camera2, send camera targets directly to a persistent MediaCodec surface
used by MediaRecorder, and separately to preview SurfaceView. No application horizontal pixel transform
is present in this inspected path. Phone orientation hint is 270°; v1.3 adds a tablet-specific 0° branch.
The preview layout has no negative scale/mirror; its positive scale=2 belongs to the record button.
Preview mirroring in the actual earlier precursor is UNKNOWN. Orientation hints write playback metadata,
not a pixel rotation or reflection. [Android API contract](https://developer.android.com/reference/android/media/MediaRecorder#setOrientationHint(int)).

CameraX migration appears only on 2025-09-25 (`01ac04e7...`), followed by Camera2 restoration on 2025-10-03
(`d2f78d68...`). This corrects the temptation to use the latest `5c933de...` recorder as a verified 2022 build.
The inspected 2023 phone path has a stable direct-surface convention; no flip-changing commit was found
among those snapshots. This is **not** an exhaustive claim about unseen precursor builds/all later branches.

The selected filename dates span 2021-12-08 to 2022-10-02, preceding public history. The FSboard paper
explicitly says collection used a **precursor** to open-sourced Record These Hands. It describes the same
collection app across phrase categories, but does not identify deployed APKs or attest saved reflection.
[Publisher collection description](https://arxiv.org/html/2407.15806v1#S3.SS2).
Official metadata has no app version/APK hash; the public clip helper itself says final bulk processing
also used an internal script. Its codec-copy path supports preservation but does not attest all v13 transforms.

**Scope classification:** #6/#8/#9 remain exact-clip unmirrored VERIFIED by prior normal-direction physical
text. The other nine remain exact-clip UNKNOWN. Collection-level unmirrored convention is STRONGLY SUPPORTED
BUT NOT FULLY ATTRIBUTABLE, for both strata; no verified stratum-specific difference or version-induced flip
was established. No source is flipped based on apparent left/right hand.

**Smallest closure evidence:** publisher/custodian attestation covering the 2021–2022 precursor saves and
v13 clip transforms, or dated precursor/APK code plus trustworthy session/version mapping. One adequate
collection-level convention would be sufficient; readable clothing text in every video is not required.
Until then, the nine UNKNOWN sources stay non-admitted. No external message was sent on the user's behalf.

## 7. Bounded temporal content review — performed, with explicit limits

All twelve were inspected through 48 uniform chronological native-frame views, including actual clip
edges. No obvious abrupt cutoff of the overall changing-handshape attempt was seen; starts/holds/releases
are plausible. #12 has a shorter post-release margin. #9 shows leading curved little-finger/hand movement
consistent with J. #2/#4/#11 show extended-finger motion consistent with Z-containing attempts. Repeated-letter
prompts #3/#4/#6/#7/#8/#10 show continuous changing/held handshapes and lateral changes; they are plausible
whole-sequence CTC examples. #6 preserves EE and MM, #8 MM, #10 LL/MM; exact occurrences were not segmented.

This is a bounded assistant visual review, **not qualified full ASL transcription**. Skipped native frames,
small motions and occlusion prevent certifying every character, complete J/Z trajectory or both repeat
occurrences. #1 J trajectory remains uncertain and its raw content gap is material. Source pixels still
show substantial attempt content; missing masks have not destroyed the entire attempt in most clips.
No obvious gross transcript conflict was established, but exact transcript-match fields remain null.
No arbitrary frame-level letter targets, boundaries, transition→OTHER conversion or difficult relabeling.

`bounded_temporal_review.json` records per-source uncertainty and hash-linked review panels.
Private panels are not face-redacted/publication artifacts and are not embedded in this report.
This gross review is enough to describe diagnostic suitability; it cannot promise label purity or accuracy.
Further qualified review of specific uncertain cases is recommended without demanding exhaustive manual
per-letter segmentation before an initial sequence experiment.

## 8. Fresh current-phone cadence — UNMEASURED external device blocker

`D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe devices -l` returned no attached devices at repeated
checks; final timestamp/output are in `phone_cadence_status.json`. No APK build/install or phone run took
place. Delivered count/duration/rate, median/p95/max gap, Candidate01 p50/p95 and drop count are **null**.
The historical ~4.38 and ~6.5–8.1 Hz observations are retained as distinct historical contexts, not selected
or averaged into a current measurement. Requested 15 Hz/desktop latency cannot replace this evidence.

Current source: `Candidate01FrameAnalyzer.analyze` constructs `PhoneRawObservation` from one current-frame
Candidate01 run, calls the unchanged `PhoneProductionSession.consume`, then ticks rolling `FpsTracker`.
It closes ImageProxy in finally; CameraX uses KEEP_ONLY_LATEST. Slow processing can discard incoming frames
without a queue of all frames. State-change logs/rolling FPS cannot recover per-observation gap percentiles
or exact capture-drop counts. Existing debug `PhoneCausalController` records count/timestamps/processing time,
but synchronized diagnostic capture overhead must be reported and cannot silently stand for normal app cadence.

Next measurement: connect Xiaomi, verify installed APK/assets against this source, warm up, then observe
a ≥60-s representative live steady period using the current normal Candidate01 path. Count actual deliveries,
timestamps and processing times wherever observable; record profiler/capture overhead, gaps and unavailable
drop counters. No user training dataset or performance tuning is needed. If exact normal-path observability
is absent, report it rather than editing protected recognition code or inventing percentiles.

Phone availability is the remaining **device** blocker. It cannot truthfully be called the sole overall
blocker while the independent historical reflection attribution above also remains unverified.

## 9. CTC structural feasibility — conditional math, measured-rate decision pending

At one encoder output per observation and no temporal stride:
`required steps = transcript characters (including spaces) + adjacent identical-character pairs`.
For the uniform-rate approximation only, `available = floor(metadata duration × rate) + 1` assumes an
observation at zero and possible endpoint. Real phase/jitter/missingness differ. No raw observations are
generated or resampled. TRAIN metadata: 64,410 alphabet/space clips, 117 official humans; DEV: 2,352/15.
Cached v13 TRAIN/DEV metadata only was read; no TEST payload/metadata was reread for this closure.

**Sensitivity cases, not current measured phone rates:**

| Assumed Hz | TRAIN impossible / count (%) whole clip | DEV impossible / count (%) whole clip | TRAIN / DEV publisher-window impossible % |
|---|---:|---:|---:|
| 4.38 | 15,438 / 64,410 (23.97) | 163 / 2,352 (6.93) | 46.10 / 26.66 |
| 6.5 | 1,419 / 64,410 (2.20) | 13 / 2,352 (0.55) | 8.13 / 4.34 |
| 8.1 | 541 / 64,410 (0.84) | 1 / 2,352 (0.04) | 2.22 / 0.94 |
| 15.0 | 12 / 64,410 (0.02) | 0 / 2,352 (0.00) | 0.08 / 0.13 |

Whole-clip idle steps can make the necessary length test optimistic about usable signing information.
Publisher windows are only a second conditional duration view, not proven exact content boundaries.
Passing either lower bound is **not proof of preserved J/Z motion, distinguishing rapid handshapes, CTC
trainability or accuracy**. Missing-hand frames remain actual time steps with masks; discarding them would
further reduce usable capacity. The product ≥15 Hz target is unchanged. A fresh measured rate must be
substituted before recommending a phone-compatible training temporal regime; no architecture/cadence sweep.

## 10. Validation, scope review and remaining evidence

Actual twelve-source validator: source/manifest/CSV/hash/role identities, prior three byte reuse,
nine diagnostic-only receipts, raw schema/chronology/masks/PTS, frozen source/models and 883-file snapshot
all PASS. Forty-five existing AZ/raw/download tests PASS; git diff --check passes (existing LF/CRLF warnings).
Archived one-off helper snapshots and an evidence hash index support reproducibility. The new panel helper's
iterator unpacking and audit-helper import-path mistakes were fixed locally; perception was not rerun or changed.

Scope review: plan/system preservation PASS; training readiness HOLD, not a runtime release review.
No critical protected-boundary violation found. Important unresolved evidence: historical source-reflection
attribution and fresh measured phone cadence/its CTC compatibility. Specific temporal-label uncertainty and
#1's severe gap remain disclosed risks, not invented OTHER labels or reasons to drop an inconvenient signer.

Later experiment preparation still needs an explicit sequence dataset/admission manifest and common-input
adapter/normalization contract; byte-equivalent offline/Android parity remains a deployment gate. Official
signer roles must remain immutable, copied sources cannot create new humans, historical AppHear protected
material stays excluded, and DEV/TEST phrase-overlap policy must be frozen before selection. These are
implementation/evaluation obligations for the future single baseline, not newly executed gates here.

## 11. Training recommendation and stop

**Representation evidence is encouraging enough to justify exactly one first causal sequence-encoder +
character-CTC experiment once the two admission gaps close.** Both source strata and moving/repeated-letter
prompts retain meaningful current-frame evidence. Twelve selected clips cannot estimate generalization,
per-character accuracy, corpus yield or end-to-end product reliability. Do not demand perfect perception,
replace hard clips, tune Candidate01, interpolate missing motion or start an architecture search.

**Do not start training now.** Complete current Xiaomi cadence measurement and conditional CTC calculation,
and obtain adequately scoped precursor/v13 reflection evidence. If those establish practical capacity and
the unmirrored convention, issue a new bounded admission decision for one baseline; otherwise document the
specific failure. All three original raw outputs and nine new diagnostics can be reused by hash.

No additional video download, custom collection, ABC mode, feature-width freeze, TFLite export or WORD/
Context Assist/product/release change follows this report.

Evidence directory: `datasets/fingerspelling/fsboard_candidate01_admission_20261002/admission_closure_01/`.
Key files: `coverage_diagnostics.json`, `stratum_summary.json`, `reflection_version_review.json`,
`bounded_temporal_review.json`, `phone_cadence_status.json`, `ctc_conditional_feasibility.json`,
`source_integrity.json`, `validation_result.json` and the nine receipts; prior three remain referenced.

FSBOARD_TRAINING_ADMISSION_HOLD
