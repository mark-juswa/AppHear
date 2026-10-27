# 3D-LEX ASL motion attribution

Update 8 (24 October 2026): 49 additional ASL motions were adapted directly
from ASL_ANIM_GLB.zip (SHA-256 bac3e8ca0dbcc45eec0952a20dd04f28cc38131baddc8a354a72da673af0bdc7).
47 contain a terminal global hip flip into the exported bind pose. Only that
mechanically invalid final frame was excluded after checking the whole-skeleton
bind reset; interior source signing frames were retained. Exact source files,
hashes, excluded times and adaptation checks are in integration-manifest.json.
The original archive is unchanged. Contextual playback bypasses only the added
0.2-second rest padding between different consecutive signs and blends their
poses. All new entries remain unreviewed previews, not certified ASL translations.

Source: Oline Ranum, Gomèr Otterspeer, Jari I. Andersen, Robert G. Belleman,
and Floris Roelofsen (2024). 3D-LEX v1.0: 3D Lexicons for American Sign
Language and Sign Language of the Netherlands. Only the ASL Animation Data
component is used here; no NGT animations are included.

Dataset: https://osf.io/cv276/
ASL animation component: https://osf.io/mqzyk/
Paper: https://aclanthology.org/2024.signlang-1.33/
Dataset licence: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
Legal terms: https://creativecommons.org/licenses/by/4.0/legalcode
License record: https://api.osf.io/v2/licenses/563c1cf88c5e4a3877f9e96a/
Official release licence index: https://www.sign-lang.uni-hamburg.de/lrec/data/3dlexv10.html

Changes: 200 source motions retargeted to AppHear's pre-existing human
skeleton at 24 Hz, rotation only, with 0.2-second neutral entry and exit.
Fixed bone-local axes are calibrated from median source offsets. Source
rotation tracks are transferred with fixed target bone lengths. Mechanically
invalid short reset suffixes are excluded with exact source ranges recorded
per entry in manifest.json; interior corruption rejects the entire candidate.
Source archives are unchanged. Abrupt rotations and excessive directional
error reject candidates. Source meshes, textures and animated scale are not copied.
All pre-existing avatar geometry and 258 actions are retained unchanged.
Per-motion source names and SHA-256 identities are in manifest.json.

The CC BY licence covers the imported 3D-LEX motion. It does not establish
rights to AppHear's pre-existing avatar or motions; those remain separately
documented/unresolved. No endorsement by the authors is implied.

UNREVIEWED PREVIEWS: source lexical labels and retargeted signing have not
received qualified ASL review. Facial blendshape grammar is unavailable.
These entries are not validated sentence translations or linguistic ground truth.

This package substitutes only WHY, YOU, YOUR/YOURS, and TODAY motion previews.
No new lexical entries or aliases are added. All previous 458 actions remain unchanged.
The new motions remain UNREVIEWED; no qualified ASL or phone approval is implied.

WHERE is also substituted. Its final source calibration-reset frame at 4.833333492s is excluded; retained through 4.791666508s. This is mechanical export cleanup, not a verified linguistic boundary. Source archive unchanged.

Authorized 647-entry preview: 215 additional source motions and 51 English aliases from the same verified ASL release, reusing frozen prior curation without reprocessing. All previous463 actions and five word substitutions are preserved. Aliases are not counted as additional signs. This remains an unreviewed word/expression preview, not qualified sentence translation.

Selective three-source integration: compatible rotation actions copied into the existing human GLB; original mesh, skin, alphabet and neutral tracks unchanged. 404 new external entries are active. 16 external overlaps and 36 primary rollback actions are retained as inactive review alternatives. No qualified ASL validation.

Update 9 (24 October 2026): 32 additional motion-backed lexical previews from
the same CC BY 4.0 ASL archive, bringing the catalog to 743 entries. Only an
identified terminal publisher coordinate-reset sample is excluded: the exact
partially baked Armature reset signature, simultaneous >150-degree global hip
jump within 1/12 second, and independently near-bind articulation are required.
No interior frame, finger pose, avatar mesh, rig, skin, alphabet, or existing
animation is changed. All earlier 789 actions and their binary data are exact.
Per-entry source hashes and excluded time ranges are in integration-manifest.json.
These motions remain UNREVIEWED ASL previews; 1,000 supported signs have not
been achieved. Missing/corrupt/duplicate data is not replaced with invented signs.

Shoulder calibration (25 October 2026): 465 imported motions have a constant
clavicle baseline corrected using a stable arms-down source preroll. A two-bone
arm solve retains the original world-space wrist position and hand orientation;
every local finger track, animation clock, alphabet, mesh and skin is unchanged.
Twenty clips without a safe neutral lead-in retain their original motion.
This is a derivative technical calibration of the credited 3D-LEX motions,
not linguistic validation. See shoulderCalibration in integration-manifest.json
and the independent verification report for bounds and exceptions.


Word-hand repair preview (25 October 2026): 38 existing lexical motions were
replaced with independently screened ASL motions from the same CC BY 4.0
archive. No vocabulary entries were added. Fixed-axis retargeting and stable
preroll shoulder calibration reuse this same human rig. Source animation reset
suffixes are excluded only by the existing pinned export signatures. Source
files, SHA-256 identities, durations and checks are recorded in wordHandRepair
in integration-manifest.json. Other selected clips have isolated return-to-pose
finger-key spikes repaired, plus reference-guided SCHOOL and HELP handshapes.
Alphabet and avatar geometry are unchanged. No qualified ASL validation is claimed.

## FBX motion expansion (2026-10-25)

41 additional ASL lexical previews are derived from the original 3D-LEX v1.0 ASL FBX motion archive: https://osf.io/mqzyk/ . License record: https://www.sign-lang.uni-hamburg.de/lrec/data/3dlexv10.html (CC BY 4.0). Original archive SHA256: 6ee2bd5b7ead8f601d2d77345cc6fcfe0b9a323970ca6a9ec316c408298336eb. Individual archive-member and motion hashes are in integration-manifest.json.

Changes: skeleton-only export using Three.js 0.180.0 (MIT), source-relative key clocks, existing anatomical retargeting with gated minimal-swing adaptation where necessary, existing stable-preroll shoulder calibration, and exact terminal exporter-reset exclusion. Target human rig, mesh, alphabet and all 821 previous animation actions are preserved. Raw source files remain unchanged. Identical buffer storage is deduplicated losslessly.

These previews are not qualified-ASL-signer validated. Of 262 previously unavailable source word names, 166 files were empty/static, 16 moving candidates failed mechanical gates, and 39 further candidates were held for contact review. Fingerspelling remains available for excluded words. No source avatar meshes or textures, third-party videos, or recognition data are included by this expansion.

## ARRIVE contact/handshape correction (2026-10-26)

ARRIVE is derived from the same CC BY 4.0 ASL FBX archive. The recorded timing, body motion and thumbs are retained; four-finger flat-hand positions reuse the existing AppHear B pose, mirrored through anatomical rest frames for the left hand. Bounded right-arm IK corrects the palm-contact overlap while retaining wrist/finger world orientation. The existing B asset and its prior provenance limitations remain unchanged; no new source avatar mesh, texture or instructional video is included. Reference: https://www.lifeprint.com/asl101/pages-signs/a/arrive.htm .

All 862 pre-existing actions, including the alphabet and idle, are preserved. The candidate passed CPU skinning checks and 347 sampled transverse-triangle checks at 1 mm tolerance. This is a technical preview requiring qualified ASL validation; it is not a validated phrase or a claim of linguistic accuracy. Other held words are not registered by this correction.
