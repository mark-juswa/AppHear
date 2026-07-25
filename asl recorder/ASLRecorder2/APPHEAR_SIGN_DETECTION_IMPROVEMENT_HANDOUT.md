# AppHear Sign Detection Improvement Handout

**Document Type:** Project Alignment and Technical Reference  
**Project:** AppHear — Android Sign Language Communication App  
**Scope:** Sign Language to Text/Speech Detection System  
**Status:** Active development — improvement planning phase  
**Last Updated:** 2026-05-23  

> This document preserves the full technical direction of the AppHear sign detection improvement project. It is written so that any developer, researcher, or AI assistant can read it cold and immediately understand what has been built, what is wrong, what the plan is, and what must happen next. If the conversation context resets, start here.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Current Sign Detection System](#2-current-sign-detection-system)
3. [Current Technical Limitations](#3-current-technical-limitations)
4. [Target Goal](#4-target-goal)
5. [Meaning of Real Signer Communication Standard](#5-meaning-of-real-signer-communication-standard)
6. [Recommended AI Approach](#6-recommended-ai-approach)
7. [Proposed CNN-LSTM Architecture](#7-proposed-cnn-lstm-architecture)
8. [Improved Feature Extraction Plan](#8-improved-feature-extraction-plan)
9. [Dataset and Training Plan](#9-dataset-and-training-plan)
10. [Real-Time Android Detection Pipeline](#10-real-time-android-detection-pipeline)
11. [Android Codebase Impact](#11-android-codebase-impact)
12. [Deployment Strategy](#12-deployment-strategy)
13. [Evaluation Metrics](#13-evaluation-metrics)
14. [Development Roadmap](#14-development-roadmap)
15. [Important Technical Decisions](#15-important-technical-decisions)
16. [What Not To Do](#16-what-not-to-do)
17. [Next Immediate Tasks](#17-next-immediate-tasks)
18. [Handoff Summary for Future AI / Developers](#18-handoff-summary-for-future-ai--developers)

---

## 1. Project Overview

AppHear is an Android Java mobile application designed to bridge communication between signers and non-signers. It is built with accessibility as its core purpose and targets real sign language communication rather than a toy demonstration.

### Two Main Features

**Feature 1 — Sign Language to Text/Speech**

The user signs in front of the device camera. The app tracks body landmarks using MediaPipe, runs a TensorFlow Lite model to classify the sign, displays the detected text on screen, and can speak the text aloud using ElevenLabs TTS or Android TTS fallback.

**Feature 2 — Voice/Text to Sign Language (3D Avatar)**

The user types text or speaks into the app. The input is normalized, matched against available animation clips, and a 3D avatar in a WebView plays the corresponding sign animations using `.glb` files and a `<model-viewer>` element.

### Scope of This Handout

This document focuses entirely on improving **Feature 1: Sign Language to Text/Speech detection**. The 3D avatar feature has separate concerns and is not covered here.

---

## 2. Current Sign Detection System

### Pipeline Overview

The current detection pipeline runs entirely on-device in Android Java:

```
CameraX (640x480, RGBA_8888, front camera)
  └── ImageProxy → Bitmap → MPImage
        └── HandLandmarkerHelper (MediaPipe)
              ├── PoseLandmarker   → 33 landmarks × {x, y, z, visibility}
              ├── HandLandmarker   → up to 2 hands × 21 landmarks × {x, y, z}
              └── FaceLandmarker   → landmarks + blendshapes (detected, NOT used in classifier)
                    └── ResultBundle passed to SignDetectActivity
                          └── KeypointExtractor
                                ├── Pose:       33 × 4 = 132 floats
                                ├── Left hand:  21 × 3 = 63 floats
                                └── Right hand: 21 × 3 = 63 floats
                                     Total = 258 floats per frame
                                          └── TemporalBuffer
                                                └── 30-frame sequence [1][30][258]
                                                      └── SignClassifier (TFLite)
                                                            └── Softmax → 7 class scores
                                                                  └── Prediction stabilization
                                                                        └── UI display + TTS
```

### Frame Gating

- `frameInFlight` flag prevents stacking expensive analysis while a frame is being processed.
- `STRATEGY_KEEP_ONLY_LATEST` backpressure drops frames that arrive during processing.
- Inference only runs when `isDetecting` is `true` (user tapped START).

### Normalization

- Pose landmarks are normalized relative to the nose (landmark 0).
- Hand landmarks are normalized relative to each hand's wrist (landmark 0).

### Prediction Stabilization (Current — Basic)

- Confidence threshold: `0.5`
- Stable frames required: `2`
- If the same label appears in 2 consecutive inference results with confidence >= 0.5, it is accepted.

### TTS Output

- Primary: ElevenLabs API (requires internet and API key)
- Fallback: Android `TextToSpeech`

### Current Supported Labels

| Label | Type |
|---|---|
| Hello | Dynamic (movement) |
| Meet | Dynamic |
| My | Dynamic |
| Name | Dynamic |
| Nice | Dynamic |
| Thank You | Dynamic |
| You | Dynamic |

**Total: 7 signs. No background/rest class. No unknown sign class.**

### Key Source Files

| File | Role |
|---|---|
| `SignDetectActivity.java` | Main detector screen, camera setup, UI, stabilization, TTS |
| `HandLandmarkerHelper.java` | MediaPipe wrapper for pose, hand, and face landmarkers |
| `LandmarkOverlayView.java` | Draws visual landmark overlay on camera preview |
| `KeypointExtractor.java` | Converts landmarks to 258-float feature vector per frame |
| `TemporalBuffer.java` | Stores 30-frame sequence, pads with repeated oldest frame |
| `SignClassifier.java` | TFLite model loader and inference runner |
| `ElevenLabsSpeechPlayer.java` | ElevenLabs TTS + Android TTS fallback |

---

## 3. Current Technical Limitations

### Model and Vocabulary

- **Only 7 labels.** Not enough for real communication. A basic conversation requires hundreds of signs.
- **No background or rest class.** The model always predicts one of the 7 known signs, even when the user is not signing. This causes constant false positives.
- **No unknown sign class.** Any sign outside the 7-label vocabulary is misclassified as the nearest-looking known sign.
- **No model metadata validation.** If `labels.json` and the TFLite input shape are mismatched, the app will silently produce wrong predictions.

### Stabilization

- **2-frame stability is too short.** At 30 fps, 2 consecutive frames is approximately 66ms. A model guessing randomly will coincidentally repeat the same label in 66ms very often. This produces false confirmations.
- **No moving average or majority voting.** Single-frame inference results are used directly for stabilization decisions.
- **No sign start or sign end detection.** The pipeline does not know when a sign is happening versus when the signer is at rest or transitioning between signs.
- **No debounce.** The same sign can be appended to the sentence multiple times if the signer holds the final hand position slightly too long.

### Feature Extraction

- **Face landmarks are detected but not used in classification.** The `FaceLandmarker` runs per frame, costing CPU time, but the resulting face data is never passed to `KeypointExtractor` or the classifier.
- **Handedness is not mirror-corrected.** For front camera, MediaPipe's left/right classification is mirrored relative to the signer's actual dominant hand. This degrades accuracy for asymmetric signs.
- **No velocity features.** The current 258-float vector contains only static positions per frame. Motion speed and direction are not explicitly encoded.
- **No hand-to-body distance features.** The spatial relationship between the hands and the face or shoulders is not a direct feature.
- **Padding strategy is wrong.** When fewer than 30 frames are in the buffer, the oldest frame is repeated to fill the gap. This creates a false temporal pattern at the start of the sequence that the model was not trained to recognize.

### Architecture

- **`SignDetectActivity` is overloaded.** It contains camera setup, permission handling, frame analysis callbacks, model inference orchestration, UI updates, sentence accumulation, TTS, and landmark toggle logic. This makes safe incremental improvement extremely risky.
- **No ViewModel or state layer.** All detection state is stored directly in the activity.
- **`AslPlaybackQueue` exists but is unused.** Technical debt from an incomplete feature.

### Dataset and Generalization

- **Single or very few signers.** The current model was likely trained on a small, non-diverse dataset.
- **No signer-variation robustness.** Different signers performing the same sign will likely not be recognized reliably.
- **No support for continuous signing.** Signs must be performed in isolation.

---

## 4. Target Goal

AppHear's sign detection improvement goal is not simply to increase model accuracy on a small label set. The goal is to build a detection system that is:

- **Accurate** — correctly identifies signs across diverse signers and conditions
- **Stable** — does not produce false positives when the user is at rest or transitioning
- **Real-time** — responds within 300ms of sign completion, matching natural signing pace
- **Signer-friendly** — works for different people without requiring recalibration
- **Scalable** — architecture supports growing the vocabulary to hundreds of signs
- **Communicative** — produces meaningful sentence-level output, not just isolated word detection

The target is a detection system that can support real, basic sign language conversation within the vocabulary it knows — not just a gesture classification demo.

---

## 5. Meaning of Real Signer Communication Standard

A system that meets a real communication standard must handle each of the following:

### Hand Shape Accuracy

Many ASL sign pairs differ only by hand shape:
- A, S, and E handshapes look similar from a front camera
- D and F handshapes differ by minor finger extension

The system must resolve these differences reliably from MediaPipe landmark data.

### Motion Direction and Path

Many ASL sign pairs differ only by movement direction or location:
- `Mother` (chin) vs. `Father` (forehead) — same handshape, different location
- `Please` vs. `Sorry` — similar handshape, different circular motion direction

The system must track hand trajectory, speed, and direction across frames.

### Facial Expression

Facial expressions are grammatically required in ASL:
- Raised eyebrows = yes/no question
- Furrowed brows = wh-question (who, what, when)
- Head nods/shakes = affirmation/negation
- Mouth movements = adverbs and intensifiers

A system that ignores the face cannot understand questions, negation, or sentence type.

### Body Posture

Shoulder orientation and upper body lean encode spatial grammar. Signs performed in different parts of the signing space reference different people or objects (referential loci).

### Signer Variation

Different signers produce the same sign with different:
- Hand size, joint flexibility, signing speed
- Signing space size (some sign small, some sign large)
- Dominant hand (left-handed signers mirror many signs)
- Regional accent (ASL has regional variation)

A communication-grade system generalizes across signers it has never seen.

### Signing Speed

Native signers sign at approximately 100–200 signs per minute. The system must keep up with natural speed and cannot require the signer to artificially slow down.

### Sign Transitions

Between two signs, the hands move from the ending position of one sign to the starting position of the next. This is a transition, not a sign. The system must recognize transitions and not classify them.

### Sentence Flow and Continuous Signing

Communication is not isolated words — it is sentences with grammar. The system must accumulate correctly detected signs into meaningful sentences without requiring a manual confirmation step between each word.

### Confidence and Failure Communication

The system should know when it does not recognize something and communicate that to the user (for example, "I did not understand, please repeat") rather than silently outputting a wrong word with low confidence.

---

## 6. Recommended AI Approach

### Why CNN Is Needed

A Convolutional Neural Network (CNN) applied per frame acts as a **spatial feature extractor**. Each frame of landmark data is a structured representation of body position. CNN learns spatial relationships between landmark coordinates:

- The angle between finger joints (hand shape)
- The distance between thumb tip and pinky tip (open vs. closed hand)
- The relative position of the wrist to the chin (sign location)

CNN is position-tolerant — it recognizes the same spatial pattern even if the hand is slightly shifted from frame to frame.

**CNN alone is not enough.** A CNN on a single frame cannot determine if a hand is moving or stationary. It cannot distinguish signs that differ only by movement direction. Two identical hand positions can belong to completely different signs depending on what motion came before.

### Why LSTM Is Needed

A Long Short-Term Memory (LSTM) network applied across a sequence of frames learns **temporal motion patterns**:

- Hand movement direction (upward stroke vs. downward stroke)
- Movement speed (fast flick vs. slow arc)
- Sequential hand configurations (sign starts open, then closes)
- Transitions (which frame-to-frame changes are signs vs. transitions)

**LSTM alone is not enough.** LSTM over raw 258-float landmark vectors learns from noisy, jittery coordinate sequences. Without first compressing each frame's spatial structure into a clean feature, the LSTM cannot efficiently learn temporal patterns across the noise.

### Why CNN + LSTM Together

```
Raw landmarks (258 floats per frame)
  → CNN/Dense encoder: extracts clean spatial descriptor per frame (64-128 floats)
      → LSTM: learns temporal motion patterns across 30 frames of spatial descriptors
          → Output: classification across N signs + background
```

CNN reduces each noisy 258-float frame to a smaller, cleaner spatial representation. LSTM then learns temporal grammar over those cleaner descriptors. The combination is more trainable, more generalizable, and more robust than either approach alone.

For AppHear's landmark-based input (not raw image pixels), the CNN component is implemented as a `TimeDistributed` dense encoder applied per frame — this is the practical mobile-compatible equivalent of a spatial CNN for structured landmark data.

---

## 7. Proposed CNN-LSTM Architecture

### Input Format

```
Shape: [batch_size, 30, feature_dim]

Where:
  batch_size = 1 (real-time single sequence inference)
  30         = number of frames per sequence (1 second at 30 fps)
  feature_dim = 258 (Phase 1–2) → 318+ (Phase 3 with face features)
```

### Model Architecture (Keras)

```python
model = tf.keras.Sequential([
    # Input
    InputLayer(input_shape=(30, feature_dim)),

    # Per-frame spatial encoder (applied independently to each frame)
    TimeDistributed(Dense(128, activation='relu')),
    TimeDistributed(BatchNormalization()),
    TimeDistributed(Dropout(0.3)),
    TimeDistributed(Dense(64, activation='relu')),

    # Temporal sequence learning
    LSTM(128, return_sequences=True),
    Dropout(0.3),
    LSTM(64, return_sequences=False),
    Dropout(0.3),

    # Classification output
    Dense(N + 1, activation='softmax')
    # N = number of sign classes
    # +1 = mandatory background/rest class
])
```

### Output Layer

- `N` sign class scores + `1` background class score
- Softmax activation gives confidence probabilities that sum to 1.0
- The background class represents: resting hands, transitions between signs, unknown signs, or empty frame

### Confidence Scoring

| Condition | Action |
|---|---|
| `max_confidence >= 0.65` AND not background | Accept prediction — output sign label |
| `max_confidence < 0.65` | Reject — output background regardless of label |
| Background class wins | Output background — no sign detected |

### Handling Unknown Signs

- Unknown signs (not in the trained vocabulary) should activate the background class if they do not resemble any known sign closely
- If an unknown sign resembles a known sign, the system will misclassify — this is expected and acceptable at the capstone scale
- A dedicated "unsupported sign" indicator in the UI should communicate uncertainty to the signer

### Avoiding False Detections When No Signer Is Present

Two pre-inference checks in Android (cost: nearly zero):

1. **Pose presence check:** At least one shoulder landmark must have visibility > 0.5. If no person is detected in frame, skip inference entirely.
2. **Hand presence check:** If MediaPipe returns no hand landmarks for the current frame, skip inference and output background directly.

---

## 8. Improved Feature Extraction Plan

The following describes the updated `KeypointExtractor` feature set.

### Hand Landmarks (Core — 126 floats)

- Both hands: 21 landmarks × 3 coordinates (x, y, z) × 2 hands = **126 floats**
- Normalize each hand relative to its own wrist (landmark 0)
- Scale by the distance from wrist to middle finger MCP joint (landmark 9) for size invariance
- If a hand is not detected: fill all 63 values with `0.0`

```
Normalization formula:
  scale = distance(wrist, middleMCP)
  normalizedX = (landmark.x - wrist.x) / scale
  normalizedY = (landmark.y - wrist.y) / scale
  normalizedZ = (landmark.z - wrist.z) / scale
```

### Pose Landmarks (Upper Body — 132 floats)

- All 33 pose landmarks × 4 values (x, y, z, visibility) = **132 floats**
- Normalize relative to the midpoint between the two hip landmarks (23 and 24)
- Scale by the hip-to-shoulder distance for body-size invariance
- If a landmark has visibility < 0.5: zero out its x, y, z but keep visibility = 0.0

Most important pose landmarks for ASL:
- Shoulders (11, 12), Elbows (13, 14), Wrists (15, 16)
- Nose (0), Eyes (1–6), Hips (23, 24)

### Face Features — Phase 3 Addition (~15–52 floats)

**Option A (Recommended):** Use MediaPipe Face Landmarker blendshape scores directly.
- Already running in the app, just accessing unused output
- ~52 named scores: `browInnerUp`, `jawOpen`, `mouthSmileLeft`, etc.
- Select 12–15 most relevant blendshapes for ASL grammar (brow, mouth, eye aperture)
- Values normalized to [0.0, 1.0] — no additional normalization needed

**Option B:** Use 20 selected raw face landmark coordinates (brow region, mouth region, eye corners) = 60 floats.

Start Phase 3 with Option A (blendshape scores). It is simpler, smaller, and more semantically meaningful.

### Handedness Flag (2 floats)

- `[is_left_hand_detected, is_right_hand_detected]`
- Binary (0.0 or 1.0) per hand slot
- Tells the model which hand slots are real data vs. zero-padded

### Movement Velocity (4 floats per frame)

```
velocity_leftWrist_x[t]  = leftWrist.x[t] - leftWrist.x[t-1]
velocity_leftWrist_y[t]  = leftWrist.y[t] - leftWrist.y[t-1]
velocity_rightWrist_x[t] = rightWrist.x[t] - rightWrist.x[t-1]
velocity_rightWrist_y[t] = rightWrist.y[t] - rightWrist.y[t-1]
```

Explicit velocity features directly encode motion direction and speed, helping LSTM distinguish similar static poses that differ only by motion.

### Spatial Relationship Features (5 floats per frame)

```
inter_hand_distance        = distance(leftWrist, rightWrist)
dist_rightWrist_to_nose    = distance(rightWrist, noseLandmark)
dist_leftWrist_to_nose     = distance(leftWrist, noseLandmark)
dist_rightWrist_to_rightShoulder = distance(rightWrist, rightShoulder)
dist_leftWrist_to_leftShoulder   = distance(leftWrist, leftShoulder)
```

Encode whether hands are near the face (facial signs), near the body (body signs), or far apart (two-handed signs).

### Handedness Mirroring for Front Camera

MediaPipe's handedness label is mirrored for a front-facing camera:
- MediaPipe "Right" → Signer's actual Left hand
- MediaPipe "Left" → Signer's actual Right hand

In `KeypointExtractor`, swap the hand slot assignment when `isFrontCamera == true` so that the signer's dominant hand is always placed in a consistent feature slot. This is critical for correct recognition of asymmetric signs.

### Missing Landmark Handling

| Situation | Handling |
|---|---|
| Hand not detected | Fill 63 floats with 0.0; set handedness flag to 0.0 |
| Pose landmark visibility < 0.5 | Zero out x, y, z; keep visibility = 0.0 |
| Face not detected | Fill face feature slot with 0.0 |
| No landmarks at all | Skip inference; output background class |

Never skip frames with missing landmarks. The model must learn to handle partial occlusion.

### Summary: Feature Dimensions by Phase

| Phase | Features | Floats Per Frame |
|---|---|---|
| Phase 1–2 | Pose + Hands + Handedness + Velocity + Spatial | ~269 |
| Phase 3 | Above + Face blendshapes (15) | ~284 |
| Phase 3 (full) | Above + Face blendshapes (52) | ~321 |

---

## 9. Dataset and Training Plan

### Target Vocabulary Size

| Phase | Signs | Rationale |
|---|---|---|
| Phase 1 | 7 (current) + background | Fix the current model with a rest class |
| Phase 2–3 | 30–50 | Achievable for a capstone team in 2–3 recording sessions |
| Phase 5+ | 100–200 | Post-capstone expansion |

A practical 30–50 sign vocabulary for Phase 2 should include:
- Extended greetings and introductions (expand from current 7)
- Common questions: what, where, who, when, how, why
- Common responses: yes, no, please, sorry, thank you, okay
- Numbers: 1–10
- Full fingerspelling alphabet (A–Z)

### Samples Per Sign

| Target | Minimum |
|---|---|
| 300–500 samples / sign / signer | 100 samples / sign / signer |
| 500+ samples for background class | 200+ samples for background class |

Background/rest class samples must include:
- Hands at rest in lap or sides
- Transitioning between signs (hands moving between positions)
- Signing words outside the vocabulary
- Speaking without signing

### Number of Signers

| Target | Minimum |
|---|---|
| 10–15 different signers | 5 different signers |

Include variation in:
- Signing speed (natural speed and deliberately slow)
- Dominant hand (include at least 1–2 left-handed signers)
- Camera distance (close vs. arm's length)
- Shirt color (avoid skin-tone colors)

### Recording Environment Variation

Record in at least 3 conditions:
1. Indoor, good lighting (baseline)
2. Indoor, dim or variable lighting
3. Outdoor or high-brightness environment

Different backgrounds (plain, busy, light, dark) to prevent the model from relying on background cues.

### Recording Workflow

Use `LandmarkSampleRecorder.java` (expanded in Phase 1 to record the full 258-float feature vector via `KeypointExtractor`). Wire it into a dedicated data-collection mode:

1. Display the sign to perform (text or reference image)
2. Countdown: 3, 2, 1, Sign
3. Capture the 30-frame landmark sequence automatically
4. Auto-label with the displayed sign name
5. Save to structured JSON
6. Advance to next sign prompt

### Data Format

```json
{
  "label": "Hello",
  "signer_id": "s01",
  "session": "2026-05-20",
  "camera": "front",
  "frames": [
    [0.12, -0.34, 0.05, ...],
    [0.11, -0.33, 0.06, ...],
    ...
  ]
}
```

### Train / Validation / Test Split

**Critical: split by signer, not by sample.**

| Split | Signers | Purpose |
|---|---|---|
| Train | 70% of signers | Model learning |
| Validation | 15% of signers | Hyperparameter tuning, early stopping |
| Test | 15% of signers (held out, never seen) | Final honest accuracy report |

Splitting by sample (random shuffle across all signers) artificially inflates accuracy. The model memorizes signer-specific patterns. Splitting by signer gives an honest estimate of generalization.

### Data Augmentation (Applied During Training)

| Augmentation | Method | Purpose |
|---|---|---|
| Coordinate jitter | Gaussian noise σ=0.02 on all coordinates | Simulate tracking noise |
| Speed variation | Resample frames at 0.8x or 1.2x, interpolate back to 30 | Simulate signing speed variation |
| Mirror/flip | Flip x-axis, swap left/right hand slots | Simulate left-handed signers |
| Landmark dropout | Randomly zero 1–3 landmarks per frame | Simulate partial occlusion |
| Scale variation | Scale all coordinates by random factor [0.85, 1.15] | Simulate different body sizes |
| Temporal shift | Shift sequence start by ±3 frames | Simulate different buffer capture timing |

### Preventing Overfitting

- Dropout 0.3 after each Dense and LSTM layer
- Batch normalization after each Dense encoder layer
- Early stopping on validation loss (patience = 10 epochs)
- L2 weight regularization (0.001) on Dense layers
- Keep the model small: the dataset is small, so the model must be appropriately sized

---

## 10. Real-Time Android Detection Pipeline

### Frame Capture

- CameraX `ImageAnalysis` with `STRATEGY_KEEP_ONLY_LATEST` (keep current)
- Frame gating via `frameInFlight` flag (keep current)
- Extract frame timestamp in milliseconds for velocity computation

### MediaPipe Landmark Extraction

- `HandLandmarkerHelper` continues to run all three landmarkers per frame (keep current)
- Add `FaceLandmarkerResult` to `ResultBundle` so `KeypointExtractor` can access blendshapes

### Sliding Window Inference

Replace the "run only when buffer is exactly full" approach with a sliding window:

```
Run inference every 5 frames (approximately every 166ms at 30 fps)
This gives approximately 6 inference calls per second
Each inference uses the most recent 30 frames from the buffer
```

This allows the system to catch a sign that completes in the middle of the 30-frame window, rather than waiting until the window fully cycles.

### Temporal Buffer Improvement

Replace "pad by repeating oldest frame" with **zero-padding at the start**:

- Zero-padding represents "no motion before this" — semantically correct
- Repeating the oldest frame creates a false temporal pattern the model was never trained on

### Inference Trigger Conditions

Both conditions must be met before running TFLite inference:

1. Buffer contains at least 15 frames
2. At least one hand is detected in the most recent frame

If condition 2 fails, output background class directly without running TFLite. This is free and eliminates false positives when no signer is present.

### Prediction Smoothing (Moving Average Confidence)

Replace the 2-frame stability check with a moving average over the last 10 inference results:

```java
// Maintain a circular buffer of last 10 (label, confidence) pairs
// Compute per-label average confidence across the window
// The smoothed prediction = label with highest average confidence

smoothedLabel = labelWithHighestAverageConfidence(last10Results)
smoothedConfidence = averageConfidence(smoothedLabel, last10Results)
```

Accept the smoothed prediction only if `smoothedConfidence >= 0.65`.

### Sign State Machine

```
States: IDLE → SIGNING → COMPLETE → COOLDOWN → IDLE

IDLE:
  - Background or low confidence → stay IDLE
  - Any sign class exceeds 0.65 avg for 5 consecutive inferences → SIGNING

SIGNING:
  - Track the current candidate label
  - Same label for 8+ consecutive inferences → COMPLETE
  - Different non-background label for 5+ inferences → transition to new sign label
  - Background class wins for 5+ inferences → return to IDLE

COMPLETE:
  - Emit confirmed sign to sentence accumulator
  - Enter COOLDOWN

COOLDOWN:
  - Ignore all predictions for 300ms
  - Return to IDLE
```

### Debounce Logic

Minimum 500ms gap before the same sign label can be appended to the sentence a second time. Prevents "Hello Hello" from a held final hand position.

### Sign Start and End Detection

The state machine above handles start (IDLE → SIGNING) and end (SIGNING → COMPLETE or SIGNING → IDLE) detection. An additional lightweight check using wrist velocity can identify natural sign boundaries (when hands return to neutral position).

### Continuous Signing Preparation (Phase 4+)

For Phase 4, add a **sign boundary detector** — a lightweight classifier or rule-based check that detects when the signer's hands return to a neutral/resting position between signs. When a boundary is detected:
- Close the current signing segment
- Run classification on the completed segment
- Immediately open the next signing segment

This allows signing multiple words without stopping between each.

---

## 11. Android Codebase Impact

### Files That Need to Be Modified

| File | Changes Required |
|---|---|
| `SignDetectActivity.java` | Remove pipeline logic; delegate to `DetectionPipelineController`; handle only UI, camera, and TTS |
| `HandLandmarkerHelper.java` | Add `FaceLandmarkerResult` to `ResultBundle`; pass face data through |
| `KeypointExtractor.java` | Add face blendshape features, velocity, spatial distance features, handedness mirroring, zero-padding |
| `TemporalBuffer.java` | Replace repeat-oldest padding with zero-padding; add sliding window inference trigger |
| `SignClassifier.java` | Update to match new input shape `[1][30][feature_dim]`; add background class handling; add `isBackground()` method |
| `LandmarkOverlayView.java` | Optional: improve face landmark display for meaningful face points |

### New Classes That Should Be Created

| New Class | Role |
|---|---|
| `DetectionPipelineController.java` | Orchestrates the full detection pipeline; owns `KeypointExtractor`, `TemporalBuffer`, `SignClassifier`, `PredictionSmoother`, `SignStateDetector`; exposes a simple `Listener` interface to the activity |
| `PredictionSmoother.java` | Maintains the moving average confidence window across the last N inference results; computes smoothed label and confidence |
| `SignStateDetector.java` | Implements the IDLE / SIGNING / COMPLETE / COOLDOWN state machine; manages debounce; emits confirmed sign events |
| `LandmarkFeatureExtractor.java` | New name for expanded `KeypointExtractor` logic; handles face features, velocity, spatial distances, handedness mirroring |
| `ModelMetadataValidator.java` | On startup, validates that the TFLite model input shape matches the feature dimension and that `labels.json` count matches the model output size; logs a clear error if mismatched |

### Clean Architecture After Refactoring

```
SignDetectActivity
  └── owns UI, camera, permissions, TTS, speak button, landmark toggle
  └── delegates to DetectionPipelineController via Listener interface
        └── DetectionPipelineController
              ├── LandmarkFeatureExtractor (expands KeypointExtractor)
              ├── TemporalBuffer
              ├── SignClassifier
              ├── PredictionSmoother
              └── SignStateDetector
                    └── emits: onSignConfirmed(label), onSignInProgress(label, confidence), onBackground()
```

The activity receives only high-level events. It never directly touches inference, buffers, or feature extraction. This makes each component independently testable and independently improvable.

---

## 12. Deployment Strategy

### Comparison of Deployment Options

| Aspect | On-Device (TFLite) | Cloud Inference | Hybrid |
|---|---|---|---|
| Accuracy | Limited to on-device model size | Can use large, powerful models | On-device fast + cloud for confirmation |
| Speed | 20–80ms per inference | Depends on network | On-device speed for real-time |
| Latency | Very low (no network) | 200–800ms round trip — unacceptable for real-time | Low for on-device path |
| Cost | Zero per-inference cost | Server costs scale with users | Moderate — cloud used selectively |
| Offline Support | Full offline | No offline | On-device path works offline |
| Privacy | All data stays on device | Landmark data leaves the device | Depends on which path is triggered |
| Scalability | Model updates require app update | Instant model updates server-side | Flexible |
| Mobile Performance | Needs quantization for efficiency | No mobile constraint | Best of both |

### Recommendation by Stage

**Phase 1–5 (Capstone Scope): Fully On-Device TFLite**

Reasons:
- The model input is landmark data (~30KB per inference call) — small enough for fast on-device inference
- A CNN-LSTM with 128/64 hidden units fits under 5MB as a TFLite flatbuffer
- Inference at 6 calls/second (sliding window) runs under 50ms per call on a Snapdragon 660 or newer with INT8 quantization
- No internet dependency for core communication feature
- All landmark data stays on device — appropriate for an accessibility communication app
- No cost at inference time

**On-Device Optimization Steps:**
1. Train in Keras (float32)
2. Apply TFLite INT8 post-training quantization (4× size reduction, ~2× speed improvement, < 2% accuracy loss)
3. Enable TFLite GPU delegate with CPU 4-thread fallback
4. Benchmark with Android Profiler and TFLite benchmark tool before shipping

**Phase 5+ (Post-Capstone Scaling): Hybrid**

- On-device model handles the common vocabulary (low latency)
- Cloud endpoint serves a larger model for vocabulary expansion
- On-device model requests cloud confirmation when confidence is below 0.5
- Cloud path only used for ambiguous or rare signs

---

## 13. Evaluation Metrics

### Offline Metrics (Python, on Held-Out Test Signers)

| Metric | Target (Phase 2) | Measurement Tool |
|---|---|---|
| Top-1 Accuracy | >= 90% | `sklearn.metrics.accuracy_score` |
| Per-class Precision | >= 85% for all classes | `classification_report` |
| Per-class Recall | >= 85% for all classes | `classification_report` |
| Macro F1-Score | >= 0.87 | `f1_score(average='macro')` |
| Background Class Precision | >= 95% | Confusion matrix diagonal |
| False Positive Rate | <= 5% | `(FP / (FP + TN))` |

**Confusion Matrix** is the most important offline tool. Print the full matrix. Inspect which sign pairs are confused most often. These pairs reveal where more training data or better features are needed.

### On-Device Runtime Metrics (Measured on Target Hardware)

| Metric | Target |
|---|---|
| Single inference latency | < 80ms |
| End-to-end frame-to-confirmed-sign latency | < 300ms |
| Camera preview frame rate | >= 25 fps |
| Model size (TFLite file) | < 10MB |
| RAM footprint (model + buffer) | < 50MB |

### Real-Signer Testing Protocol

Conduct structured testing sessions with signers who were not part of the training data:

1. Show each sign label on screen
2. Signer performs the sign naturally (no countdown)
3. Record whether the app detected the correct sign
4. Record how many attempts were needed

**Metrics to collect:**
- First-attempt recognition rate per sign
- Average attempts per sign
- Signs that consistently fail (candidates for retraining)
- Signer feedback on whether they felt forced to sign unnaturally

### Communication Success Rate (Primary Practical Metric)

```
Scenario: Signer performs a 3-sign sentence using only supported vocabulary
Metric:   (correctly reconstructed sentences) / (total sentence attempts)
Target:   >= 80% for 3-word sentences using trained vocabulary
```

This directly measures whether AppHear reaches a communication-grade standard, not just isolated-sign classification accuracy.

### Usability Metrics

- System Usability Scale (SUS) questionnaire score >= 70
- Task completion rate for standard communication scenarios
- Time per sentence (from start of signing to correct text display)
- Number of corrections the signer needed to make

---

## 14. Development Roadmap

| Phase | Name | Duration | Goal | Key Deliverables |
|---|---|---|---|---|
| **Phase 1** | Stabilize Current Detector | 2–3 weeks | Fix false positives, add background class, clean architecture | `PredictionSmoother`, `SignStateDetector`, retrained 7+1 label model |
| **Phase 2** | Build Better Dataset | 3–4 weeks | Collect diverse multi-signer data for 30–50 signs | Dataset JSON files, structured recording sessions, signer coverage |
| **Phase 3** | Train CNN-LSTM Model | 2–3 weeks | Replace current model with CNN-LSTM trained on new dataset | Keras model, TFLite conversion, updated `labels.json` |
| **Phase 4** | Improve Real-Time Stabilization | 2 weeks | Sliding window, smoothing, state machine, debounce | `DetectionPipelineController`, `SignStateDetector` with full state machine |
| **Phase 5** | Add Face and Body Features | 3–4 weeks | Incorporate face blendshapes, retrain model | Expanded `LandmarkFeatureExtractor`, Phase 3 retrain |
| **Phase 6** | Continuous Signing | 4–5 weeks | Detect sign boundaries, remove forced pauses between signs | Sign boundary detector, upgraded state machine, sentence accumulator |
| **Phase 7** | Expand Vocabulary | 3–4 weeks | Scale to 100–200 signs, optimize model for mobile | Expanded dataset, INT8 quantization, model size profiling |
| **Phase 8** | User Testing with Signers | 2–3 weeks | Validate with real signers, measure communication success rate | Usability testing report, accuracy report, final retrain based on failures |

### Phase 1 Detailed Task List

- [ ] Implement `PredictionSmoother.java` with moving average confidence window
- [ ] Implement `SignStateDetector.java` with IDLE/SIGNING/COMPLETE/COOLDOWN state machine
- [ ] Add hand presence check and pose visibility check before inference
- [ ] Fix `TemporalBuffer` padding (replace repeat-oldest with zero-padding)
- [ ] Add sliding window inference trigger (every 5 frames)
- [ ] Record background/rest class samples from current signers
- [ ] Retrain current model to include background class as label 8
- [ ] Convert retrained model to TFLite, replace in `assets/`
- [ ] Create `ModelMetadataValidator` to validate input shape and label count on startup
- [ ] Extract pipeline logic from `SignDetectActivity` into `DetectionPipelineController`

---

## 15. Important Technical Decisions

The following decisions have been made for AppHear's improvement plan. These should not be revisited without strong justification.

| Decision | Rationale |
|---|---|
| **Use landmark features, not raw image pixels** | Landmarks are compact (~30KB per inference), device-independent, privacy-preserving, and already extracted by MediaPipe. Raw image CNN would require 100× more compute and training data. |
| **Use CNN-LSTM (spatial encoder + temporal LSTM)** | Signs are spatial-temporal — they combine hand shape (spatial) and movement (temporal). Neither model alone is sufficient. The combination is the established best practice for gesture recognition from skeleton/landmark data. |
| **Start with small vocabulary, expand carefully** | High accuracy on 30 well-trained signs is more useful than poor accuracy on 200 signs. The architecture scales — the dataset does not scale automatically. |
| **Improve dataset quality before improving model complexity** | More diverse data from more signers provides more accuracy gain per effort than architectural changes. Model improvements on a poor dataset still produce a poor model. |
| **On-device TFLite for the capstone stage** | No network dependency, no latency penalty, zero per-inference cost, all data stays on device. The model size and compute requirements fit within mobile constraints with INT8 quantization. |
| **Mandatory background/rest class** | Without it, the model always outputs a sign prediction, causing constant false positives. The background class is not optional — it is essential for any practical deployment. |
| **Split dataset by signer, not by sample** | Splitting by sample produces inflated accuracy because the model memorizes signer-specific patterns. Only signer-split evaluation honestly measures generalization to new users. |
| **Zero-padding instead of repeat-oldest-frame padding** | Repeating the oldest frame creates a false temporal pattern. Zero-padding represents "nothing was happening before this" — semantically correct for the start of a sign. |
| **Raise confidence threshold from 0.5 to 0.65** | 0.5 is too permissive. With 7 classes, a random model would reach ~14% confidence per class. At 0.5, weak predictions pass. 0.65 requires genuine model certainty. |
| **Consider cloud/hybrid only for Phase 5+ vocabulary expansion** | At 30–50 signs, on-device is fully capable. Cloud adds latency, cost, and network dependency. Only worth considering when vocabulary exceeds on-device model capacity. |

---

## 16. What Not To Do

These are active warnings based on the current codebase and the nature of sign language recognition. Avoid these approaches.

- **Do not jump to hundreds of signs without a strong, diverse dataset.** Model architecture improvements cannot compensate for limited training data. A better model with bad data still produces bad predictions. Build the dataset before scaling vocabulary.

- **Do not rely on confidence thresholding alone for stability.** A threshold of 0.5 or even 0.65 on a single inference result is not enough. The model can produce high-confidence wrong predictions on a single noisy frame. Always combine thresholding with temporal smoothing (moving average) and a state machine.

- **Do not use face landmarks only for display if they affect sign meaning.** The current app runs `FaceLandmarker` every frame but ignores the results in the classifier. This wastes compute and misses grammatical signal. Either use the face data in the classifier or disable the FaceLandmarker to save resources.

- **Do not add more business logic to `SignDetectActivity`.** The activity is already overloaded. Every additional feature added there increases the risk of breaking unrelated functionality and makes future improvements harder. Extract to `DetectionPipelineController` first.

- **Do not claim communication readiness without testing with actual signers.** Offline accuracy on a test set from your own team is not the same as working with real signers. The system may achieve 92% on your test set and 60% in real use if the training signers were not diverse enough. Always test with people not in the training data.

- **Do not treat sign language as simple word-by-word gesture recognition.** ASL has its own grammar, syntax, and morphology that differs from English word order. The system accumulates detected labels in English order, which does not reflect ASL grammar. This is acceptable for the capstone scope, but should be acknowledged rather than ignored. True ASL-to-English translation requires natural language processing beyond gesture classification.

- **Do not use Bidirectional LSTM for the capstone scope.** BiLSTM improves accuracy by reading sequences forward and backward, but doubles LSTM parameters, significantly complicates TFLite conversion, and adds inference latency. The accuracy benefit does not justify the added complexity at this stage.

- **Do not train on publicly available ASL video datasets alone.** Datasets like WLASL and MS-ASL use raw video, not MediaPipe landmark sequences. Converting them to your feature format is significant work, and the resulting data may not match your normalization pipeline. Use them as reference or supplement — not as primary training data.

- **Do not deploy a model without first running `ModelMetadataValidator`.** If `labels.json` label count and TFLite output shape do not match, predictions will be silently incorrect. Always validate at app startup.

---

## 17. Next Immediate Tasks

The following tasks are the most practical starting points based on the current codebase state. Execute them in this order.

| Priority | Task | Why First |
|---|---|---|
| 1 | Validate current model metadata | Confirm `labels.json` matches TFLite input shape `[1][30][258]` and output size 7. Fix any mismatch before building on top of it. |
| 2 | Fix `TemporalBuffer` padding | Change from repeat-oldest to zero-padding. This is a 5-line change with significant correctness impact. |
| 3 | Implement `PredictionSmoother` | Add moving average confidence window. This will immediately improve stability without any new data or model changes. |
| 4 | Implement `SignStateDetector` | Add IDLE/SIGNING/COMPLETE/COOLDOWN state machine with 300ms cooldown and 500ms debounce. This alone will eliminate most repeated-word false detections. |
| 5 | Add hand presence check and pose check | Before running TFLite, check that at least one hand and one shoulder are detected. Free false-positive elimination. |
| 6 | Record background/rest class samples | Collect 200+ samples of non-signing states from 2–3 signers. This is the most impactful dataset change possible right now. |
| 7 | Retrain current 7-label model with background class | Add background as label index 8. Retrain the existing architecture first (do not change to CNN-LSTM yet). This gives a working baseline before architectural changes. |
| 8 | Convert retrained model to TFLite, replace in assets | Update `sign_classifier.tflite` and `labels.json`. Test on device. |
| 9 | Create `DetectionPipelineController` | Extract pipeline logic from `SignDetectActivity`. After this refactor, all further improvements are isolated to the pipeline classes. |
| 10 | Create `ModelMetadataValidator` | Validate on app startup that model shape and label count match. Log clear error if not. |
| 11 | Begin multi-signer dataset recording | Schedule recording sessions with 5+ signers. Use `LandmarkSampleRecorder` in data collection mode. |
| 12 | Build Python CNN-LSTM training pipeline | Once multi-signer data is collected, train the CNN-LSTM model, convert to INT8 TFLite, replace in assets. |

---

## 18. Handoff Summary for Future AI / Developers

**Read this section first if you are picking up this project cold.**

### What the Project Is

AppHear is an Android Java application for sign language communication. It has two features: (1) sign language detection using the camera, and (2) text/voice to 3D avatar animation playback. This handout covers Feature 1 only.

### What Has Already Been Built

The app has a working but limited sign detection pipeline:
- CameraX captures frames at 640×480 from the front camera
- MediaPipe detects hand, pose, and face landmarks per frame (face landmarks are detected but unused in the classifier)
- `KeypointExtractor` converts pose and hand landmarks to a 258-float vector per frame
- `TemporalBuffer` stores 30 frames, padding short sequences by repeating the oldest frame
- A TensorFlow Lite model takes `[1][30][258]` input and outputs confidence scores for 7 signs
- Basic prediction stabilization requires 2 identical predictions at confidence >= 0.5
- ElevenLabs TTS or Android TTS speaks detected text aloud

The current supported vocabulary: Hello, Meet, My, Name, Nice, Thank You, You.

### What the Current Problem Is

The current system is a limited prototype, not a communication tool:
- Only 7 signs — not enough for real communication
- No background/rest class — the model always outputs a sign even when nobody is signing, causing constant false positives
- 2-frame stability is too short and produces coincidental false confirmations
- Face landmarks are detected and processed per frame but contribute zero to the classifier
- No sign start/end detection — continuous real-time inference produces repeated detections
- `SignDetectActivity` contains too much logic — pipeline and UI are tightly coupled
- The 258-float feature set lacks velocity, spatial distance relationships, and handedness correction

### What the Chosen Solution Direction Is

Improve the system in phases:
1. Immediately: fix stabilization (moving average confidence, state machine, zero-padding), add background class, extract pipeline from the activity
2. Short-term: collect diverse multi-signer data for 30–50 signs, train a CNN-LSTM model (TimeDistributed Dense encoder + LSTM 128→64), convert to INT8 TFLite
3. Medium-term: add face blendshape features, expand vocabulary, add continuous signing support
4. Long-term: hybrid on-device/cloud deployment for large vocabulary

The architecture remains on-device TFLite with MediaPipe landmarks — not raw image CNN and not cloud inference — for latency, privacy, and cost reasons.

### What Should Be Done Next

1. Fix `TemporalBuffer` zero-padding and implement `PredictionSmoother` + `SignStateDetector`
2. Record background/rest class data and retrain the 7-label model to include it
3. Extract pipeline logic from `SignDetectActivity` into `DetectionPipelineController`
4. Schedule multi-signer recording sessions using `LandmarkSampleRecorder`
5. Build CNN-LSTM training pipeline in Python/Keras
6. Train, quantize, deploy new model
7. Validate with signers not in the training data

**The single most impactful next action: add the background/rest class and fix stabilization.** These two changes require no new model architecture and no new data beyond a few minutes of rest-state recordings, but they will immediately make the detection noticeably more reliable and usable.

---

*End of AppHear Sign Detection Improvement Handout*  
*Generated from full project analysis of AppHear source code and architecture review.*  
*For questions or updates, refer to `APPHEAR_FULL_SYSTEM_ANALYSIS.md` for codebase context.*
