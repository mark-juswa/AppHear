# FSBOARD_REFLECTION_PROVENANCE_CLOSURE

Date: 2026-10-02. Scope: historical saved-pixel reflection and v13 release processing only.

**Decision: public evidence still cannot establish the saved-video convention for both FSboard collections.** Unmirrored video is strongly supported, and three selected released clips have direct proof. Newly located 2021–2022 predecessor source improves the historical evidence but lacks deployment attribution. Training admission remains on HOLD. No flip, training, further extraction or runtime work was performed.

## 1. Repository state and preservation

- Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
- HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Protected WORD baseline: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`, under `baseline/apphear-s2-r2-integration-complete-2026-09-26` and `codex/recognition-stable-ru-d10`. The annotated baseline tag peels to the same commit.
- Preserved pre-existing modified files: `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`, `context/feature-schema.md`, `context/progress-tracker.md`, `memory.md`.
- Preserved untracked work: `.codex_tmp/`, AZ contract/config/pipeline/tests/tools, `datasets/`, earlier AZ/FSboard reports, signing sentinel CSV, and existing phone-pull folders. Exact status is recorded in the integrity artifact. No reset, merge, branch switch, staging or commit.

AZ-0/AZ-1 and the completed admission closure/phone follow-up remain governing records. This adds provenance evidence; it does not rewrite earlier reviews, receipts or training eligibility.

**VERIFIED integrity:** fixed manifest SHA-256 `23f1bf347f016f3ffe208d4dc181038c1d814a00c4c340c0dc669b0db9bcd000`; all 12 TRAIN originals match official size/MD5 and prior SHA-256, totaling 97,918,150 bytes. Prior evidence indexes (32 admission-check, 77 admission-closure, 15 phone-follow-up files) and their reports match hashes. All 883 protected files match the existing baseline inventory. See [integrity verification](<F:/ASL DATASET/5. Apphear3/datasets/fingerspelling/fsboard_candidate01_admission_20261002/reflection_provenance_closure_01/integrity_verification.json>).

## 2. Prior exact-clip reflection evidence

The existing saved-frame reviews and their reference hashes were reverified, not rerun or upgraded:

| Index | Stratum / signer | Recording date from filename | Exact released-clip finding | Scope |
|---|---|---|---|---|
| 6 | DAUN / c7d4 | 2022-10-02 | Normally oriented physical binder text | `EXACT_CLIP_VERIFIED`: unmirrored |
| 8 | MacKenzie / 03ad | 2022-06-19 | Normally oriented physical clothing text | `EXACT_CLIP_VERIFIED`: unmirrored |
| 9 | MacKenzie / 4f1e | 2022-06-28 | Normally oriented physical clothing text | `EXACT_CLIP_VERIFIED`: unmirrored |
| 1–5, 7, 10–12 | Both strata | 2021–2022 | No decisive asymmetric reference established | `UNKNOWN` |

These findings apply to the final released pixels in those three exact sources. They do not independently establish the original-camera convention, rule out an earlier pair of flips, or identify any deployed APK. Signer handedness was not used. All source admission flags remain unchanged.

## 3. Historical collection timeline

The official supplement gives August 2021–March 2023 in its summary and September 2021–March 2023 in its provenance section. That small start-month discrepancy is preserved. It describes continuous session recording, timestamp annotations and Python/FFmpeg splitting, but does not specify mirroring or build identities. [Official supplement, pp. 1–2 and 6](https://openaccess.thecvf.com/content/CVPR2025/supplemental/Georg_FSboard_Over_3_CVPR_2025_supplemental.pdf).

| Date / period | Verified record | Attribution limit |
|---|---|---|
| 2021-10-20 onward | Newly found `sahirshahryar/ASLRecorder` commit history; initial commit `52931fdb0430eb626c163b29c804981edc2c3dff` | Public predecessor family, not proof of FSboard deployment |
| 2021-12-08–2022-10-02 | Date components of the selected 12 full-video filenames | Capture-date indications, not trusted APK identifiers |
| January–November 2022 | Predecessor CameraX path visible in historical source; November changes alter FOV/stabilization | Real implementation variation; no established reflection change |
| December 2022 | `matthew-so/ASLRecorder` v1.1 branch returns to direct Camera2 recording | Not attributed to FSboard sessions |
| 2023-06-08 / 06-10 | Public Record These Hands root / cleaned source v1.2 | Later than every selected recording |
| 2023-09-13 | Public v1.3 release | Later than the supplement's collection end |
| 2024-11-07–08 | Selected metadata `clipCreationTime` dates | Publisher metadata dates; no build/run identity |
| 2025-01-10 onward | Public clipping-code history | First public commit is later than those clip creation dates |
| 2025-07-26 | Cached official FSboard v13 release record | Release notes identify daun_v3/dmk_v3 clips and landmarks, not reflection processing |

This corrects an **incomplete search boundary**, not the earlier repository fact: public **Record These Hands** history starts in June 2023, but public **ASLRecorder predecessor** history exists in 2021–2022. [Sahir predecessor](https://github.com/sahirshahryar/ASLRecorder), [Matthew predecessor](https://github.com/matthew-so/ASLRecorder), [Record These Hands releases](https://github.com/Accessible-Technology-in-Sign/RecordTheseHands/releases).

## 4. Precursor/open-source relationship

The FSboard paper explicitly identifies the collection app as a precursor to open-source Record These Hands and describes Pixel 4a loaner devices. It discusses MacKenzie within the same collection account, without giving per-stratum executable provenance. [FSboard paper §3.2](https://arxiv.org/html/2407.15806v1#S3.SS2).

The Record These Hands README identifies ASLRecorder as an earlier app and lists Sahir Shahryar and Matthew So among its principal authors. This supports the relevance of their predecessor repositories. It does **not** identify either public branch as the actual FSboard fingerspelling build. Their public source also contains isolated-sign workflows. [Pinned v1.2 README](https://github.com/Accessible-Technology-in-Sign/RecordTheseHands/blob/1ac8af67117323e6093515544a784f0f25c81095/README.md).

## 5. Recording-path findings

Inspected source snapshots are pinned by commit and retained with SHA-256 in the new evidence package. Findings are **source inspection**, not deployed-build proof:

| Source / commit | Functions and active path | Reflection finding within inspected code |
|---|---|---|
| Sahir, 2021-12-08 `9cc83a0292c539d41fa346204bb6ba35e5d323cf` | `RecordingActivity.createRecordingSurface`, `prepareRecorder`, `initializeCamera`: front Camera2 → persistent MediaCodec surface → MediaRecorder; separate preview target; orientation hint 270 | No application horizontal transform found on the saving path |
| Sahir, 2022-02-03 `63b00228cd296ab8c1d196dbbe83c68837ca6286` | `startCamera`: front `Preview` and `VideoCapture.withOutput(Recorder)`; `prepareRecording` → MediaStore | No explicit save-mirroring setting or pixel-flip operation found; commented Camera2 code is not the active recorder |
| Matthew, 2022-05-18 `1d2c4cf10113ef9cb30574184712addbbfa611b5` | `startCamera`: separate CameraX preview/video use cases; continuous `prepareRecording` into MediaStore | Same application-level finding; library defaults and field deployment are not inferred from code absence |
| Matthew, 2022-11-08 `864fb2923b1fbf863afdb3e28a8973f8d4fabe2c` | `startCamera`: CameraX; `QualitySelector`, stabilization-off and zoom/FOV controls | FOV controls change geometry, not evidence of horizontal reflection |
| Matthew v1.1, 2022-12-17 `122d572f1beb5bf770c8567b188eb5b81b9796a8` | `createRecordingSurface`, `prepareRecorder`, `initializeCamera`, `startRecording`: front Camera2 → MediaRecorder, orientation hint 270 | No application horizontal transform found |
| Record These Hands v1.2/v1.3, 2023 | Existing pinned `RecordingActivity`/layout review: direct front Camera2 surfaces and phone hint 270 | Supports unmirrored capture; cannot identify 2021–2022 deployment |

Historical source path: `app/src/main/java/edu/gatech/ccg/aslrecorder/recording/RecordingActivity.kt`. [2021 snapshot](https://github.com/sahirshahryar/ASLRecorder/blob/9cc83a0292c539d41fa346204bb6ba35e5d323cf/app/src/main/java/edu/gatech/ccg/aslrecorder/recording/RecordingActivity.kt), [May 2022 snapshot](https://github.com/matthew-so/ASLRecorder/blob/1d2c4cf10113ef9cb30574184712addbbfa611b5/app/src/main/java/edu/gatech/ccg/aslrecorder/recording/RecordingActivity.kt), [December snapshot](https://github.com/matthew-so/ASLRecorder/blob/122d572f1beb5bf770c8567b188eb5b81b9796a8/app/src/main/java/edu/gatech/ccg/aslrecorder/recording/RecordingActivity.kt).

Several snapshots share versionName `1.0`/versionCode 1 despite implementation changes; December uses `1.1.6`/7. These are not unique APK identities. No predecessor APK releases were returned by their release endpoints. No selected official metadata record supplies app version, APK hash, source commit or a build/session mapping.

## 6. Preview versus saved video

Camera2 preview and recording surfaces are separate targets. CameraX `PreviewView` presentation and `VideoCapture` output are distinct use cases. Historical layouts contain positive `scaleX=2` for a button, not a horizontal camera reflection. No explicit negative camera scale was found in the inspected application paths. **The actual precursor preview's mirrored appearance remains UNKNOWN.** A normal selfie preview or handedness cannot establish saved pixels.

`MediaRecorder.setOrientationHint` stores playback orientation information rather than rotating the encoded frame pixels. It does not establish reflection. Existing selected-source probes contain a rotation-only display matrix (positive 2D determinant); this rules out a reflection *in that matrix*, not one already baked into pixels. Decoding upright by the frozen rotation is separate from horizontally flipping. [Android API](https://developer.android.com/reference/android/media/MediaRecorder#setOrientationHint(int)).

## 7. FSboard v13 clipping/conversion

**VERIFIED collection processing:** continuous session videos became timestamp-bounded clips using Python/FFmpeg, according to the supplement. Therefore released phrase clips are not simply untouched full camera-session files.

**VERIFIED public helper behavior, not v13-run attribution:** at pinned Record These Hands commit `5c933debadb73be24d4f663547699802f053775c`, `server/collector/clip_video.py:make_clip` searches keyframe boundaries and checks endpoint packet MD5s. `utils.py:trim_video` invokes FFmpeg with `-ss`, `-to`, `-an`, `-c:v copy`; no `hflip`, rotation filter, scaling filter or re-encoding is requested. This command copies compressed video packets and drops audio. `local_video_pipeline.py` calls this helper. The helper also documents a separate internal Google bulk-processing script. [Clipping helper](https://github.com/Accessible-Technology-in-Sign/RecordTheseHands/blob/5c933debadb73be24d4f663547699802f053775c/server/collector/clip_video.py), [trim utility](https://github.com/Accessible-Technology-in-Sign/RecordTheseHands/blob/5c933debadb73be24d4f663547699802f053775c/server/collector/utils.py).

The selected v13 metadata has the helper's characteristic timing/file/packet-hash fields. This supports codec-copy provenance, but there is no release job specification, original session payload comparison or publisher statement tying every v13 output to the inspected command. Packet/file MD5 metadata establishes identities, not the absence of an earlier or later transformation.

| v13 question | Result |
|---|---|
| Session-to-phrase clipping? | VERIFIED at collection-documentation scope |
| Every v13 clip made by codec-copy? | STRONGLY SUPPORTED, NOT ATTRIBUTED |
| Any transcode before/after cutting? | UNKNOWN |
| Physical pixel rotation before release? | UNKNOWN; retained orientation matrix is verified separately |
| Horizontal flip before/after cutting? | UNKNOWN |
| Arrow/Parquet conversion proves RGB semantics? | No; the provided landmark serialization converter is not an RGB release-processing specification |

The [cached official v13 documentation](https://www.kaggle.com/datasets/googleai/fsboard?datasetVersionNumber=13) describes RGB release content, not a horizontal-normalization policy.

## 8. DAUN versus MacKenzie

| Evidence | DAUN | MacKenzie / dmk_v3 |
|---|---|---|
| Direct released-pixel proof in fixed TRAIN selection | Clip 6 | Clips 8 and 9 |
| Remaining exact-clip status | Five UNKNOWN | Four UNKNOWN |
| Broad documented collection platform | Pixel 4a / precursor family | Same broad account |
| Actual shared build/save convention | UNKNOWN | UNKNOWN |
| Attributed v13 horizontal-transform policy | UNKNOWN | UNKNOWN |

There is **no demonstrated mixed convention**, but absence of detected disagreement is not proof of one convention. No source was flipped or classified using the signing hand.

## 9. Evidence-scope table

| Finding | Required scope classification | What it establishes |
|---|---|---|
| Saved-pixel references for 6/8/9 | `EXACT_CLIP_VERIFIED` | Those final three sources are unmirrored |
| Other nine final clips | `UNKNOWN` | No exact asymmetric proof |
| Publisher-described session recording and Python/FFmpeg splitting | `COLLECTION_PIPELINE_VERIFIED` | Broad collection workflow, not horizontal behavior |
| Public predecessor source dated within collection | `STRONGLY_SUPPORTED_NOT_ATTRIBUTED` | Relevant historical camera code exists; no FSboard APK attribution |
| Source snapshots without application save-flip calls | `STRONGLY_SUPPORTED_NOT_ATTRIBUTED` | Supports unmirrored convention in that source family |
| Deployed precursor version/commit/APK for DAUN and MacKenzie | `UNKNOWN` | No `COLLECTION_BUILD_VERIFIED` reflection evidence obtained |
| Later public codec-copy helper and matching metadata dialect | `STRONGLY_SUPPORTED_NOT_ATTRIBUTED` | Plausible packet-preserving clipping lineage |
| Every v13 output preserves historical horizontal orientation | `UNKNOWN` | Internal release chain remains unverified |
| Rotation-only matrices in existing exact-source probes | `EXACT_CLIP_VERIFIED` | Container rotation, not baked-pixel reflection |

## 10. Bounded investigation and unresolved gaps

Reviewed official paper/supplement, cached official v13 docs/metadata, Record These Hands local Git history/tags/pinned camera source, release notes, all 31 returned issue/PR records, predecessor repository/branch/commit metadata and five pinned camera snapshots. Source/search attempts and SHA-256s are retained. Public search was restricted to provenance, not alternative datasets. Some browser source requests failed; direct bounded public-source fetches recovered the relevant files. The conference index exceeded the text limit and was not retained; targeted official paper/supplement links were recovered instead. No authoritative archived deployment record was obtained.

The precise missing link is **deployment and release attribution**, not lack of historical source code: which precursor builds/configurations recorded these two collections, and what operations produced the v13 RGB payloads? Public camera snapshots are not APK attestations. Source-history changes to CameraX/Camera2 and FOV do not demonstrate a reflection change. No claim is made about all unseen branches, builds or internal processing.

## 11. Admission consequence

Available evidence is insufficient to assert a collection-wide `UPRIGHT_UNMIRRORED_SOURCE_RGB` convention for DAUN and MacKenzie v13. It also cannot justify a canonical horizontal flip or a mixed-convention verdict. Keep `FSBOARD_TRAINING_ADMISSION_HOLD` and existing non-admission flags. The measured phone cadence and all 12 diagnostic observations remain reusable; no further Candidate01 run is needed for this provenance question.

**Recommendation:** obtain a scoped publisher/custodian confirmation covering historical saved front-camera video, both collections and v13 post-processing. Such a confirmation can establish the convention at collection level; readable text is not required in every clip. If confirmation instead identifies exceptions, record their scope before any normalization or subsequent admission decision. Do not start feature adaptation or training from this report alone.

## 12. Publisher inquiry — prepared, NOT SENT

Suggested first recipient: **Manfred Georg, `mgeorg@google.com`**, publicly identified as an FSboard author and Record These Hands principal author. The cached official Kaggle v13 record identifies him as the dataset creator. This is a relevant contact, not a guarantee of current responsibility or response. [Official paper contact](https://openaccess.thecvf.com/content/CVPR2025/papers/Georg_FSboard_Over_3_Million_Characters_of_ASL_Fingerspelling_Collected_via_CVPR_2025_paper.pdf), [project README contact](https://github.com/Accessible-Technology-in-Sign/RecordTheseHands).

Subject: FSboard v13 RGB saved-video reflection convention

Hi Manfred,

We are preparing a Candidate01-based fingerspelling baseline from FSboard v13 original RGB and need to preserve the same upright, unmirrored camera-input convention in offline extraction and phone deployment. We have reviewed the FSboard paper/supplement and public ASLRecorder/Record These Hands source, but cannot attribute the historical collection builds or the v13 release processing.

Could you please confirm:

1. Were the **saved front-camera videos** for the DAUN and MacKenzie collections (2021–2023, including 2021–2022 recordings) horizontally mirrored or unmirrored, independently of the preview?
2. Did any FSboard clipping/conversion or release step apply a horizontal flip before the **v13 RGB clips** were published?
3. Did DAUN and MacKenzie use the same saved-video reflection convention, or were there any build/session exceptions?

Thank you. A collection-level confirmation is sufficient; no participant identities or video transfers are needed.

The separate inquiry draft and hashed source evidence are retained in [the provenance evidence folder](<F:/ASL DATASET/5. Apphear3/datasets/fingerspelling/fsboard_candidate01_admission_20261002/reflection_provenance_closure_01>). No contact was made. No new video, protected TEST payload, model experiment or protected implementation change was made.

FSBOARD_REFLECTION_STILL_UNRESOLVED
