# Text-to-Sign vocabulary batch 3 — 2026-10-16

Scope: existing clone/branch only. Checkpoint `98a40b4`, tag
`checkpoint/update-2-before-batch-3-20261016`. No push, cleanup, new clone,
dependency upgrade, screen/layout/navigation, recognition, camera or database edit.

## Candidate vocabulary and references

All ten were absent from the active Update-2 lexical catalog, including aliases.
They previously used automatic fingerspelling. Aliases, spelling and related
meanings are not counted as extra motions. These are **reference-authored local
previews**, not downloaded source animations, verified lexical signs, or validated
sentence translations. Qualified ASL validations remain **zero**.

| Word | Intended sense and primary reference | Candidate implementation / review focus |
|---|---|---|
| STOP | [Cease an activity](https://www.lifeprint.com/asl101/pages-signs/s/stop.htm) | Flat dominant hand edge descends onto upward other palm. Contact and timing need review. Not FINISH or a street sign. |
| UNDERSTAND | [Comprehend](https://www.lifeprint.com/asl101/pages-signs/u/understand.htm) | Index opens near forehead. Thumb/index contact and flick timing need review. No negative headshake inferred. |
| HUNGRY | [Hunger](https://www.lifeprint.com/asl101/pages-signs/h/hungry.htm) | C hand descends along central chest area. No WISH alias or fabricated sentence grammar. |
| FINISH | [Completion](https://www.lifeprint.com/asl101/pages-signs/f/finish.htm), [HandSpeak](https://www.handspeak.com/word/795/) | Two open five-hands turn outward with separation. Single-turn variant; not an instruction to continue until completion or a universal English tense rule. |
| TIRED | [Fatigued](https://www.lifeprint.com/asl101/pages-signs/t/tired.htm) | Two bent hands rotate/slump around stable wrists. Not a chest slide; body/facial expression remains unvalidated. |
| DEAF | [Deaf](https://www.lifeprint.com/asl101/pages-signs/d/deaf.htm) | Index arcs between cheek near ear and cheek near mouth, with clearance. No direct ear/lip contact. |
| HEARING | [Hearing person/community](https://www.lifeprint.com/asl101/pages-signs/h/hearing.htm) | Index makes two small forward circles near mouth. Existing physical HEAR remains separate. |
| LEARN | [Acquire knowledge](https://www.lifeprint.com/asl101/pages-signs/l/learn.htm) | Dominant fingertips gather from other palm and lift toward forehead. No PERSON suffix or automatic LEARNING alias. Contact/closure need review. |
| RAIN | [Ordinary rain](https://www.lifeprint.com/asl101/pages-signs/r/rain.htm), [HandSpeak](https://www.handspeak.com/word/1764/) | Two palms-down bent/splayed hands descend twice from upper signing space. No storm/wind intensity or idiom translation. |
| NOW | [Present time](https://www.lifeprint.com/asl101/pages-signs/n/now.htm) | Palms-up Y hands descend once; repeated TODAY remains a separate existing action. |

References are linked only. No Lifeprint video/image/animation is copied into the
APK. New trajectories are authored locally; existing AppHear rig/mesh and donor
motion provenance is unresolved. No redistribution rights or linguistic approval
are asserted. This distinction must survive future dataset imports and reviews.

## Implementation

`expand-text-to-sign-batch3.py` pins the complete Update-2 bundle hash, appends new
named `SIGN_*_HUMAN_AUTHORED_PREVIEW` actions and records construction separately
from imported/retargeted clips. `sourceAsset` identifies the immutable original
resident rig, explicitly **not** an imported animation of the new word. Metadata
also records the reference, intended sense, unresolved rights and review status.

The Text-to-Sign catalog loader and expansion model accept this construction
explicitly and retain MAPPED/unreviewed status. Unknown constructions, mismatched
action naming, corrupt bundle hashes and alias/ID collisions fail. Existing
retargeted entries retain their prior defaults. No playback-controller change.

Hand articulation uses actual local anatomical frames and corresponding existing
B/C/O/Y or YES articulation where relevant; each new sign has its own specified
handshape and trajectory. Left articulation is reflected through its own parent
and rest frames, never copied as right-hand local quaternions. Fixed-length arm IK
is an offline authoring tool. New tracks contain rotations only, with shortest
quaternion continuity and explicit neutral entry/release. No global joint clamp,
skin-weight edit, scale change, arm stretch, runtime physics or idle-layer change.

The first candidate exposed HUNGRY/THIRSTY/TIRED body penetration. HUNGRY had used
a finger-base anchor that put the wrist inside the chest; THIRSTY's straight-up
tip anchor put the curled hand behind the throat surface; TIRED's fixed finger
anchor pulled the wrist backward as it rotated. Corrections change only those
new trajectories/orientations. LEARN's initial unreachable wrist target was
rejected by the arm solver and its approach corrected; the reach guard remains.

Recovery checklist diagnosis: isolated new offline-tool defect, not a defect
found in the existing player or old rig. The initial post-blend correction
mistakenly quaternion-normalized idle translation/scale vectors alongside
rotations. Internal arm lengths then disagreed with the renderer. The tool now
asserts idle translations/scales agree with immutable bind data, retains only
rotation overrides and checks actual arm lengths at every authored frame.
STOP/LEARN approach/release lift forward and upward before crossing the
body, bounded analytically by the original arm reach sphere. Held signing paths
are unchanged by that transition correction. No finger limits or scale changes.
UNDERSTAND uses the rig's O thumb/index contact
articulation opening to its straight index; contact/flick still need ASL review.
FINISH shares axial rotation through its forearms while preserving world hand
position/orientation, instead of putting the full turn into the wrist alone.
The first installed pose review rejected RAIN's forward-facing palm orientation:
HandSpeak explicitly specifies palms down. Its final candidate uses open/splayed
articulation, palms down and two descents from upper signing space.

THIRSTY was rejected: one candidate met the intersection proxy but its index was
poorly visible from the front; alternatives with a more upright index penetrated
the neck/collar region. GIRL's thumb-contact candidate also failed skin-clearance
checks. Neither motion is included or registered. Both retain automatic spelling.
FINISH is the tenth accepted candidate. No unsuitable motion is relabeled to
inflate coverage. The earlier THIRSTY captures are diagnostic drafts, not evidence
for a shipped lexical entry.

Final independent sampled projection check: **zero measured hand penetration
for all ten**, at 41 samples per action. FINISH has a maximum **4.05 mm forearm
projection depth** during transition; the other nine have zero measured forearm
depth. This small residual and full mesh contact still need review. All 248 old actions and the
old binary prefix, skeleton, geometry and skinning compare unchanged. The bundle
hash is `e9079308b6780e180528e4b893e64bdb77e46b33b6ad2cd99355bec03df57b18`.
Zero in this bounded projection test does not rule out every possible mesh
intersection or establish linguistically correct signing.

Independent audit compares all 248 old action descriptions and the old binary
prefix, geometry, skeleton, skinning, materials, images and textures. It samples
41 poses per new action including between authored keys, finite unit quaternions,
strict timestamps and front torso/face projection depth. This is not a full
closed-surface or finger-to-finger collision test and cannot prove ASL correctness.

## Reproduction

Recover Update-2 GLB and adjacent JSON from checkpoint into a distinct working
filename. Run `expand-text-to-sign-batch3.py BASELINE.glb CANDIDATE.glb REPORT.json`,
then `audit-text-to-sign-everyday.py BASELINE.glb CANDIDATE.glb AUDIT.json
everydayExpansion3`. Use the existing development NumPy/Pillow runtime. Review
actual Android poses and motion before replacing the production bundle/checksum.
Run the existing build wrapper with OriginalWords, unit/controller tests and the
instrumented normal-input test. Source/data checks do not replace signer review.

For the exact exported bundle, recover the GLB and adjacent JSON from candidate
checkpoint **1d9abe3** into a distinct working filename. Run
`correct-text-to-sign-tired.py CHECKPOINT.glb FINAL.glb CORRECTION.json`, then the
independent audit against Update-2 with audit key `everydayExpansion3`. This
targeted patch keeps the other 257 actions and every TIRED finger channel
unchanged, appending only six arm/wrist output arrays (about 7.5 KB). The full
generator also contains the corrected pose, but the exported bundle uses this
minimal patch to preserve the other nine inspected candidates exactly.

TIRED's final wrist correction changes the direction of the slump: bent
fingertips move downward, rather than the initial candidate's upward turn. The
chest-area MCP anchors stay stationary while wrist orientation changes. No finger
pose restrictions or global idle changes are introduced. At sampled active poses
the dominant middle fingertip drops from 1.330 m to 1.273 m, with no measured hand
or forearm penetration in the independent 41-pose test. Qualified ASL review of
contact, facial expression, timing and the complete motion is still required.

## Build and controller evidence

Existing OriginalWords/fake build wrapper: `testDebugUnitTest assembleDebug
assembleDebugAndroidTest`, successful in **10m 34s**; **254 JVM tests, zero
failures/errors**. Existing SDK/Gradle/JDK configuration retained. Debug signature
verified, same certificate SHA256
`5a315db9ca99c70f5f0c127dc8c6558e02d343e5b41d0bf4eee8bb256ce38a8c`.
The existing fake service configuration is unchanged; this is not evidence of
provisioned live account, Gemini or voice services.

Controller tests pass: all 258 action names, **304 word/letter completion
callbacks**, one resident model load/viewer, early/duplicate/stale completion,
rapid cancellation, wrong/missing named clips and model failure. Expected negative
cases log load errors. These are controller mocks, separate from actual Android
rendering and normal-input tests.

Catalog: 232 lexical dictionary entries,
231 unique lexical actions (NAME shares a prior action), 26 letters, neutral;
258 total actions. Validated ASL sentences added: zero.
These are ten new input entries and independently named motion clips, not ten
newly discovered ASL lexemes: HEARING is related to SPEAK and TIRED to EXHAUSTED.

Final APK installation was verified against SHA256 f6bfd28405efb98ae421b0ffe2867f364cf867eb9f31813d1b950cdf778a3340. Installed animation bundle matches the checksum above. Compared with Update-2, unrelated packaged resources, assets and native libraries were unchanged; retained preference files were byte-identical. Final rendered inspection and the full emulator regression do not have a confirmed completion result and must not be reported as passed.

## Exact component files

Relative to the Android project:

- `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb`: append ten native candidate actions; preserve all prior motion/geometry bytes.
- Adjacent `fingerspelling-avatar.json`: entries, senses, references, construction, rights/review status and audit provenance.
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt`: pin the new bundle checksum.
- `app/src/main/java/com/example/apphear/domain/texttoasl/AslVocabularyExpansion.kt`: distinguish reference-authored previews from imported/retargeted previews, require matching action naming and reject unknown construction.
- `app/src/main/java/com/example/apphear/ui/texttoasl/AndroidAssetAslCatalogLoader.kt`: read that optional construction field; legacy entries retain their default.
- `app/src/test/java/com/example/apphear/AslVocabularyExpansionTest.kt`: ten absent words, naming/source existence, explicit unreviewed status, mixed spelling, sense boundaries and rejected candidates.
- `app/src/test/java/com/example/apphear/AslFingerspellingFallbackTest.kt`: updated total action assertion; existing A–Z/fallback tests retained.
- `app/src/androidTest/java/com/example/apphear/AslFingerspellingPlaybackInstrumentedTest.kt`: normal-button tests for ten words, mixtures and retained unknown-word spelling.
- `tools/test-text-to-sign-resident.cjs`: updated total; still exercises every named action and completion/cancellation paths.
- `tools/expand-text-to-sign-batch3.py`: reproducible offline authoring with pinned baseline, geometry preservation, quaternion, reach, length and transform-type guards.
- `tools/correct-text-to-sign-tired.py`: checkpoint-pinned six-channel correction, with assertions preserving the other 257 actions, TIRED fingers and geometry.
- `tools/TextToSignVocabularyBatch3.md`: this component report, references, test evidence and limitations.

No unrelated source file or application feature was changed. No Windows files,
APK exports, original source assets or Git history were removed.
