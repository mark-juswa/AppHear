# AppHear — Phase 2 Dataset Collection Plan

**Document Type:** Dataset Design and Recording Reference  
**Project:** AppHear — Android Sign Language Communication App  
**Phase:** Phase 2 — Dataset Collection for CNN-LSTM Training  
**Depends on:** Phase 1 must be stable (TemporalBuffer, PredictionSmoother, SignStateDetector, DetectionPipelineController implemented)  
**Last Updated:** 2026-05-23  

> This document is the authoritative reference for AppHear's Phase 2 dataset collection. It covers the sign language standard decision, vocabulary, recording protocol, dataset format, and quality standards. Any developer, researcher, or AI assistant picking up this project should read this document before touching data collection.

---

## Table of Contents

1. [Critical Decision: Sign Language Standard](#1-critical-decision-sign-language-standard)
2. [Phase 2 Goals and Dataset Targets](#2-phase-2-goals-and-dataset-targets)
3. [Final Vocabulary — 25 Signs + Background](#3-final-vocabulary--25-signs--background)
4. [Signer Requirements](#4-signer-requirements)
5. [Recording Protocol](#5-recording-protocol)
6. [Signing Variations to Record](#6-signing-variations-to-record)
7. [Background / Rest Class Collection](#7-background--rest-class-collection)
8. [Dataset Folder Structure](#8-dataset-folder-structure)
9. [Sample JSON Format](#9-sample-json-format)
10. [Dataset Split Rules](#10-dataset-split-rules)
11. [Data Quality Checklist](#11-data-quality-checklist)
12. [Updated labels.json](#12-updated-labelsjson)
13. [Realistic Targets Summary](#13-realistic-targets-summary)
14. [What Not To Do](#14-what-not-to-do)
15. [Next Steps After Collection](#15-next-steps-after-collection)

---

## 1. Critical Decision: Sign Language Standard

### Decision required before any recording begins

AppHear must use **one and only one** sign language standard throughout the dataset. Mixing signs from different sign language systems in one dataset degrades model accuracy across the entire vocabulary and makes the app unusable for any real user community.

**Options:**

| Standard | When to choose | Notes |
|---|---|---|
| **Filipino Sign Language (FSL)** | If the app targets Filipino deaf users | More appropriate for a Philippine capstone; fewer public reference datasets |
| **American Sign Language (ASL)** | If the app targets a broader audience or uses existing ASL assets | All current codebase references (TextToAslActivity, asl_animations) already use ASL naming |

**Choose one now. Write it here:**

```
CHOSEN SIGN LANGUAGE STANDARD: _______________
Decision date:                  _______________
Reference dictionary used:      _______________
Confirmed by:                   _______________
```

**Do not change this decision mid-project.** All recorded samples must follow the same standard. If FSL is chosen, use FSL reference videos from institutions such as the Philippine School for the Deaf. If ASL is chosen, use ASL-LEX, Handspeak, or Lifeprint.com.

### Why mixing ASL and FSL causes problems

- A "Hello" sign in ASL and a "Hello" sign in FSL are different motions with different hand configurations
- The model learns inconsistent patterns for conceptually similar signs
- Feature distributions overlap in confusing ways across sign pairs
- Neither the FSL community nor the ASL community is properly served
- Accuracy on real users from either community will be poor

---

## 2. Phase 2 Goals and Dataset Targets

### Purpose of Phase 2

Phase 2 produces a dataset that is used to train the CNN-LSTM model defined in the technical improvement plan. It replaces the current 7-sign model with a 26-class model (25 signs + 1 background class) that generalizes to new signers.

### Dataset size targets

| Version | Signs | Classes | Signers | Samples/sign/signer | Total samples | Goal |
|---|---|---|---|---|---|---|
| **Version 0** (minimum — pipeline validation) | 7 existing + Background | 8 | 4 | 60 | ~1,920 | Prove CNN-LSTM pipeline works |
| **Version 1** (capstone demo) | 25 + Background | 26 | 7 | 80-100 | ~16,380 | Demo-ready, ≥85% test accuracy |
| Version 2 (post-capstone) | 50 + Background | 51 | 15 | 200 | ~153,000 | Research-quality publication |

**Capstone target is Version 1.**

### Background class target

| Scenario | Target samples |
|---|---|
| Total background samples (Version 0) | ≥ 400 |
| Total background samples (Version 1) | ≥ 1,400 |

---

## 3. Final Vocabulary — 25 Signs + Background

### Carry-over from current 7-sign model (re-record with multi-signer protocol)

| # | Sign | Type | Priority | Notes |
|---|---|---|---|---|
| 0 | Hello | Dynamic | Must have | Existing; re-record with all 7 signers |
| 1 | Thank You | Dynamic | Must have | Existing; re-record |
| 2 | You | Dynamic | Must have | Existing; re-record |
| 3 | My | Dynamic | Must have | Existing; re-record |
| 4 | Name | Dynamic | Must have | Existing; re-record |
| 5 | Nice | Dynamic | Must have | Existing; re-record |
| 6 | Meet | Dynamic | Must have | Existing; re-record |

### New additions — Phase 2 (18 new signs)

| # | Sign | Category | Type | Difficulty | Confusable with | Notes |
|---|---|---|---|---|---|---|
| 7 | Goodbye | Greeting | Dynamic | Low | — | Clear wave motion |
| 8 | Yes | Response | Dynamic | Low | — | Head nod + hand sign |
| 9 | No | Response | Dynamic | Low | — | Head shake + hand sign |
| 10 | Please | Response | Dynamic | Medium | Sorry | Circular chest motion |
| 11 | Sorry | Response | Dynamic | Medium | Please | Monitor confusion matrix carefully |
| 12 | Good | Response | Dynamic | Low | — | Useful feedback word |
| 13 | I | Pronoun | Static | Low | — | Point to self |
| 14 | He She | Pronoun | Dynamic | Medium | You | Outward point; direction matters |
| 15 | We | Pronoun | Dynamic | Medium | — | Sweeping motion |
| 16 | Want | Verb | Dynamic | Low | — | Two-handed pull; very distinct |
| 17 | Help | Verb | Dynamic | Low | — | One hand lifted by other |
| 18 | Understand | Verb | Dynamic | Low | — | Index finger flick from forehead |
| 19 | What | Question | Dynamic | Medium | Where | Monitor confusion matrix |
| 20 | Where | Question | Dynamic | Medium | What | Monitor confusion matrix |
| 21 | Who | Question | Dynamic | Medium | — | Circular motion near lips |
| 22 | Stop | Command | Dynamic | Low | — | Flat hand chop; very distinct |
| 23 | More | Basic need | Dynamic | Low | — | Fingertip tap; universally useful |
| 24 | Wait | Command | Dynamic | Low | — | Spread fingers, slight wave |
| 25 | Background | Rest/Transition | — | — | — | Mandatory class; see Section 7 |

**Total: 26 classes (25 signs + 1 background)**

### Signs deliberately excluded from Phase 2 and why

| Sign | Reason for exclusion | Phase to add |
|---|---|---|
| Mother / Father | Same handshape, differ only by location (chin vs. forehead). Need face features. | Phase 3 |
| Happy / Sad / Angry | Require facial expression to disambiguate | Phase 3 |
| Numbers 1-10 | Static handshapes only; many similar (1/D, 3/W). Add as a separate subset. | Phase 3 |
| Full alphabet A-Z | 26 handshapes, many confusable (A/S/N, D/F). Needs better spatial features. | Phase 3 |
| Water / Food | Mouth-area signs; need face features to separate from similar signs | Phase 3 |
| Today / Tomorrow / Yesterday | Require signing space direction understanding | Phase 4 |
| Don't Want / Don't Like | Differ from Want/Like only by palm flip; very confusable | Phase 3 |

---

## 4. Signer Requirements

### Minimum vs. recommended signer count

| Requirement | Minimum | Recommended |
|---|---|---|
| Total signers | 5 | 7-10 |
| Right-handed dominant | 4 | 5-7 |
| Left-handed dominant | 1 | 2 |
| Female signers | 2 | 3-4 |
| Male signers | 2 | 3-4 |
| No prior sign language experience | 2 | 3 |
| Some prior sign language experience | 1 | 2-3 |

### Signer diversity requirements

Each signer must be assigned a unique ID (S01, S02, etc.) before recording begins. Record the following profile information for each signer:

```
Signer ID:          S__
Age group:          18-25 / 25-35 / 35-50
Gender:             M / F / Other
Dominant hand:      Right / Left
Sign experience:    None / Some / Experienced
Hand size:          Small / Medium / Large (self-assessed)
Split assignment:   train / val / test
Notes:              Any relevant physical characteristics
```

### Split assignment guidelines

- **Test signer**: must be someone who signs clearly and consistently (worst case for generalization, best case for evaluation honesty). Assign before recording starts. Never change after any training is done.
- **Validation signer**: medium skill, medium variability
- **Training signers**: all others, include the most varied

With 7 signers: 5 train / 1 val / 1 test.  
With 10 signers: 7 train / 2 val / 1 test.

---

## 5. Recording Protocol

### Step-by-step session procedure

#### Before the session

- [ ] Confirm Phase 1 pipeline is stable and running on the recording device
- [x] Confirm `LandmarkSampleRecorder` is expanded to record pose + hand landmarks
- [ ] Open landmark overlay — verify both shoulders, both hands, and face are tracked
- [ ] Assign signer ID and create signer profile in `signers.json`
- [ ] Print or display the reference sign video for the chosen sign language standard
- [ ] Set environment conditions (lighting, background, shirt) and record them in session metadata
- [ ] Record 5 seconds of signer at rest — confirm landmark tracking is stable

#### Camera setup

```
Camera:     Front-facing only
Height:     At signer's eye level or slightly above
Distance:   60-80 cm from signer's chest (default)
Angle:      Camera perpendicular to signer, no tilt
Frame:      Head, shoulders, and full signing space must be visible
Preview:    Shoulder landmarks visible with visibility > 0.5 on both sides
```

#### Per-sign recording steps

```
1. Display sign label and reference video
2. Signer watches reference 2-3 times
3. Signer practices freely 2-3 times (not recorded)
4. Begin recording: "3 ... 2 ... 1 ... SIGN"
5. Signer performs sign once
6. Signer returns hands to rest for ≥ 1 second
7. Repeat steps 4-6 for 15 repetitions
8. Reviewer accepts/rejects each sample immediately
9. Advance to next sign
10. Break after every 5 signs
```

#### Speed distribution per sign session

```
Repetitions 1-5:   Normal speed (comfortable, natural pace)
Repetitions 6-10:  Slow speed (deliberate, clear execution)
Repetitions 11-15: Fast speed (brisk, natural communication speed)
```

#### Session time planning

```
Setup and calibration:           15 min
10-12 signs × 15 reps × 90 sec: 22-27 min
Background samples:              15 min
Breaks (every 5 signs):          10 min
Review and metadata:             10 min
────────────────────────────────────────
Total per session:               ~75-80 min
Sessions needed per signer:      2-3 (for all 25 signs)
```

### Sample acceptance criteria

**Accept if:**
- Correct sign was performed
- Both hands visible throughout (for two-handed signs)
- Landmark tracking was smooth (no large jumps in overlay)
- Sign had a clear beginning and end without hesitation

**Reject if:**
- Wrong sign was performed
- Signer paused mid-sign or showed visible hesitation
- Hand went out of frame mid-sign
- Strong MediaPipe failure (hand disappeared and reappeared suddenly)
- Signer coughed, sneezed, or was interrupted
- Recording shows less than 70% frames with hand detected

---

## 6. Signing Variations to Record

Every real-world variation that will occur during inference must appear in the training set.

### Speed variations (within each session)

| Speed | Description | Target proportion |
|---|---|---|
| Normal | Natural comfortable pace | 40% |
| Slow | Deliberate, clear execution | 30% |
| Fast | Brisk, natural communication speed | 30% |

### Posture variations (per signer)

| Posture | Requirement |
|---|---|
| Seated | At least 50% of samples across all sessions |
| Standing | At least one full session per signer |

### Distance variations (per signer)

| Distance | Range | Requirement |
|---|---|---|
| Close | 40-50 cm | One session per signer |
| Normal | 60-80 cm | Default for all sessions |
| Far | 90-110 cm | Optional, one session if possible |

### Lighting conditions

| Condition | Setup | Target proportion |
|---|---|---|
| Indoor, good | Well-lit room, ceiling lights on | 50% |
| Indoor, dim | Single lamp, evening conditions | 25% |
| Outdoor / bright | Window light or outdoor | 15% |
| Side lighting | Single light source to one side | 10% |

### Background and clothing

- Record on at least 3 different background colors/types (plain white, plain dark, natural/busy)
- Avoid skin-tone shirts (beige, light tan) — they reduce contrast for hand detection
- Include at least one session per signer with a bright-colored shirt and one with a dark shirt
- Some sessions may include accessories (watch, ring) for real-world robustness

### Handedness

- Record all right-handed signers normally
- For left-handed signers: record normally with dominant left hand
- If no left-handed signers are available: mirror right-handed landmark data in the Python pipeline (flip x-axis of all coordinates, swap left and right hand feature slots)

---

## 7. Background / Rest Class Collection

The background class is mandatory. Without it, the model has no target for "nothing is happening" and will constantly predict wrong signs when the user is at rest or transitioning.

### Background sub-scenarios and targets

| Scenario | Description | Target samples |
|---|---|---|
| Hands at sides | Person standing with arms naturally down | 150 |
| Hands in lap | Person seated, hands resting on legs | 150 |
| Hands on desk | Person at table, hands flat or loose | 100 |
| Talking without signing | Natural mouth/hand movement, no sign | 150 |
| Transition movement | Hands moving between general positions | 200 |
| Unknown sign | Signing something NOT in the vocabulary | 200 |
| Hand near face (non-sign) | Touching face, adjusting hair, thinking | 100 |
| Single hand visible | One-handed context, other out of frame | 100 |
| Empty frame | No person visible or only lower body | 100 |
| Random hand movement | General hand motion, no sign pattern | 150 |
| **Total** | | **1,400** |

### How to record background

- Do not use a formal countdown protocol — these should be casual and natural
- Ask the signer to naturally walk in and out of frame
- Record signer having a conversation with someone off-camera (mouth moving, natural gestures)
- Record the hand position between known signs during a signing session
- Ask the signer to sign 3-4 known signs slowly and record the transitions between them
- Ask the signer to sign something not in the vocabulary (opposite hand, or a completely different gesture)

### Collection requirement

Every signer who records sign samples must also record background samples. The background class must represent the same people the model will see during inference.

Minimum background samples per signer: 200 samples
Total across 7 signers: 1,400 samples

---

## 8. Dataset Folder Structure

```
apphear_dataset/
│
├── labels.json                          ← Master label list (26 classes)
│
├── metadata/
│   ├── signers.json                     ← Signer profiles + split assignments
│   ├── dataset_summary.json             ← Total counts, dates, version
│   └── quality_log.json                 ← Rejection log with reasons
│
├── splits/
│   ├── train_manifest.json              ← Sample IDs assigned to training
│   ├── val_manifest.json                ← Sample IDs assigned to validation
│   └── test_manifest.json               ← Sample IDs assigned to test (held out)
│
├── samples/
│   ├── signs/
│   │   ├── Hello/
│   │   │   ├── S01_001_Hello_0001.json
│   │   │   ├── S01_001_Hello_0002.json
│   │   │   └── ...
│   │   ├── Goodbye/
│   │   ├── Yes/
│   │   ├── No/
│   │   ├── Please/
│   │   ├── Sorry/
│   │   ├── Good/
│   │   ├── I/
│   │   ├── He_She/
│   │   ├── We/
│   │   ├── Thank_You/
│   │   ├── You/
│   │   ├── My/
│   │   ├── Name/
│   │   ├── Nice/
│   │   ├── Meet/
│   │   ├── Want/
│   │   ├── Help/
│   │   ├── Understand/
│   │   ├── What/
│   │   ├── Where/
│   │   ├── Who/
│   │   ├── Stop/
│   │   ├── More/
│   │   └── Wait/
│   │
│   └── background/
│       ├── S01_bg_hands_down_001.json
│       ├── S01_bg_transition_001.json
│       ├── S02_bg_talking_001.json
│       └── ...
│
└── exports/                             ← Generated by Python pipeline, not recorded manually
    ├── train.npz
    ├── val.npz
    └── test.npz
```

### File naming convention

```
Signs:      {SIGNER_ID}_{SESSION_NUMBER}_{LABEL}_{REP_INDEX:04d}.json
Background: {SIGNER_ID}_bg_{SCENARIO}_{REP_INDEX:04d}.json

Examples:
  S01_001_Hello_0003.json
  S03_002_Thank_You_0012.json
  S05_bg_transition_0007.json
```

---

## 9. Sample JSON Format

### Sign sample

```json
{
  "sample_id":        "a3f2c1d4-7b8e-4f01-9a2b-3c4d5e6f7a8b",
  "label":            "Hello",
  "label_index":      0,
  "sign_language":    "FSL",
  "signer_id":        "S01",
  "session_id":       "S01_Session001",
  "recording_date":   "2026-05-23",
  "repetition_index": 3,
  "camera_direction": "front",
  "speed":            "normal",
  "posture":          "seated",
  "distance_cm":      70,
  "lighting":         "indoor_good",
  "background":       "plain_white",
  "shirt_color":      "dark_blue",
  "dominant_hand":    "right",
  "validated":        true,
  "rejected_reason":  null,
  "frame_count":      30,
  "feature_size":     258,
  "mediapipe_version": "0.10.14",
  "app_version":      "phase2_recorder_v1",
  "frames": [
    [0.012, -0.341, 0.054, 0.98, 0.002, -0.310, 0.071, 0.95, "..."],
    "... 30 arrays of 258 floats each ..."
  ]
}
```

### Feature vector layout (258 floats per frame)

```
Indices   0 – 131  : Pose landmarks (33 × 4 values: x, y, z, visibility) — nose-normalized
Indices 132 – 194  : Signer's LEFT hand (21 × 3 values: x, y, z) — wrist-normalized
Indices 195 – 257  : Signer's RIGHT hand (21 × 3 values: x, y, z) — wrist-normalized

All values produced by KeypointExtractor.extract(poseResult, handResult, isFrontCamera=true)
with front-camera handedness correction applied.
If a hand is not detected, its 63 float slots are filled with 0.0.
```

### Background sample

```json
{
  "sample_id":      "b8e1a2c3-...",
  "label":          "Background",
  "label_index":    25,
  "sign_language":  "FSL",
  "signer_id":      "S02",
  "session_id":     "S02_Session001",
  "recording_date": "2026-05-23",
  "bg_scenario":    "hands_in_lap",
  "validated":      true,
  "frame_count":    30,
  "feature_size":   258,
  "frames":         [ "... 30 arrays of 258 floats ..." ]
}
```

### Python loading function

```python
import json
import numpy as np
import os

def load_apphear_dataset(dataset_root, split_manifest_path):
    """
    Load AppHear landmark samples from JSON files.
    
    Args:
        dataset_root: Path to the root of apphear_dataset/
        split_manifest_path: Path to train_manifest.json, val_manifest.json, or test_manifest.json
    
    Returns:
        X: np.ndarray of shape (N, 30, 258) — landmark sequences
        y: np.ndarray of shape (N,) — label indices
        meta: list of dicts with signer_id, label, sample_id etc.
    """
    with open(split_manifest_path) as f:
        manifest = json.load(f)
    
    X, y, meta = [], [], []
    
    for sample_path in manifest["sample_paths"]:
        full_path = os.path.join(dataset_root, sample_path)
        with open(full_path) as f:
            sample = json.load(f)
        
        if not sample.get("validated", False):
            continue
        if len(sample["frames"]) != 30:
            continue
        
        X.append(sample["frames"])
        y.append(sample["label_index"])
        meta.append({
            "sample_id": sample["sample_id"],
            "signer_id": sample["signer_id"],
            "label":     sample["label"],
            "speed":     sample.get("speed", "unknown")
        })
    
    return (
        np.array(X, dtype=np.float32),
        np.array(y, dtype=np.int32),
        meta
    )

# Usage:
X_train, y_train, meta_train = load_apphear_dataset(
    "apphear_dataset", "apphear_dataset/splits/train_manifest.json")

print(f"Training set: {X_train.shape}")  # (N_train, 30, 258)
```

---

## 10. Dataset Split Rules

### The mandatory rule: split by signer, not by sample

**Never randomly shuffle all samples and assign 70/15/15 to train/val/test.**

This produces inflated accuracy — the model memorizes signer-specific patterns and evaluates on samples from the same signers it trained on. When a real new user (a new signer) tries the app, accuracy drops significantly.

**Correct split: assign entire signers to each split.**

| Split | Signers (from 7 total) | Purpose |
|---|---|---|
| **Training** | S01, S02, S03, S04, S05 | Model learns from these signers |
| **Validation** | S06 | Hyperparameter tuning, early stopping |
| **Test** | S07 (held out entirely) | Final honest accuracy report |

### Test signer rules

- The test signer (S07) must have **zero samples in training or validation**
- The test signer's data must not be looked at until training is fully complete
- The final accuracy number reported in the capstone must be from the test signer only
- The test signer must be someone who was not involved in any model design decisions

### Verification script (run before training)

```python
import json

with open("apphear_dataset/metadata/signers.json") as f:
    signers = json.load(f)

train_signers = set(signers["split_assignments"]["train"])
val_signers   = set(signers["split_assignments"]["val"])
test_signers  = set(signers["split_assignments"]["test"])

# No signer should appear in more than one split
assert train_signers.isdisjoint(val_signers),  "LEAK: signer in both train and val"
assert train_signers.isdisjoint(test_signers), "LEAK: signer in both train and test"
assert val_signers.isdisjoint(test_signers),   "LEAK: signer in both val and test"

print("Split verification passed. No signer leakage.")
```

---

## 11. Data Quality Checklist

### Automated checks (built into recording tool — reject automatically)

- [ ] Frame count equals exactly 30
- [ ] At least 70% of frames have at least one hand detected (non-zero hand slots)
- [ ] At least one shoulder has visibility > 0.3 in at least 80% of frames
- [ ] No individual frame is entirely zero (complete MediaPipe failure)
- [ ] JSON file is valid and all required metadata fields are present
- [ ] `label` matches one entry in `labels.json` exactly (case-sensitive, exact string)
- [ ] `label_index` matches `label_to_index` mapping in `labels.json`

### Human review checks (done during or immediately after recording)

- [ ] Signer performed the correct sign as shown in the reference
- [ ] Sign was performed completely (not cut off at start or end)
- [ ] Both hands visible for the full sign (for two-handed signs)
- [ ] No visible hesitation, pause, or restart mid-sign
- [ ] No interruption (cough, sneeze, distraction)
- [ ] No major MediaPipe tracking failure visible in the overlay
- [ ] Speed matches the declared speed label (normal / slow / fast)
- [ ] Dominant hand matches the declared dominant hand in metadata

### Dataset-level checks (run before the training pipeline)

- [ ] Each of the 26 label classes has samples in the training split
- [ ] No single signer contributes more than 35% of any class
- [ ] Background class has at least 400 samples in training split
- [ ] Test signer (S07) has zero samples in training or validation splits
- [ ] All `label_index` values are in range [0, 25]
- [ ] Metadata files are internally consistent (signer IDs match across files)
- [ ] Class distribution across training split is checked and roughly balanced

---

## 12. Updated labels.json

This is the `labels.json` file that replaces `assets/labels.json` in the Android project **at the same time** as the retrained TFLite model is deployed. Do not update this file without updating the model simultaneously. The `ModelMetadataValidator` will catch any mismatch.

```json
{
  "sign_language":   "FSL",
  "version":         "2.0",
  "last_updated":    "2026-05-23",
  "sequence_length": 30,
  "feature_size":    258,
  "label_count":     26,
  "labels": [
    "Hello",
    "Thank You",
    "You",
    "My",
    "Name",
    "Nice",
    "Meet",
    "Goodbye",
    "Yes",
    "No",
    "Please",
    "Sorry",
    "Good",
    "I",
    "He She",
    "We",
    "Want",
    "Help",
    "Understand",
    "What",
    "Where",
    "Who",
    "Stop",
    "More",
    "Wait",
    "Background"
  ],
  "label_to_index": {
    "Hello":      0,
    "Thank You":  1,
    "You":        2,
    "My":         3,
    "Name":       4,
    "Nice":       5,
    "Meet":       6,
    "Goodbye":    7,
    "Yes":        8,
    "No":         9,
    "Please":     10,
    "Sorry":      11,
    "Good":       12,
    "I":          13,
    "He She":     14,
    "We":         15,
    "Want":       16,
    "Help":       17,
    "Understand": 18,
    "What":       19,
    "Where":      20,
    "Who":        21,
    "Stop":       22,
    "More":       23,
    "Wait":       24,
    "Background": 25
  },
  "background_label":       "Background",
  "background_label_index": 25
}
```

---

## 13. Realistic Targets Summary

### Version 0 — Pipeline validation (start here first)

```
Signs:          7 existing + Background = 8 classes
Signers:        4 (team members)
Samples/sign:   60 per signer
Total samples:  4 × 8 × 60 = ~1,920
Split:          3 train / 1 test
Goal:           Confirm CNN-LSTM pipeline works end-to-end
Expected acc:   75-85% on test signer
Time to record: ~6 hours total
```

**Build this before investing in the full 25-sign dataset. Prove the pipeline works first.**

### Version 1 — Capstone demo target

```
Signs:          25 + Background = 26 classes
Signers:        7
Samples/sign:   80-100 per signer
Total samples:  7 × 26 × 90 = ~16,380
Split:          5 train / 1 val / 1 test
Goal:           Real-signer demo, ≥85% test accuracy
Expected acc:   82-90% on test signer with data augmentation
Time to record: ~18 hours total (2-3 hours per signer × 7 signers)
```

### Version 2 — Post-capstone / research quality

```
Signs:          50 + Background = 51 classes
Signers:        15
Samples/sign:   200 per signer
Total samples:  15 × 51 × 200 = ~153,000
Split:          10 train / 3 val / 2 test
Expected acc:   90-95% on test signers
```

---

## 14. What Not To Do

- **Do not start recording before choosing the sign language standard.** Mixing ASL and FSL destroys the dataset.
- **Do not split the dataset randomly by sample.** Always split by signer. Random splitting inflates accuracy by 15-25% and makes the results meaningless.
- **Do not skip the background class.** Even Version 0 must have a background class. This is not optional.
- **Do not record all 25 signs in one 3-hour session per signer.** Signer fatigue changes signing style in the later signs. Split into 2-3 sessions of 10-12 signs each.
- **Do not record all signers on the same day.** Physical fatigue and session conditions should be varied.
- **Do not train the model before running the split verification script.** Confirm zero signer leakage before any training begins.
- **Do not update labels.json without simultaneously replacing sign_classifier.tflite.** The ModelMetadataValidator will catch this mismatch but updating one without the other will break predictions during development.
- **Do not accept samples where the signer is clearly signing the wrong word.** Noisy labels are worse than fewer samples.
- **Do not use validation accuracy as the primary accuracy metric if the split is not by signer.** Only the test signer accuracy matters.
- **Do not delay background class collection.** Record it in the very first session with the first signer.

---

## 15. Next Steps After Collection

After all samples are recorded and validated:

### Step 1: Export to NumPy arrays

Run the Python export script to convert all JSON samples to compressed `.npz` files for fast loading during training:

```python
X_train, y_train, _ = load_apphear_dataset("apphear_dataset", "splits/train_manifest.json")
X_val,   y_val,   _ = load_apphear_dataset("apphear_dataset", "splits/val_manifest.json")
X_test,  y_test,  _ = load_apphear_dataset("apphear_dataset", "splits/test_manifest.json")

np.savez_compressed("apphear_dataset/exports/train.npz", X=X_train, y=y_train)
np.savez_compressed("apphear_dataset/exports/val.npz",   X=X_val,   y=y_val)
np.savez_compressed("apphear_dataset/exports/test.npz",  X=X_test,  y=y_test)
```

### Step 2: Dataset statistics report

Before training, generate and review:
- Class distribution histogram (are classes balanced?)
- Per-signer sample count (any signer over-represented?)
- Rejection rate per sign (any signs with high rejection suggest recording quality issues)

### Step 3: Data augmentation in Python

Apply augmentation only to the training set during training (not validation or test):
- Coordinate jitter: Gaussian noise σ=0.02
- Speed variation: subsample at 0.8x or 1.2x, interpolate back to 30 frames
- Mirror/flip: flip x-axis, swap left/right hand slots (simulate left-handed signers)
- Landmark dropout: randomly zero 1-3 landmarks per frame
- Temporal shift: shift sequence start by ±3 frames

### Step 4: Train CNN-LSTM model (Phase 3)

Use the Phase 3 training pipeline:
```
Architecture: TimeDistributed(Dense 128) → TimeDistributed(Dense 64) → LSTM(128) → LSTM(64) → Dense(26, softmax)
Loss:         Categorical cross-entropy
Optimizer:    Adam (lr=0.001)
Batch size:   32
Early stop:   patience=10 on val_loss
```

### Step 5: Convert to TFLite and deploy

```python
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]  # INT8 quantization
tflite_model = converter.convert()
with open("sign_classifier.tflite", "wb") as f:
    f.write(tflite_model)
```

Replace `assets/sign_classifier.tflite` and `assets/labels.json` in the Android project simultaneously.

### Step 6: Validate with ModelMetadataValidator

On app startup, `ModelMetadataValidator` will confirm the new model matches the new `labels.json` and `KeypointExtractor.FEATURE_SIZE`. Check Logcat for `ModelMetadataValidator: Model metadata validation passed`.

### Step 7: Test on unseen signers

Run the user testing protocol from the handout with at least 2-3 signers who were not in any training or validation set. Measure:
- First-attempt recognition rate per sign
- Overall sentence accuracy for 3-sign sequences
- False positive rate during rest/transition

---

*End of Phase 2 Dataset Collection Plan*  
*Next document: PHASE_3_CNN_LSTM_TRAINING_PLAN.md*  
*Related: APPHEAR_SIGN_DETECTION_IMPROVEMENT_HANDOUT.md, APPHEAR_FULL_SYSTEM_ANALYSIS.md*
