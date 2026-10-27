# Word hand repair batch (2026-10-25)

This batch repairs 74 existing lexical actions. It does not add vocabulary,
replace the human mesh, constrain the live skeleton, or change recognition.
The result remains a technical preview requiring qualified ASL review.

## Findings and corrections

The baseline contains isolated finger quaternion excursions which return to
nearly the same pose within 100 ms. These are stored animation keys, not evidence
of a generally defective skin or bind pose. The repair removes only isolated
outliers with independently close neighbouring anchors. Sustained handshapes,
adjacent suspect keys and endpoints are excluded; no universal joint clamp or
whole-sign smoothing is applied.

SCHOOL and HELP also receive explicit reference-guided hand profiles. SCHOOL
uses flat hands; HELP uses a supporting flat hand and the resident rig's closed
fingers. Thumb channels are retained where a reliable replacement was not
established. STUDENT's initial flat-hand correction was superseded by a licensed
source-motion replacement.

38 actions use screened CC BY 4.0 3D-LEX source motions, retargeted to the same
resident rig. Source checksums, exclusions and conversion checks are recorded in
`word-motion-replacement-profiles.json`. Target mesh, skin, bind transforms and
bone lengths are unchanged. The converter uses a fixed anatomical calibration
rather than rebuilding finger axes from an animated palm at each frame. Only
stable arms-down source preroll is shoulder-calibrated, preserving world-space
hand motion. This is not a global shoulder lock.

Replacement clips have 0.2-second synthetic entry/exit padding. The catalog
loader reads explicit per-action padding metadata so the existing queue can
skip these neutral margins between consecutive signs. Letter clips are not
eligible for this override. Durations and integrity hashes are synchronized.

## Reproduce candidates before applying

Run from the repository root, with Python and NumPy available. Keep outputs in
an ignored scratch directory. Do not run against an unknown baseline.

```text
python android/tools/repair-word-hand-key-spikes.py --source BEFORE.glb --output KEYS.glb --report KEYS.json
python android/tools/stage-word-motion-repairs.py ASL_ANIM_GLB.zip PINNED_CONVERTER.py BEFORE.glb STAGE_DIR
python android/tools/package-word-motion-repairs.py KEYS.glb STAGE_DIR/source-motion AFTER.glb MOTIONS.json
python android/tools/verify-word-hand-repairs.py BEFORE.glb AFTER.glb KEYS.json VERIFICATION.json --motion-profiles android/tools/word-motion-replacement-profiles.json --staged-motions STAGE_DIR/source-motion
```

The archive and external converter are intentionally not vendored. Staging
requires their pinned checksums and aborts on unexpected inputs. See attribution
and profile records for provenance. Do not substitute differently named motions.

## Regression protection

The full-action fixture and `AslWordHandRepairGateTest` cover all 821 actions,
including the 26 unchanged alphabet actions. The 36 non-replacement actions
preserve clocks, endpoints and unlisted channels. Historical motion-pin tests
accept only explicitly reviewed replacement hashes, not arbitrary new bytes.
The JVM suite passed 370 tests. Production playback tests and still-pose
instrumentation are separate: diagnostic seeking/replay does not establish
uninterrupted queue completion or ASL correctness.

## Remaining limitations

Fast finger-key warnings remain; stable-axis full wrist-turn candidates remain
in CLOSE, EXCUSE ME, HUSBAND, IMPORTANT, LET, PAY, PAY SOMEONE, PEOPLE and WIFE.
Large swing angles can make twist decomposition ambiguous. Contact detectors
also flag legitimate two-handed or body-contact signs, so their flags are review
requests rather than automatic evidence of incorrect signing.

NECKLACE, HEAD, CHOKE, EYEGLASSES, TABLE and ACCOMPLISH retain concerning contact
placement. Target/source body proportions can affect orientation-only retargets;
no unvalidated global collision push-out was applied. Existing LOVE, YOU, YOUR,
ME/I and YES were preserved. A warning alone is insufficient to replace a
previously reviewed sign. FINISH was already repaired in the baseline.

Native regression results: 171 normal playback cases passed, including all 26
letter actions across individual/mixed inputs and rapid cancellation. 87 lexical
entries (all 74 changed entries plus 13 controls) received six-pose captures and
rotation comparisons; maximum sampled mismatch was below 0.000003 degrees with
one active animation owner and one visible avatar. All 87 screenshot sheets were
reviewed. Five entries also received denser fixed-camera captures: PLAY, RUN,
PAPER, HELP and STUDENT. Sparse sampling can miss their short central stroke.

These tests do not clear complete signs: BOOK, BUY, CLOSE, HUSBAND, LITTLE,
DRIVE and other flagged entries still require individual correction/review.
HELP's right-finger component changed, but the required supporting-hand movement
was not established in the dense captures. Its source replacement was rejected
for invalid interior bone lengths. Do not advertise HELP as a fully repaired ASL
sign. Qualified ASL validations remain zero.

References: https://www.lifeprint.com/asl101/pages-signs/s/school.htm ,
https://www.lifeprint.com/asl101/pages-signs/s/student.htm ,
https://www.lifeprint.com/asl101/pages-signs/h/help.htm . Motion license record:
https://www.sign-lang.uni-hamburg.de/lrec/data/3dlexv10.html ;
source: https://osf.io/mqzyk/ . No reference videos were redistributed.
