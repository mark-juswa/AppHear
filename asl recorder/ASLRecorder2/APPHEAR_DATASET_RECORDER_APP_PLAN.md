# APPHEAR_DATASET_RECORDER_APP_PLAN.md

**Document Type:** Developer Handoff — App Design and Architecture Plan
**App Name:** AppHear Dataset Recorder
**Package:** `com.example.aslrecorder`
**Purpose:** Phase 2 Dataset Collection for AppHear CNN-LSTM Sign Language Model
**Depends on:** PHASE_2_DATASET_COLLECTION_PLAN.md (authoritative reference for dataset requirements)
**Last Updated:** 2026-05-25

> This document is the authoritative design and architecture reference for the AppHear Dataset Recorder app. Any developer or AI assistant picking up this project should read this document before writing any code. All recording logic, screen designs, quality rules, folder structures, and class responsibilities are specified here.

---

## Table of Contents

1. [App Purpose and Scope](#1-app-purpose-and-scope)
2. [Why a Separate Recorder App Is Needed](#2-why-a-separate-recorder-app-is-needed)
3. [Main User Flow](#3-main-user-flow)
4. [App Screens](#4-app-screens)
5. [Recording Logic and State Machine](#5-recording-logic-and-state-machine)
6. [Landmark Overlay and Guidance System](#6-landmark-overlay-and-guidance-system)
7. [Automatic Sample Quality Check](#7-automatic-sample-quality-check)
8. [Manual Review Option](#8-manual-review-option)
9. [Data Format — JSON Sample Schema](#9-data-format--json-sample-schema)
10. [Folder Structure](#10-folder-structure)
11. [File Naming Convention](#11-file-naming-convention)
12. [Counter and Progress System](#12-counter-and-progress-system)
13. [Background / Rest Recording Mode](#13-background--rest-recording-mode)
14. [Android Technical Architecture](#14-android-technical-architecture)
15. [MediaPipe and CameraX Integration](#15-mediapipe-and-camerax-integration)
16. [Storage and Permissions](#16-storage-and-permissions)
17. [UI/UX Requirements](#17-uiux-requirements)
18. [Code-Level Guidance — Pseudocode](#18-code-level-guidance--pseudocode)
19. [Minimum Viable Version (MVP)](#19-minimum-viable-version-mvp)
20. [Advanced Features for Later](#20-advanced-features-for-later)
21. [Next Development Steps](#21-next-development-steps)

---

## 1. App Purpose and Scope

**AppHear Dataset Recorder** is a standalone Android utility app whose sole purpose is to collect, validate, organize, and save landmark-based sign language training data for the AppHear Phase 2 CNN-LSTM model.

This is **not** the main AppHear communication app. It does not perform sign recognition, TTS, or avatar animation. It records MediaPipe landmark sequences from live camera input and saves them as structured JSON files on the device.

### What the app does

- Guides a signer through a structured recording protocol
- Captures 30-frame MediaPipe landmark sequences per sign attempt
- Automatically checks each sample for technical recording quality
- Saves accepted and rejected samples in organized folders
- Records full metadata per sample (signer, session, speed, posture, lighting)
- Supports all 25 sign labels plus the Background class from the Phase 2 plan
- Supports both FSL and ASL standards
- Produces a dataset that can be loaded directly by the Phase 3 Python CNN-LSTM training pipeline

### What the app does NOT do

- It does not recognize or classify signs (no TFLite model)
- It does not determine whether the signer performed the sign correctly in a semantic sense
- It does not replace human review of sign correctness
- It does not train models or export TFLite files
- It is not the communication interface for deaf users

### Primary users

| User type | Role |
|---|---|
| Signer (S01–S07) | Performs signs in front of the camera |
| Session operator / researcher | Sets up session parameters, monitors recording quality |
| Dataset reviewer | Reviews accepted/rejected samples, approves final dataset |

---

## 2. Why a Separate Recorder App Is Needed

Manually recording sign data without a dedicated tool produces inconsistent, hard-to-use datasets. The following table explains the specific problems solved by this app.

| Problem without app | How the recorder app solves it |
|---|---|
| Samples are different lengths | App captures exactly 30 frames per sample every time |
| Labels are entered manually and often wrong | Label is selected before recording; it is auto-applied to every sample in the session |
| No metadata is captured | App records signer ID, session ID, speed, posture, lighting, background, shirt color per sample |
| No quality checking | App automatically rejects samples where hands are not visible, tracking fails, or frames are missing |
| No folder structure | App saves to `AppHearDataset/samples/signs/Hello/accepted/` automatically |
| Researcher does not know how many good samples exist | App shows live counter: Accepted 12/60, Remaining 48, Rejected 3 |
| Rejected samples are lost or mixed with good ones | Rejected samples go to a separate `rejected/` subfolder with the rejection reason in the filename and JSON |
| Hard to re-record only the bad samples | App tracks which samples are rejected and offers a "Redo Rejected" workflow |
| No countdown or pacing guidance | App shows 3-2-1-SIGN countdown before every attempt |
| Signer does not know if they are in frame | Live landmark overlay + visual tracking status indicators guide the signer |
| Dataset is not retraining-ready | Output format matches the Phase 2 JSON schema expected by the Python training pipeline |

---

## 3. Main User Flow

```
App Launch
  └── Home Screen
        ├── [Continue Session] → Session already exists → Resume Recording
        │
        └── [Start New Session]
              │
              ├── Step 1: Choose Sign Language Standard (FSL / ASL)
              │
              ├── Step 2: Create or Select Signer Profile
              │     └── Enter: Signer ID, dominant hand, age group, gender, experience, split assignment
              │
              ├── Step 3: Session Setup
              │     └── Enter: sign label, target reps, speed, posture, distance, lighting,
              │             background, shirt color, session number
              │
              ├── Step 4: Pre-Recording Check
              │     └── App shows live camera + overlay
              │         Guidance: "Center your body", "Move back", "Hands in frame"
              │         Green indicator when tracking is stable
              │         [Ready — Start Recording] button
              │
              ├── Step 5: Recording Loop
              │     └── Countdown: 3 → 2 → 1 → SIGN
              │           ↓
              │         User performs sign
              │           ↓
              │         App captures 30 frames
              │           ↓
              │         Quality check runs
              │           ↓
              │         ┌─ ACCEPTED → counter +1, REST pause, next countdown
              │         └─ REJECTED → reason shown, [Redo] or [Skip] offered
              │
              ├── Step 6: Session Complete
              │     └── "60/60 accepted" shown
              │         Summary: total attempts, accepted, rejected, redo needed
              │         [Save & Finish] → files written to folder
              │         [Redo Rejected Samples] → re-enter recording loop for rejected only
              │
              └── Step 7: Review and Export
                    └── Review screen: view accepted/rejected, open file, mark manually
                        Export: ZIP session folder
                        Next: record another sign label
```

---

## 4. App Screens

### A. Home Screen

**Purpose:** Entry point. Shows session status and dataset statistics at a glance.

**Layout (card-based, inspired by reference design):**

```
┌──────────────────────────────────┐
│  AppHear Dataset Recorder        │
│  Good morning, S01               │
│                                  │
│  ┌────────────────────────────┐  │
│  │  Dataset Progress          │  │
│  │  Accepted samples: 420     │  │
│  │  Signs recorded: 7 / 25    │  │
│  │  Last session: 2026-05-24  │  │
│  └────────────────────────────┘  │
│                                  │
│  [ + Start New Session     ]     │  ← large dark button
│  [ ↩  Continue Last Session]     │
│                                  │
│  ┌─────────┐  ┌─────────┐        │
│  │ Browse  │  │ Export  │        │
│  │ Dataset │  │ Dataset │        │
│  └─────────┘  └─────────┘        │
│                                  │
│  [ ⚙ Settings ]                  │
└──────────────────────────────────┘
```

**Contents:**
- App title and current signer greeting
- Dataset progress card: total accepted samples, signs completed out of 25, last session date
- Start New Session button (primary action)
- Continue Last Session button (secondary, grayed out if no session exists)
- Browse Dataset card: open DatasetBrowserActivity
- Export Dataset card: trigger ZIP export
- Settings link: sign language standard, storage path, MediaPipe config

---

### B. Signer Profile Screen

**Purpose:** Create or select the signer before a session begins. Each signer gets a unique ID that is embedded in every JSON sample they produce.

**Fields:**

| Field | Type | Options / Notes |
|---|---|---|
| Signer ID | Text (auto-suggested: S01–S99) | Must be unique, used in filenames |
| Full name / nickname | Text | Optional, not saved in sample JSON |
| Age group | Dropdown | 18-25 / 25-35 / 35-50 |
| Gender | Dropdown | Male / Female / Other / Prefer not to say |
| Dominant hand | Toggle | Right / Left |
| Sign experience | Dropdown | None / Some / Experienced |
| Hand size | Toggle | Small / Medium / Large (self-assessed) |
| Split assignment | Dropdown | train / val / test |
| Notes | Multi-line text | Any relevant physical characteristics |

**Actions:**
- Save Profile → writes to `metadata/signers.json`
- Select Existing → loads saved signer list from `signers.json`
- Delete Profile → removes signer from list (with confirmation)

**Validation rules:**
- Signer ID is required and must be unique
- Split assignment is required before saving
- Warn if a test signer already exists (only 1 test signer per dataset)

---

### C. Session Setup Screen

**Purpose:** Configure all session metadata that will be embedded in every sample recorded in this session. These fields map directly to the Phase 2 JSON schema.

**Fields:**

| Field | Type | Options |
|---|---|---|
| Sign language standard | Toggle | FSL / ASL |
| Sign label | Dropdown + search | 25 signs + Background (from labels.json) |
| Target repetitions | Number input | Default 60; min 15; max 200 |
| Speed variation | Radio group | Normal / Slow / Fast |
| Posture | Radio group | Seated / Standing |
| Distance from camera (cm) | Slider | 40 / 60 / 70 / 90 (labeled: Close / Normal / Normal+ / Far) |
| Lighting condition | Dropdown | Indoor Good / Indoor Dim / Outdoor / Side Lighting |
| Background type | Dropdown | Plain White / Plain Dark / Natural/Busy / Other |
| Shirt color | Text / color picker | Free text |
| Session number | Auto-incremented | Shown for reference, editable |
| Recording date | Auto-filled | Today's date; not editable |

**Bottom of screen:**
- [Open Camera Check] → opens camera preview with landmark overlay so signer can verify they are in frame before recording starts
- [Start Recording] → only enabled after all required fields are set

---

### D. Recording Screen

**Purpose:** The main working screen. Shows the camera feed, guides the signer through each attempt, and gives real-time feedback.

**Layout:**

```
┌──────────────────────────────────┐
│  ← Back          PAUSE    STOP   │  ← top bar
│                                  │
│  ┌────────────────────────────┐  │
│  │                            │  │
│  │    LIVE CAMERA PREVIEW     │  │
│  │    + LANDMARK OVERLAY      │  │
│  │                            │  │
│  │  [● HANDS OK]  [● POSE OK] │  │  ← tracking indicators
│  │                            │  │
│  └────────────────────────────┘  │
│                                  │
│  Sign:  H E L L O               │  ← large label
│  Speed: Normal                   │
│                                  │
│  ┌────────────────────────────┐  │
│  │         3                  │  │  ← BIG countdown
│  │   Get ready to sign...     │  │
│  └────────────────────────────┘  │
│                                  │
│  Accepted  ██████░░░░  12 / 60   │  ← progress bar
│  Rejected: 3   Remaining: 48     │
│                                  │
│  ┌──────────┐  ┌──────────────┐  │
│  │  REDO    │  │  SKIP LABEL  │  │
│  │ REJECTED │  │              │  │
│  └──────────┘  └──────────────┘  │
└──────────────────────────────────┘
```

**State-dependent UI changes:**

| State | Display |
|---|---|
| IDLE | "Tap Start to begin" |
| PREPARE | "Get ready..." (camera active, overlay visible) |
| COUNTDOWN | Large "3" → "2" → "1" → "SIGN!" with color flash |
| RECORDING | Red pulsing border on camera, "Recording..." |
| ANALYZING | Spinner, "Checking quality..." |
| ACCEPTED | Green flash + checkmark, "✓ Accepted" |
| REJECTED | Red flash + X, reason text shown |
| REST | "Rest... next in 1s" with short pause animation |
| COMPLETE | Confetti-style celebration, "60/60 Done!" |

**Tracking indicator pills (top of camera):**
- `● HANDS OK` — green when ≥1 hand detected; red when no hands
- `● POSE OK` — green when shoulders visible; red when not
- `● FACE OK` — green/gray (face detection status)
- `⚠ MOVE BACK` — shown when signer appears too close
- `⚠ CENTER` — shown when body is off-center

---

### E. Review Screen

**Purpose:** Post-session summary. Shows what was recorded, what was rejected, and lets the operator make manual decisions before finalizing.

**Contents:**

```
Session Review — Hello (S01, Session 001)
─────────────────────────────────────────
Target:    60
Accepted:  57  ████████████████████░░░
Rejected:   3  ███░░░░░░░░░░░░░░░░░░░░
Attempts:  60

Rejection breakdown:
  • hand_not_visible    — 2 samples
  • tracking_failed     — 1 sample

[ Redo 3 Rejected Samples ]   [ Skip — Accept as-is ]

──────────────────────────────────────────────
Accepted Samples (57)
  S01_001_Hello_0001_ACCEPTED.json   [View] [Delete]
  S01_001_Hello_0002_ACCEPTED.json   [View] [Delete]
  ...

Rejected Samples (3)
  S01_001_Hello_0014_REJECTED_hand_not_visible.json  [View] [Override ✓] [Delete]
  ...

──────────────────────────────────────────────
Saved to:
Documents/AppHearDataset/samples/signs/Hello/

[ Open Folder ]   [ Export Session ZIP ]   [ Record Next Sign ]
```

---

### F. Dataset Browser Screen

**Purpose:** Lets the operator view the full dataset at any time — browse by sign, view individual JSON files, delete bad samples, check totals, and export.

**Sections:**

1. **Signs Overview** — list of 25 signs with accepted/rejected count per sign
2. **Background Samples** — background scenarios with counts
3. **Sample Viewer** — tap any filename to view JSON metadata and frame statistics
4. **Delete** — long-press to delete a sample (moves to trash, does not delete permanently by default)
5. **Export** — ZIP the full dataset or just one sign folder
6. **Dataset Stats** — total samples, signers, date range, class distribution

---

## 5. Recording Logic and State Machine

### States

```
IDLE
  ↓  [user taps Start]
PREPARE
  ↓  [3-second warm-up, overlay shown, tracking verified]
COUNTDOWN
  ↓  [3 → 2 → 1 → SIGN displayed at 1 second each]
RECORDING
  ↓  [30 frames collected from LandmarkFrameBuffer]
ANALYZING
  ↓  [SampleQualityAnalyzer runs checks]
  ├─→ ACCEPTED  → save to accepted/, flash green, counter+1
  └─→ REJECTED  → save to rejected/, show reason, offer redo
      ↓
REST (1.0 second pause regardless of accept/reject)
  ↓
NEXT_SAMPLE
  ├─→ accepted < target → back to COUNTDOWN
  └─→ accepted == target → COMPLETE
COMPLETE
  ↓  [show summary, save session metadata]
  └─→ ReviewActivity
```

### Countdown timing

```
PREPARE state:    camera active for 2 seconds before countdown begins
                  tracking must be GOOD (hands + pose visible) before countdown starts
                  if tracking is NOT good, countdown is held and warning is shown

COUNTDOWN:        "3" displayed for 900ms
                  "2" displayed for 900ms
                  "1" displayed for 900ms
                  "SIGN!" displayed for 300ms (color flash)

RECORDING:        starts immediately after SIGN! flash
                  captures exactly 30 frames from LandmarkFrameBuffer
                  30 frames at ~30 fps = ~1 second of capture
                  auto-stops after 30 frames regardless of time

REST:             1000ms delay after ANALYZING result is shown
                  hands-at-rest animation or "Lower hands" prompt shown
                  next countdown does not start until REST period ends
```

### Countdown hold conditions

The countdown does NOT start if any of the following are true:
- No hand detected in current frame
- No shoulder detected (pose visibility < 0.3)
- User appears too close to camera (estimated from shoulder width)
- App shows warning and waits for signer to correct position

### Pause and resume

- PAUSE button halts the state machine at the end of the current REST period
- It does not interrupt an active RECORDING or ANALYZING state
- Resume resumes from NEXT_SAMPLE
- STOP button ends the session early, saves all samples collected so far, opens ReviewActivity

### Retry logic

- After a REJECTED result, the operator sees:
  - Rejection reason text
  - `[Redo Now]` button — immediately queues another attempt for the same label (does not count the rejected sample toward the target)
  - `[Continue]` button — skips the redo for now and continues; rejected sample is flagged for later redo
- At end of session: all samples with `validated: false` are listed in ReviewActivity for batch redo

---

## 6. Landmark Overlay and Guidance System

### What is drawn

| Overlay element | Source | Color |
|---|---|---|
| Hand skeleton (21 landmarks + connections) | MediaPipe HandLandmarker | White lines, colored joints |
| Wrist position marker | HandLandmarker | Bright green dot |
| Shoulder line (left shoulder → right shoulder) | PoseLandmarker landmarks 11, 12 | Blue line |
| Elbow and wrist dots | PoseLandmarker landmarks 13–16 | Blue dots |
| Nose position dot | PoseLandmarker landmark 0 | Yellow dot |
| Face detection ring | FaceLandmarker presence | Green ring around detected face area |
| Body center reference line | Computed from shoulder midpoint | Faint white vertical guide line |

### Tracking status indicators

These are shown as pill badges at the top of the camera preview.

| Indicator | Condition | Color |
|---|---|---|
| HANDS OK | ≥1 hand detected with ≥50% landmark visibility | Green |
| HANDS LOW | hand detected but many landmarks low visibility | Yellow |
| NO HANDS | no hand detected | Red |
| POSE OK | both shoulders visible > 0.5 | Green |
| POSE LOW | only one shoulder visible or visibility < 0.5 | Yellow |
| NO POSE | neither shoulder detected | Red |
| FACE DETECTED | FaceLandmarker returns a result | Green |
| FACE ABSENT | no face result | Gray |

### Positional guidance messages

These appear as a text banner below the camera preview and auto-dismiss when corrected.

| Condition | Message |
|---|---|
| Shoulders not visible | "Move camera down or step back" |
| Hands at screen edge | "Move hands toward center" |
| Estimated signer too close | "Move back — aim for 60-80 cm" |
| Body off-center | "Center your body in frame" |
| Poor lighting (avg frame brightness < threshold) | "Find better lighting" |
| Hand missing mid-sign (during RECORDING state) | "Keep hands in frame" |
| Two-handed sign but only 1 hand detected | "Both hands must be visible" |

### Visual recording indicator

During RECORDING state:
- A red pulsing border appears around the camera preview
- Frame progress dots shown: `● ● ● ○ ○ ○` (filled as each frame is captured)
- After ANALYZING: border flashes green (ACCEPTED) or red (REJECTED) once

---

## 7. Automatic Sample Quality Check

`SampleQualityAnalyzer` runs immediately after the 30-frame buffer is collected. It applies the checks below in order. The first failing check sets the rejection reason. Multiple warnings can be collected even if the sample is accepted.

### Hard reject rules (any one = REJECTED)

| Check | Rule | Rejection reason code |
|---|---|---|
| Frame count | Must equal exactly 30 | `wrong_frame_count` |
| Hand presence | At least 70% of frames (≥21 frames) must have at least one hand detected (non-zero hand slot) | `hand_not_visible` |
| Pose presence | At least 80% of frames (≥24 frames) must have at least one shoulder with visibility > 0.3 | `pose_not_visible` |
| Complete zero frame | No frame may be entirely zero across all 258 values | `complete_tracking_failure` |
| Tracking jump | Hand position must not jump more than 0.3 normalized units between any two consecutive frames | `tracking_jump` |
| Hand boundary | Hand wrist landmark must not be in the outer 5% of frame boundary in more than 3 consecutive frames | `hand_out_of_frame` |
| Label missing | `label` field must not be null or empty | `missing_label` |
| Signer ID missing | `signer_id` must not be null | `missing_signer_id` |

### Soft warning rules (sample is ACCEPTED but flagged)

| Check | Rule | Warning code |
|---|---|---|
| Low hand visibility | 71-80% of frames have hand detected (passes but barely) | `low_hand_visibility` |
| Single hand for two-handed sign | Sign is flagged as two-handed in labels config but only 1 hand detected | `one_hand_for_two_handed_sign` |
| Jitter | High variance in landmark positions across consecutive frames | `high_tracking_jitter` |
| Short motion | Wrist displacement across 30 frames is below a low threshold (possible static pose, no motion) | `low_motion_detected` |
| Early start | Wrist velocity in frames 1-5 is high (signer may have started before SIGN! prompt) | `possible_early_start` |
| Low face visibility | FaceLandmarker returned no result in more than 50% of frames | `face_not_detected` |

### Quality score

Each sample receives a float `quality_score` from 0.0 to 1.0:

```
quality_score = (
    (hand_present_frames / 30) * 0.40 +
    (pose_present_frames / 30) * 0.30 +
    (1.0 - normalized_jitter) * 0.20 +
    (face_present_frames / 30) * 0.10
)
```

This score is saved in the JSON metadata but is not used for accept/reject decisions — only the hard rules above determine acceptance.

### Rejection reason display

Each rejection reason is mapped to a human-readable message shown on screen:

| Code | Display message |
|---|---|
| `wrong_frame_count` | "Rejected: wrong number of frames captured" |
| `hand_not_visible` | "Rejected: hand not visible in enough frames" |
| `pose_not_visible` | "Rejected: shoulders not detected — step back or adjust camera" |
| `complete_tracking_failure` | "Rejected: MediaPipe tracking completely failed" |
| `tracking_jump` | "Rejected: sudden hand position jump detected" |
| `hand_out_of_frame` | "Rejected: hand moved out of camera frame" |
| `missing_label` | "Rejected: sign label is missing — check session setup" |
| `missing_signer_id` | "Rejected: signer profile is not set" |

---

## 8. Manual Review Option

Automatic quality checks verify **technical recording quality only** — they cannot determine whether the signer performed the correct sign. A human reviewer must confirm semantic correctness.

### How manual review works

On the Review Screen, each sample shows:

```
S01_001_Hello_0014_REJECTED_hand_not_visible.json
Frames: 30 | Hand frames: 18/30 (60%) | Quality: 0.54
Reason: hand_not_visible

[ ✓ Override Accept ]   [ ✗ Confirm Reject ]   [ 🔁 Redo ]
```

When a reviewer manually overrides:
- `validated` is set to `true`
- `rejected_reason` is set to `null`
- `manual_override` is set to `true`
- The file is moved from `rejected/` to `accepted/`

When a reviewer confirms a rejection:
- `validated` remains `false`
- `rejected_reason` stays as-is
- Sample remains in `rejected/`

### JSON fields for review state

```json
"validated":        true,
"rejected_reason":  null,
"manual_override":  false,
"reviewer_notes":   null
```

For a manually overridden sample:
```json
"validated":        true,
"rejected_reason":  null,
"manual_override":  true,
"reviewer_notes":   "Signer's sleeve partially covered wrist but sign was correct"
```

For a rejected sample:
```json
"validated":        false,
"rejected_reason":  "hand_not_visible",
"manual_override":  false,
"reviewer_notes":   null
```

---

## 9. Data Format — JSON Sample Schema

Every recorded sample is saved as a single JSON file. The schema matches the Phase 2 dataset plan exactly so that Python training scripts can load it without modification.

### Sign sample (full schema)

```json
{
  "sample_id":         "a3f2c1d4-7b8e-4f01-9a2b-3c4d5e6f7a8b",
  "label":             "Hello",
  "label_index":       0,
  "sign_language":     "FSL",
  "signer_id":         "S01",
  "session_id":        "S01_Session001",
  "recording_date":    "2026-05-25",
  "repetition_index":  3,
  "camera_direction":  "front",
  "speed":             "normal",
  "posture":           "seated",
  "distance_cm":       70,
  "lighting":          "indoor_good",
  "background":        "plain_white",
  "shirt_color":       "dark_blue",
  "dominant_hand":     "right",
  "validated":         true,
  "rejected_reason":   null,
  "manual_override":   false,
  "reviewer_notes":    null,
  "frame_count":       30,
  "feature_size":      258,
  "quality_score":     0.91,
  "quality_warnings":  [],
  "mediapipe_version": "0.10.14",
  "app_version":       "asl_recorder_v1",
  "frames": [
    [0.012, -0.341, 0.054, 0.98, 0.002, -0.310, 0.071, 0.95, "...258 floats total..."],
    "... 29 more frame arrays ..."
  ]
}
```

### Feature vector layout (258 floats per frame)

```
Indices   0 – 131  : Pose landmarks (33 × 4: x, y, z, visibility) — nose-normalized
Indices 132 – 194  : Signer's LEFT hand (21 × 3: x, y, z) — wrist-normalized
Indices 195 – 257  : Signer's RIGHT hand (21 × 3: x, y, z) — wrist-normalized

Front-camera handedness correction applied:
  MediaPipe "Right" label → assigned to LEFT hand slot (signer's actual left)
  MediaPipe "Left"  label → assigned to RIGHT hand slot (signer's actual right)

If a hand is not detected: its 63 float slots are filled with 0.0
```

### Background sample (reduced schema)

```json
{
  "sample_id":      "b8e1a2c3-...",
  "label":          "Background",
  "label_index":    25,
  "sign_language":  "FSL",
  "signer_id":      "S02",
  "session_id":     "S02_Session001",
  "recording_date": "2026-05-25",
  "bg_scenario":    "hands_in_lap",
  "camera_direction": "front",
  "posture":        "seated",
  "validated":      true,
  "rejected_reason": null,
  "manual_override": false,
  "frame_count":    30,
  "feature_size":   258,
  "quality_score":  0.85,
  "quality_warnings": [],
  "mediapipe_version": "0.10.14",
  "app_version":    "asl_recorder_v1",
  "frames":         [ "... 30 arrays of 258 floats ..." ]
}
```

---

## 10. Folder Structure

The app saves all data under a single root folder. The default location is app-specific external storage. If the user grants `MANAGE_EXTERNAL_STORAGE`, the app offers to save to `Documents/AppHearDataset/`.

```
AppHearDataset/
│
├── labels.json                          ← 26-class label list (from Phase 2 plan)
│
├── metadata/
│   ├── signers.json                     ← Signer profiles and split assignments
│   ├── sessions.json                    ← All recorded sessions with metadata
│   ├── dataset_summary.json             ← Total counts per class, dates, version
│   └── quality_log.json                 ← All rejection events with reasons and timestamps
│
├── samples/
│   │
│   ├── signs/
│   │   ├── Hello/
│   │   │   ├── accepted/                ← validated: true samples
│   │   │   │   ├── S01_001_Hello_0001_ACCEPTED.json
│   │   │   │   └── ...
│   │   │   ├── rejected/                ← validated: false samples (kept for audit)
│   │   │   │   ├── S01_001_Hello_0014_REJECTED_hand_not_visible.json
│   │   │   │   └── ...
│   │   │   └── redo/                    ← flagged for redo (not yet re-recorded)
│   │   │       └── ...
│   │   │
│   │   ├── Thank_You/
│   │   │   ├── accepted/
│   │   │   ├── rejected/
│   │   │   └── redo/
│   │   │
│   │   ├── You/
│   │   ├── My/
│   │   ├── Name/
│   │   ├── Nice/
│   │   ├── Meet/
│   │   ├── Goodbye/
│   │   ├── Yes/
│   │   ├── No/
│   │   ├── Please/
│   │   ├── Sorry/
│   │   ├── Good/
│   │   ├── I/
│   │   ├── He_She/
│   │   ├── We/
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
│       ├── accepted/
│       │   ├── S01_bg_hands_down_0001_ACCEPTED.json
│       │   └── ...
│       ├── rejected/
│       └── redo/
│
└── exports/                             ← generated files, not recorded manually
    ├── dataset_summary.csv
    ├── quality_report.csv
    └── AppHearDataset_export_2026-05-25.zip
```

### Folder purpose reference

| Folder | Purpose |
|---|---|
| `metadata/` | Session and signer metadata. Updated after every session. |
| `samples/signs/<Label>/accepted/` | Validated samples ready for training. These are what the Python pipeline loads. |
| `samples/signs/<Label>/rejected/` | Failed samples kept for audit. Never loaded by training pipeline. |
| `samples/signs/<Label>/redo/` | Samples flagged by reviewer for re-recording. App uses these to queue redo sessions. |
| `samples/background/` | All background/rest class samples, same subfolder structure. |
| `exports/` | ZIP archives and CSV summaries generated on demand. Never touched by recording. |

---

## 11. File Naming Convention

### Signs

```
{SIGNER_ID}_{SESSION_NUMBER}_{LABEL}_{REP_INDEX:04d}_{STATUS}.json

Examples:
  S01_001_Hello_0001_ACCEPTED.json
  S01_001_Hello_0014_REJECTED_hand_not_visible.json
  S03_002_Thank_You_0007_ACCEPTED.json
  S05_003_He_She_0031_REJECTED_tracking_jump.json
```

### Background

```
{SIGNER_ID}_bg_{SCENARIO}_{REP_INDEX:04d}_{STATUS}.json

Examples:
  S01_bg_hands_down_0001_ACCEPTED.json
  S02_bg_transition_0007_ACCEPTED.json
  S03_bg_talking_0003_REJECTED_pose_not_visible.json
```

### Rules

- `SIGNER_ID`: always uppercase, format `S##` (S01, S02, ... S99)
- `SESSION_NUMBER`: zero-padded 3 digits (001, 002, ...)
- `LABEL`: the exact label string with spaces replaced by underscores (`Thank_You`, `He_She`)
- `REP_INDEX`: zero-padded 4 digits, resets to 0001 for each new session
- `STATUS`: one of `ACCEPTED` or `REJECTED_{reason_code}`
- `SCENARIO` for background: one of `hands_down`, `hands_in_lap`, `hands_on_desk`, `talking`, `transition`, `unknown_sign`, `hand_near_face`, `one_hand`, `empty_frame`, `random_movement`

---

## 12. Counter and Progress System

The progress counter tracks accepted samples against the target. Only accepted samples count toward the target.

### Display

```
Sign: Hello
Target: 60 accepted samples

[ ████████████░░░░░░░░ ]  22 / 60 accepted
Remaining:  38
Rejected:    4  (4 samples need redo)
Attempts:   26  (22 accepted + 4 rejected)
```

### Rules

- `Accepted` increments only when `SampleQualityAnalyzer` passes all hard rules
- `Rejected` increments when any hard rule fails
- `Attempts` = Accepted + Rejected (total attempts made)
- `Remaining` = Target − Accepted
- A rejected sample does NOT count toward the target
- If the user manually overrides a rejection to accepted in ReviewActivity, Accepted increments and Rejected decrements
- The session is COMPLETE when Accepted == Target

### Redo queue

When the session ends with rejected samples, the app builds a redo queue:

```
Redo queue for Hello:
  - S01_001_Hello_0014_REJECTED_hand_not_visible.json → needs 1 replacement
  - S01_001_Hello_0022_REJECTED_tracking_jump.json   → needs 1 replacement
  Total: 2 additional accepted samples needed to reach target 60
```

The operator can tap [Redo Rejected Samples] to re-enter recording mode with the redo count as the new target.

---

## 13. Background / Rest Recording Mode

The Background class is mandatory and must be collected with the same care as sign samples.

### Background recording mode

When the user selects "Background" as the sign label in Session Setup, the screen enters Background Mode. The session setup shows an extra field: **Scenario**.

### Background scenarios

| Scenario key | Description | Target (Version 1) |
|---|---|---|
| `hands_down` | Person standing, arms naturally at sides | 150 |
| `hands_in_lap` | Person seated, hands resting on legs | 150 |
| `hands_on_desk` | Person at table, hands flat or loose | 100 |
| `talking` | Natural mouth/hand gestures, no sign | 150 |
| `transition` | Hands moving between general positions | 200 |
| `unknown_sign` | Signing something NOT in the vocabulary | 200 |
| `hand_near_face` | Touching face, adjusting hair, thinking | 100 |
| `one_hand` | One-handed context, other hand out of frame | 100 |
| `empty_frame` | No person visible or only lower body | 100 |
| `random_movement` | General hand motion, no sign pattern | 150 |

### Differences from sign recording mode

- No "SIGN!" countdown prompt — replaced with a casual "Recording..." indicator
- No requirement for both hands to be visible (background includes one-hand and empty-frame scenarios)
- The `pose_not_visible` hard reject is relaxed for `empty_frame` scenario
- Samples are saved to `samples/background/accepted/` or `samples/background/rejected/`
- `bg_scenario` field is written to the JSON instead of `speed` and `posture`

### Guidance for background recording

The operator instruction screen (shown before background recording begins) says:

```
Background Recording — {SCENARIO}

Instructions:
- Do NOT use the countdown protocol
- Act naturally for this scenario
- The app will automatically capture 30 frames
- Aim for casual, natural movement — not rigid or posed
- Mix in transitions between known signs slowly
- You may sign 3-4 known signs slowly and capture the transitions
```

---

## 14. Android Technical Architecture

### Package structure

```
com.example.aslrecorder
  ├── activities/
  │   ├── MainActivity.java
  │   ├── SignerProfileActivity.java
  │   ├── SessionSetupActivity.java
  │   ├── RecordingActivity.java
  │   ├── ReviewActivity.java
  │   └── DatasetBrowserActivity.java
  │
  ├── mediapipe/
  │   └── MediaPipeRecorderHelper.java
  │
  ├── ml/
  │   ├── LandmarkFrameBuffer.java
  │   └── SampleQualityAnalyzer.java
  │
  ├── recording/
  │   └── RecordingStateMachine.java
  │
  ├── data/
  │   ├── DatasetFileManager.java
  │   ├── MetadataManager.java
  │   ├── LabelsRepository.java
  │   └── DatasetExporter.java
  │
  └── ui/
      └── LandmarkOverlayView.java
```

### Class responsibilities

| Class | Package | Purpose |
|---|---|---|
| `MainActivity` | activities | Home screen. Loads dataset summary. Navigates to all other screens. |
| `SignerProfileActivity` | activities | Create, select, and edit signer profiles. Reads/writes `signers.json`. |
| `SessionSetupActivity` | activities | Configure session metadata. Validates all fields. Navigates to RecordingActivity. |
| `RecordingActivity` | activities | Main recording screen. Owns camera, MediaPipe, state machine, countdown UI, progress counter. Delegates logic to helper classes. |
| `ReviewActivity` | activities | Post-session review. Loads session sample list. Allows manual override. Triggers redo queue. |
| `DatasetBrowserActivity` | activities | Browses full dataset folder tree. Shows per-sign counts. Opens individual JSON files. |
| `MediaPipeRecorderHelper` | mediapipe | Wraps HandLandmarker, PoseLandmarker, FaceLandmarker. Converts `ImageProxy` → `MPImage`. Returns `ResultBundle` to `RecordingActivity`. Applies front-camera handedness correction. |
| `LandmarkOverlayView` | ui | Custom `View`. Draws hand skeleton, shoulder line, nose dot, face ring on camera preview. Draws tracking status indicators. Positioned as overlay over `PreviewView`. |
| `LandmarkFrameBuffer` | ml | Stores most recent N landmark feature vectors. Provides `getSequence()` returning `float[30][258]`. Implements zero-padding for frames before the first detection. |
| `SampleQualityAnalyzer` | ml | Applies all hard reject and soft warning rules to a `float[30][258]` sequence. Returns `QualityResult` with accept/reject decision, reason code, quality score, and warnings list. |
| `RecordingStateMachine` | recording | Implements IDLE → PREPARE → COUNTDOWN → RECORDING → ANALYZING → ACCEPTED/REJECTED → REST → NEXT_SAMPLE → COMPLETE. Notifies `RecordingActivity` via listener interface on state transitions. |
| `DatasetFileManager` | data | Creates folder structure, writes JSON files, moves files between accepted/rejected/redo, deletes files. All I/O runs on a background thread. |
| `MetadataManager` | data | Reads and writes `signers.json`, `sessions.json`, `dataset_summary.json`, `quality_log.json`. Maintains sample counts per sign per signer. |
| `LabelsRepository` | data | Loads `labels.json` from assets. Provides label → index and index → label lookups. Provides the list of two-handed signs for quality checking. |
| `DatasetExporter` | data | Generates `dataset_summary.csv`, `quality_report.csv`, and ZIP archives. Runs on background thread. |

### Key interfaces

```java
// RecordingActivity implements these to receive state machine and MediaPipe events
interface RecordingStateListener {
    void onStateChanged(RecordingState newState);
    void onFrameCaptured(int frameIndex, int totalFrames);
    void onCountdownTick(int secondsRemaining);
    void onSampleResult(QualityResult result);
    void onSessionComplete(SessionSummary summary);
}

interface LandmarkResultListener {
    void onLandmarkResult(ResultBundle result);
}
```

---

## 15. MediaPipe and CameraX Integration

### CameraX setup

```java
// In RecordingActivity

// Preview use case — shows live feed on PreviewView
Preview preview = new Preview.Builder().build();
preview.setSurfaceProvider(previewView.getSurfaceProvider());

// Analysis use case — sends frames to MediaPipe
ImageAnalysis imageAnalysis = new ImageAnalysis.Builder()
    .setTargetResolution(new Size(640, 480))
    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
    .build();
imageAnalysis.setAnalyzer(cameraExecutor, imageProxy -> {
    if (!frameInFlight.getAndSet(true)) {
        mediaRecorderHelper.processFrame(imageProxy);
    } else {
        imageProxy.close();
    }
});

// Bind to front camera
CameraSelector cameraSelector = CameraSelector.DEFAULT_FRONT_CAMERA;
cameraProvider.bindToLifecycle(this, cameraSelector, preview, imageAnalysis);
```

### MediaPipeRecorderHelper

```java
// Runs HandLandmarker, PoseLandmarker, FaceLandmarker per frame
// Returns ResultBundle to listener
// Applies handedness correction for front camera

public void processFrame(ImageProxy imageProxy) {
    Bitmap bitmap = imageProxyToBitmap(imageProxy);
    MPImage mpImage = new BitmapImageBuilder(bitmap).build();

    HandLandmarkerResult handResult = handLandmarker.detect(mpImage);
    PoseLandmarkerResult poseResult = poseLandmarker.detect(mpImage);
    FaceLandmarkerResult faceResult = faceLandmarker.detect(mpImage);

    imageProxy.close();
    frameInFlight.set(false);

    listener.onLandmarkResult(new ResultBundle(handResult, poseResult, faceResult));
}
```

### KeypointExtractor (same as AppHear main app)

```java
// Produces float[258] per frame
// Pose: 33 × 4 (x, y, z, visibility), nose-normalized
// Left hand: 21 × 3 (x, y, z), wrist-normalized
// Right hand: 21 × 3 (x, y, z), wrist-normalized
// Front-camera correction: MediaPipe "Right" → signer's Left slot; MediaPipe "Left" → signer's Right slot
// Missing hand: fill 63 slots with 0.0f

float[] extract(PoseLandmarkerResult pose, HandLandmarkerResult hand, boolean isFrontCamera)
```

### LandmarkFrameBuffer

```java
// Stores up to 30 feature vectors
// Zero-pads at start (not repeat-oldest)
// getSequence() returns float[30][258]
// Records state: only adds frames when RecordingStateMachine is in RECORDING state

public void addFrame(float[] features) { ... }
public float[][] getSequence() { ... }   // always returns [30][258]
public void reset() { ... }
public int getFrameCount() { ... }
public boolean isFull() { return getFrameCount() >= 30; }
```

### Front-camera handedness correction

MediaPipe's left/right label is mirrored relative to the signer's actual hand when using the front camera. Correction must be applied in `KeypointExtractor`:

```java
if (isFrontCamera) {
    // MediaPipe says "Left" → it's actually the signer's RIGHT hand
    // MediaPipe says "Right" → it's actually the signer's LEFT hand
    // Swap slot assignment accordingly
    if (handedness.equals("Left")) {
        fillHandSlot(features, RIGHT_HAND_OFFSET, handLandmarks);
    } else {
        fillHandSlot(features, LEFT_HAND_OFFSET, handLandmarks);
    }
} else {
    // Back camera: no swap needed
    if (handedness.equals("Left")) {
        fillHandSlot(features, LEFT_HAND_OFFSET, handLandmarks);
    } else {
        fillHandSlot(features, RIGHT_HAND_OFFSET, handLandmarks);
    }
}
```

---

## 16. Storage and Permissions

### Storage strategy (Android 10+)

| Option | API | When to use |
|---|---|---|
| App-specific external storage | `getExternalFilesDir(null)` | Default. No permission needed on Android 10+. Path: `Android/data/com.example.aslrecorder/files/AppHearDataset/` |
| Shared Documents folder | `MediaStore` + `ContentResolver` or `Storage Access Framework` | If user wants data accessible outside the app. Requires user to grant folder access via directory picker. |

**Default (MVP):** Use `getExternalFilesDir(null)`. This requires no storage permission on Android 10+ and the data is accessible when the phone is connected to a computer. Show the path to the user.

### Permissions required

```xml
<!-- AndroidManifest.xml -->

<!-- Camera — required for recording -->
<uses-permission android:name="android.permission.CAMERA" />

<!-- Storage — only needed for Android 9 and below -->
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"
    android:maxSdkVersion="28" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
    android:maxSdkVersion="28" />
```

### Showing save path to user

After every accepted sample is saved, the footer of the Recording Screen shows:

```
Saved to: Android/data/com.example.aslrecorder/files/AppHearDataset/samples/signs/Hello/accepted/
```

Tapping this path opens Android's Files app at that directory (using `Intent.ACTION_VIEW` with the directory URI via `FileProvider`).

### ZIP export

`DatasetExporter.exportToZip()` compresses the entire `AppHearDataset/` folder into:

```
AppHearDataset/exports/AppHearDataset_export_2026-05-25.zip
```

This ZIP can be shared to a computer via USB, Google Drive, or any share intent. The ZIP contains the exact same folder structure as the original dataset, ready to be placed on a machine running the Python training pipeline.

---

## 17. UI/UX Requirements

The visual design follows the clean card-based style shown in the reference image: white background, rounded cards, strong typography, minimal chrome, dark primary action buttons.

### Typography

| Element | Style |
|---|---|
| App title | Bold, 20sp |
| Sign label (Recording screen) | ExtraBold, 36sp, letter-spaced |
| Countdown number | ExtraBold, 96sp, centered |
| Progress fraction (22/60) | Bold, 28sp |
| Status message | Regular, 14sp, muted |
| Rejection reason | Medium, 14sp, red |

### Color system

| Color | Hex | Use |
|---|---|---|
| Background | #F5F5F5 | App background |
| Surface | #FFFFFF | Cards, panels |
| Primary | #1A1A1A | Primary buttons, countdown |
| Accepted green | #22C55E | Accept flash, HANDS OK badge |
| Rejected red | #EF4444 | Reject flash, NO HANDS badge |
| Warning yellow | #F59E0B | Low visibility badges |
| Progress fill | #1A1A1A | Progress bar filled segment |
| Progress track | #E5E7EB | Progress bar empty segment |

### Animations

| Event | Animation |
|---|---|
| ACCEPTED | Card border flashes green once (200ms) + checkmark icon appears for 1s |
| REJECTED | Card border flashes red once (200ms) + X icon + reason text slides in |
| Countdown 3→2→1 | Number scales in with a subtle bounce (scale 0.8 → 1.1 → 1.0) |
| SIGN! | Background flashes accent color for 300ms |
| Progress bar | Smooth animated fill on each accept |
| Session complete | 60/60 card slides up with success icon |

### Key UI requirements

- Countdown must be legible from 1 meter away — minimum 72sp
- Sign label must be visible at a glance without reading — minimum 32sp, high contrast
- Tracking indicators must be visible while the signer is looking at the camera — keep them small and in a fixed corner
- Accept/reject feedback must be instant — no delay between ANALYZING result and visual feedback
- The save path must be tappable and open the correct folder
- The redo button must be prominent after a rejection (do not hide it)

---

## 18. Code-Level Guidance — Pseudocode

### Recording state machine

```java
// RecordingStateMachine.java

public enum RecordingState {
    IDLE, PREPARE, COUNTDOWN, RECORDING, ANALYZING, ACCEPTED, REJECTED, REST, NEXT_SAMPLE, COMPLETE
}

public class RecordingStateMachine {

    private RecordingState currentState = RecordingState.IDLE;
    private int acceptedCount = 0;
    private final int targetCount;
    private final RecordingStateListener listener;

    public void start() {
        transitionTo(RecordingState.PREPARE);
    }

    public void onTrackingReady() {
        if (currentState == RecordingState.PREPARE) {
            transitionTo(RecordingState.COUNTDOWN);
        }
    }

    public void onCountdownComplete() {
        if (currentState == RecordingState.COUNTDOWN) {
            transitionTo(RecordingState.RECORDING);
        }
    }

    public void onFrameBufferFull() {
        if (currentState == RecordingState.RECORDING) {
            transitionTo(RecordingState.ANALYZING);
        }
    }

    public void onQualityResult(QualityResult result) {
        if (currentState == RecordingState.ANALYZING) {
            if (result.isAccepted()) {
                acceptedCount++;
                transitionTo(RecordingState.ACCEPTED);
            } else {
                transitionTo(RecordingState.REJECTED);
            }
            listener.onSampleResult(result);
            scheduleTransition(RecordingState.REST, 1500);
        }
    }

    private void scheduleTransition(RecordingState next, long delayMs) {
        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            transitionTo(next);
            if (next == RecordingState.REST) {
                scheduleTransition(RecordingState.NEXT_SAMPLE, 1000);
            }
            if (next == RecordingState.NEXT_SAMPLE) {
                if (acceptedCount >= targetCount) {
                    transitionTo(RecordingState.COMPLETE);
                } else {
                    transitionTo(RecordingState.COUNTDOWN);
                }
            }
        }, delayMs);
    }

    private void transitionTo(RecordingState newState) {
        currentState = newState;
        listener.onStateChanged(newState);
    }
}
```

### Countdown timer

```java
// In RecordingActivity, triggered when state enters COUNTDOWN

private void startCountdown() {
    int[] ticks = {3, 2, 1};
    int[] delays = {0, 900, 1800};

    for (int i = 0; i < ticks.length; i++) {
        final int tick = ticks[i];
        handler.postDelayed(() -> {
            countdownText.setText(String.valueOf(tick));
            countdownText.animate().scaleX(1.1f).scaleY(1.1f).setDuration(100)
                .withEndAction(() -> countdownText.animate().scaleX(1f).scaleY(1f).setDuration(100).start())
                .start();
            listener.onCountdownTick(tick);
        }, delays[i]);
    }

    handler.postDelayed(() -> {
        countdownText.setText("SIGN!");
        countdownText.setTextColor(Color.parseColor("#22C55E"));
        stateMachine.onCountdownComplete();
    }, 2700);
}
```

### Frame buffer collection

```java
// LandmarkFrameBuffer.java

public class LandmarkFrameBuffer {
    private static final int SEQUENCE_LENGTH = 30;
    private static final int FEATURE_SIZE = 258;
    private final float[][] buffer = new float[SEQUENCE_LENGTH][FEATURE_SIZE];
    private int frameCount = 0;
    private boolean collecting = false;

    public void startCollecting() {
        Arrays.fill(buffer, null);
        for (int i = 0; i < SEQUENCE_LENGTH; i++) {
            buffer[i] = new float[FEATURE_SIZE]; // zeros by default
        }
        frameCount = 0;
        collecting = true;
    }

    public boolean addFrame(float[] features) {
        if (!collecting || frameCount >= SEQUENCE_LENGTH) return false;
        buffer[frameCount] = Arrays.copyOf(features, FEATURE_SIZE);
        frameCount++;
        return isFull();
    }

    public float[][] getSequence() {
        return buffer; // already zero-padded at start for early frames
    }

    public boolean isFull() { return frameCount >= SEQUENCE_LENGTH; }
    public int getFrameCount() { return frameCount; }
    public void stopCollecting() { collecting = false; }
}
```

### Quality analyzer

```java
// SampleQualityAnalyzer.java

public QualityResult analyze(float[][] frames, String label, String signerId) {
    List<String> warnings = new ArrayList<>();

    // Hard reject: frame count
    if (frames.length != 30) {
        return QualityResult.rejected("wrong_frame_count", frames.length, 0f, warnings);
    }

    // Hard reject: missing metadata
    if (label == null || label.isEmpty()) {
        return QualityResult.rejected("missing_label", frames.length, 0f, warnings);
    }
    if (signerId == null || signerId.isEmpty()) {
        return QualityResult.rejected("missing_signer_id", frames.length, 0f, warnings);
    }

    // Count frames with hands detected
    int handFrames = 0;
    int poseFrames = 0;
    int faceFrames = 0;
    boolean hasTotalZeroFrame = false;

    for (float[] frame : frames) {
        if (hasHandData(frame)) handFrames++;
        if (hasPoseData(frame)) poseFrames++;
        if (hasFaceData(frame)) faceFrames++;
        if (isTotallyZero(frame)) hasTotalZeroFrame = true;
    }

    // Hard reject: total zero frame
    if (hasTotalZeroFrame) {
        return QualityResult.rejected("complete_tracking_failure", frames.length, 0f, warnings);
    }

    // Hard reject: hand visibility
    if (handFrames < (int)(frames.length * 0.70)) {
        return QualityResult.rejected("hand_not_visible", frames.length, 0f, warnings);
    }

    // Hard reject: pose visibility
    if (poseFrames < (int)(frames.length * 0.80)) {
        return QualityResult.rejected("pose_not_visible", frames.length, 0f, warnings);
    }

    // Hard reject: tracking jump
    if (hasTrackingJump(frames, 0.3f)) {
        return QualityResult.rejected("tracking_jump", frames.length, 0f, warnings);
    }

    // Soft warnings
    if (handFrames < (int)(frames.length * 0.80)) warnings.add("low_hand_visibility");
    if (faceFrames < frames.length / 2) warnings.add("face_not_detected");
    if (hasLowMotion(frames)) warnings.add("low_motion_detected");

    // Quality score
    float qualityScore = computeQualityScore(handFrames, poseFrames, faceFrames, frames.length);

    return QualityResult.accepted(frames.length, qualityScore, warnings);
}
```

### JSON sample saving

```java
// DatasetFileManager.java

public void saveSample(SampleData sample, File datasetRoot) {
    String subdir = sample.isBackground()
        ? "samples/background"
        : "samples/signs/" + sample.label.replace(" ", "_");
    String status = sample.validated ? "accepted" : "rejected";
    String folder = subdir + "/" + status + "/";

    File dir = new File(datasetRoot, folder);
    dir.mkdirs();

    String filename = buildFilename(sample);
    File file = new File(dir, filename);

    try (FileWriter writer = new FileWriter(file)) {
        JSONObject json = sample.toJson();
        writer.write(json.toString(2));
    } catch (IOException | JSONException e) {
        Log.e("DatasetFileManager", "Failed to save sample: " + e.getMessage());
    }
}

private String buildFilename(SampleData sample) {
    String status = sample.validated
        ? "ACCEPTED"
        : "REJECTED_" + sample.rejectedReason;
    return String.format("%s_%03d_%s_%04d_%s.json",
        sample.signerId,
        sample.sessionNumber,
        sample.label.replace(" ", "_"),
        sample.repetitionIndex,
        status);
}
```

### Progress counter update

```java
// In RecordingActivity

private int acceptedCount = 0;
private int rejectedCount = 0;
private final int targetCount = 60; // from session setup

private void updateProgress() {
    progressBar.setProgress((int)((acceptedCount / (float)targetCount) * 100));
    acceptedCountText.setText(acceptedCount + " / " + targetCount + " accepted");
    remainingText.setText("Remaining: " + (targetCount - acceptedCount));
    rejectedText.setText("Rejected: " + rejectedCount);
}

private void onSampleAccepted() {
    acceptedCount++;
    updateProgress();
    flashGreen();
}

private void onSampleRejected(String reason) {
    rejectedCount++;
    updateProgress();
    flashRed();
    showRejectionReason(reason);
}
```

### Folder creation

```java
// DatasetFileManager.java — called once on app first launch or new sign

public void ensureFolderStructure(File datasetRoot, List<String> signLabels) {
    String[] subdirs = {"accepted", "rejected", "redo"};

    for (String label : signLabels) {
        for (String sub : subdirs) {
            File dir = new File(datasetRoot,
                "samples/signs/" + label.replace(" ", "_") + "/" + sub);
            dir.mkdirs();
        }
    }

    for (String sub : subdirs) {
        new File(datasetRoot, "samples/background/" + sub).mkdirs();
    }

    new File(datasetRoot, "metadata").mkdirs();
    new File(datasetRoot, "exports").mkdirs();
}
```

---

## 19. Minimum Viable Version (MVP)

The MVP must be usable for a real recording session. It does not need advanced features. Every item below is required for Version 0 data collection.

### MVP feature checklist

| Feature | Required for MVP | Notes |
|---|---|---|
| CameraX preview (front camera) | Yes | |
| MediaPipe HandLandmarker | Yes | |
| MediaPipe PoseLandmarker | Yes | |
| MediaPipe FaceLandmarker | Optional in MVP | Run it but can skip writing face data to JSON in v1 |
| LandmarkOverlayView (hand + shoulder) | Yes | Face overlay optional in MVP |
| Tracking status indicators (HANDS OK / POSE OK) | Yes | |
| Signer profile input (ID + dominant hand) | Yes | Minimal form, no validation screen needed |
| Session setup (label + target reps + speed + posture) | Yes | |
| RecordingStateMachine (all states) | Yes | |
| Countdown display (3-2-1-SIGN) | Yes | |
| 30-frame buffer collection | Yes | |
| Zero-padding for early frames | Yes | |
| Front-camera handedness correction | Yes | |
| KeypointExtractor (258 floats) | Yes | Same as AppHear main app |
| SampleQualityAnalyzer (hard reject rules only) | Yes | Soft warnings optional in MVP |
| Progress counter (accepted/rejected/remaining) | Yes | |
| Accept/reject feedback (flash + text) | Yes | |
| JSON saving (full schema) | Yes | |
| Folder structure (accepted/rejected subfolders) | Yes | |
| File naming convention | Yes | |
| Save path shown to user | Yes | |
| ReviewActivity (list of accepted/rejected) | Yes | |
| Manual override on rejected samples | Yes | |
| Background class recording mode | Yes | Must have in MVP |
| Dataset Browser (basic) | No — V2 | |
| ZIP export | No — V2 | |
| Reference sign video | No — V2 | |
| Multi-signer session management | No — V2, use separate phone runs |

### MVP dependencies (app/build.gradle.kts)

```kotlin
// CameraX
implementation("androidx.camera:camera-core:1.3.4")
implementation("androidx.camera:camera-camera2:1.3.4")
implementation("androidx.camera:camera-lifecycle:1.3.4")
implementation("androidx.camera:camera-view:1.3.4")

// MediaPipe Tasks Vision
implementation("com.google.mediapipe:tasks-vision:0.10.14")

// JSON (built-in org.json — no extra dependency)

// UUID generation (built-in java.util.UUID — no extra dependency)

// Material Design
implementation("com.google.android.material:material:1.12.0")
```

### MVP screen count: 5

1. `MainActivity` — home with start session button
2. `SessionSetupActivity` — sign label, signer ID, target reps, speed, posture
3. `RecordingActivity` — camera + overlay + countdown + counter
4. `ReviewActivity` — accepted/rejected list with override buttons
5. (Optional for MVP) `DatasetBrowserActivity` — simple file list

---

## 20. Advanced Features for Later

These features are explicitly excluded from the MVP. Add them only after the MVP is validated with real recording sessions.

| Feature | Why deferred | Notes |
|---|---|---|
| Reference sign video playback | Requires `.mp4` assets; increases app size; signer can use external video during MVP | V2 |
| Signer management UI | Can use separate phone instances per signer in MVP | V2 |
| Dataset browser with JSON viewer | Nice to have; file manager handles this in MVP | V2 |
| ZIP export | USB cable is fine for MVP; add export once dataset is large | V2 |
| CSV export | Same as ZIP | V2 |
| Cloud backup (Supabase/Drive) | Adds complexity and internet dependency; not needed for local collection | V3 |
| Automatic sign correctness model | Requires a pre-trained model; not available until after Phase 3 training | V3 |
| Reviewer mode (separate login) | Useful for multi-person projects; overkill for single-team capstone | V3 |
| Multi-device sync | Same as cloud backup | V3 |
| Raw video backup alongside JSON | Doubles storage; useful for debugging model failures | V2 |
| Dataset dashboard with charts | Nice for reporting; Excel/Python can do this from exported JSON | V3 |
| Face blendshape recording | FaceLandmarker is already running; expanding feature vector to 321 floats is V2 | V2 |
| Velocity + spatial features | Same as above | V2 |
| Augmentation preview | Show what augmented version of a sample looks like | V3 |

---

## 21. Next Development Steps

Follow these steps in order. Do not jump ahead.

### Step 1 — Project setup (Day 1)

- [ ] Create `com.example.aslrecorder` Android project (already created as `ASLRecorder2`)
- [ ] Add CameraX, MediaPipe Tasks Vision dependencies to `app/build.gradle.kts`
- [ ] Copy `KeypointExtractor.java` from AppHear main app as starting point
- [ ] Copy `HandLandmarkerHelper.java` from AppHear main app and rename to `MediaPipeRecorderHelper.java`
- [ ] Add MediaPipe `.task` model files to `assets/` folder
- [ ] Add `hand_landmarker.task`, `pose_landmarker_lite.task`, `face_landmarker.task`
- [ ] Add camera permission to `AndroidManifest.xml`
- [ ] Verify camera preview works on device

### Step 2 — Core pipeline (Day 2–3)

- [ ] Implement `LandmarkFrameBuffer.java` with zero-padding
- [ ] Wire `MediaPipeRecorderHelper` → `LandmarkFrameBuffer` in frame callback
- [ ] Implement `LandmarkOverlayView.java` (hand skeleton + shoulder line + tracking badges)
- [ ] Verify overlay renders correctly on device with live camera

### Step 3 — Recording state machine (Day 3–4)

- [ ] Implement `RecordingStateMachine.java` with all states
- [ ] Build `RecordingActivity.java` with countdown UI and state-driven display
- [ ] Wire state machine → UI updates (countdown text, flash animations, progress counter)
- [ ] Test full recording loop manually: IDLE → COMPLETE with a static hand

### Step 4 — Quality checking and saving (Day 4–5)

- [ ] Implement `SampleQualityAnalyzer.java` with all hard reject rules
- [ ] Implement `DatasetFileManager.java` with folder creation and JSON writing
- [ ] Implement `SampleData.toJson()` producing the full Phase 2 schema
- [ ] Test: record a sign → check JSON file saved correctly → verify schema

### Step 5 — Session setup and signer profile (Day 5–6)

- [ ] Build `SessionSetupActivity.java` with all metadata fields
- [ ] Build `SignerProfileActivity.java` with signer form
- [ ] Implement `MetadataManager.java` reading/writing `signers.json` and `sessions.json`
- [ ] Wire session metadata into every saved JSON sample

### Step 6 — Review and home screen (Day 6–7)

- [ ] Build `ReviewActivity.java` with accepted/rejected list and manual override
- [ ] Build `MainActivity.java` with dataset summary card and navigation
- [ ] Add save path display and folder open intent in RecordingActivity

### Step 7 — Background mode (Day 7–8)

- [ ] Add Background class to label selector
- [ ] Add `bg_scenario` field to SessionSetupActivity
- [ ] Modify `RecordingActivity` to use casual recording mode for Background
- [ ] Save to `samples/background/accepted/` or `rejected/`
- [ ] Test all 10 background scenarios

### Step 8 — Device testing and first recording session (Day 8–10)

- [ ] Install on recording device
- [ ] Run Version 0 recording session: 7 signs + Background × 4 signers × 60 samples
- [ ] Transfer dataset folder to laptop via USB
- [ ] Run Python `load_apphear_dataset()` function to verify JSON loads correctly
- [ ] Verify `X.shape == (N, 30, 258)` in Python
- [ ] Fix any schema or path issues found during loading test

### Step 9 — Phase 2 full recording sessions (Weeks 2–3)

- [ ] Schedule 7 signer recording sessions
- [ ] Record all 25 signs + Background for each signer
- [ ] Target: 80–100 accepted samples per sign per signer
- [ ] Run split verification script from Phase 2 plan before any training

---

*End of APPHEAR_DATASET_RECORDER_APP_PLAN.md*
*Related documents: PHASE_2_DATASET_COLLECTION_PLAN.md, APPHEAR_SIGN_DETECTION_IMPROVEMENT_HANDOUT.md, APPHEAR_FULL_SYSTEM_ANALYSIS.md*
*Next document to create: APPHEAR_DATASET_RECORDER_IMPLEMENTATION_GUIDE.md (actual code files)*
