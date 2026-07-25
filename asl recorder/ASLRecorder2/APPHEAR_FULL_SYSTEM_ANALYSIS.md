# AppHear Full System Analysis Report

## 1. App Overview

AppHear is an Android Java application for sign language communication. It has two main communication directions:

1. Sign Language to Text/Speech
   - The user signs in front of the camera.
   - The app tracks the signer through MediaPipe landmarks.
   - A TensorFlow Lite classifier predicts the sign.
   - The detected sign is shown as text.
   - The detected text can be spoken aloud through ElevenLabs or Android Text-to-Speech fallback.

2. Voice/Text to Sign Language
   - The user types text or speaks into the app.
   - Speech input is converted to text by Android speech recognition.
   - The text is normalized and matched to available sign animation clips.
   - A WebView-hosted 3D avatar plays the matching sign animations.

The current app is a single Android app module. It uses activity-driven architecture, meaning most feature logic is directly inside activities. Helper classes exist for MediaPipe, machine learning, Supabase auth, text planning, avatar playback, recent signs, and speech output.

## 2. Main Features

### 2.1 Sign Language to Text Detector

Main screen:

- `SignDetectActivity.java`
- `activity_sign_detect.xml`

Main capabilities:

- Camera preview through CameraX.
- Hand landmarks through MediaPipe Hand Landmarker.
- Pose landmarks through MediaPipe Pose Landmarker.
- Face landmarks through MediaPipe Face Landmarker.
- Visual overlay for hand skeleton, selected face points, and shoulder line.
- Buttons to show/hide face landmarks and hand landmarks.
- TensorFlow Lite classifier for sign prediction.
- Sentence accumulation from stable detected signs.
- Speak button using ElevenLabs TTS first, Android TTS fallback second.
- Swipeable/collapsible detector control panel.

Current supported model labels:

- `Hello`
- `Meet`
- `My`
- `Name`
- `Nice`
- `Thank You`
- `You`

Important limitation:

The app now detects and displays face landmarks, but the current classifier does not use face landmarks for prediction yet. The current classifier still receives the old `258`-feature input from pose and hands only.

### 2.2 Text to Sign Language 3D

Main screen:

- `TextToAslActivity.java`
- `activity_text_to_asl.xml`

Main capabilities:

- Text input mode.
- Speech input mode.
- Android speech recognizer converts voice to text.
- Text normalizer cleans and standardizes user input.
- Phrase planner maps text to available sign animation assets.
- WebView loads a local HTML viewer shell.
- 3D `.glb` animation assets are played by a `<model-viewer>` element.
- Replay button restarts the current sign sequence.
- Speak button reads the entered text aloud using ElevenLabs or Android TTS fallback.
- Recent signs from this feature are saved for the homepage.

Current animation support:

- Phrases:
  - `hello`
  - `nice to meet you`
- Individual letters:
  - `A` to `G`
- Grouped alphabet clips:
  - `F-I`
  - `J-T`
  - `U-Z`

Important limitation:

This feature does not generate sign language from arbitrary text. It maps text to available animation clips. If an input word or letter has no animation alias, that part is skipped or marked unsupported internally.

## 3. Project Structure Explanation

Project root:

```text
C:\Users\Gigabyte\AndroidStudioProjects\AppHear2
```

Important root files:

```text
settings.gradle.kts
build.gradle.kts
gradle.properties
local.properties
APPHEAR_CODEBASE_HANDOUT.md
APPHEAR_FULL_SYSTEM_ANALYSIS.md
supabase_profile_setup.sql
```

Important app module structure:

```text
app/
  build.gradle.kts
  proguard-rules.pro
  src/main/
    AndroidManifest.xml
    java/com/example/apphear/
    assets/
    res/
```

### 3.1 Java Packages

`com.example.apphear`

Contains main activities and shared UI/navigation classes:

- `SplashActivity`
- `LoadingActivity`
- `MainActivity`
- `SignDetectActivity`
- `ProfileActivity`
- `FeatureCardAdapter`
- `OnSwipeTouchListener`

`com.example.apphear.auth`

Contains Supabase authentication/profile logic:

- `SupabaseAuthManager`

`com.example.apphear.avatar`

Contains WebView avatar playback logic:

- `AvatarPlaybackController`

`com.example.apphear.data`

Contains local data helpers and unused sample/phrase classes:

- `RecentSignsStore`
- `Phrase`
- `PhraseRepository`
- `LandmarkSampleRecorder`

`com.example.apphear.mediapipe`

Contains MediaPipe setup and frame analysis:

- `HandLandmarkerHelper`

Despite the name, this class now handles hand, pose, and face landmarkers.

`com.example.apphear.ml`

Contains detector model input preparation and TensorFlow Lite classification:

- `KeypointExtractor`
- `TemporalBuffer`
- `SignClassifier`

`com.example.apphear.texttoasl`

Contains text-to-sign planning and speech input classes:

- `TextToAslActivity`
- `SpeechInputManager`
- `AslTextNormalizer`
- `AslAnimationRegistry`
- `AslPhrasePlanner`
- `AslAnimationAsset`
- `AslPlaybackQueue`

`com.example.apphear.ui`

Contains reusable UI helpers:

- `LandmarkOverlayView`
- `NavTouchAnimator`

`com.example.apphear.utils`

Contains speech and performance helpers:

- `ElevenLabsSpeechPlayer`
- `TtsVoiceHelper`
- `FrameRateTracker`

### 3.2 Assets

Important assets:

```text
assets/sign_classifier.tflite
assets/labels.json
assets/hand_landmarker.task
assets/pose_landmarker_lite.task
assets/face_landmarker.task
assets/model_viewer.html
assets/asl_animations/manifest.json
assets/asl_animations/*.glb
```

Roles:

- `sign_classifier.tflite`: TensorFlow Lite sign classifier.
- `labels.json`: label names and model metadata.
- `hand_landmarker.task`: MediaPipe model for hand landmarks.
- `pose_landmarker_lite.task`: MediaPipe model for body pose landmarks.
- `face_landmarker.task`: MediaPipe model for face landmarks and blendshapes.
- `model_viewer.html`: WebView page that hosts the 3D avatar viewer.
- `asl_animations/manifest.json`: registry of available animation clips and aliases.
- `.glb` files: 3D avatar animation clips.

### 3.3 Layouts

Important layouts:

- `activity_splash.xml`: first-time onboarding splash screen.
- `activity_loading.xml`: animated loading/calibration screen.
- `activity_main.xml`: homepage with greeting, recent signs, feature carousel, bottom nav.
- `activity_sign_detect.xml`: camera detector screen with overlay, controls, and permission panel.
- `activity_text_to_asl.xml`: 3D avatar screen with text/speech input bottom sheet.
- `activity_profile.xml`: profile, login/signup, settings, Supabase profile image.
- `nav_bottom.xml`: shared bottom navigation.
- `item_feature_card_detect.xml`: homepage detector card.
- `item_feature_card_project.xml`: homepage text-to-ASL card.
- `row_setting_*.xml`: settings rows in profile screen.

### 3.4 Resources

Important drawable groups:

- Mascots and branding:
  - `splash.png`
  - `applogo.png`
  - `mascot_detect.png`
  - `mascot_project.png`
  - `one_maskot.png`
  - `two_maskot.png`
  - `three_maskot.png`
- Navigation:
  - `homes.png`
  - `user_images.png`
  - `wave_hand.png`
  - `users.png`
  - `bg_nav_active_circle.xml`
  - `bg_nav_inactive_pill.xml`
- Detector:
  - `face_recognition.png`
  - `hand_recognition.png`
  - `soundwaves.png`
  - `flip.png`
  - `play.png`
  - `ic_pause.xml`
  - `bg_landmark_toggle.xml`
- Profile/auth/settings:
  - `bg_auth_*`
  - `bg_profile_*`
  - `bg_settings_panel_coffee.xml`
  - `bg_setting_row.xml`

## 4. Architecture and Code Flow

The app is currently activity-centered.

High-level launch flow:

```text
SplashActivity
  -> LoadingActivity
  -> MainActivity
```

If the user has already seen the splash:

```text
SplashActivity
  -> LoadingActivity
  -> MainActivity
```

So the loading screen still appears on later launches.

Main navigation:

```text
MainActivity
  -> SignDetectActivity
  -> TextToAslActivity
  -> ProfileActivity
```

Profile navigation:

```text
ProfileActivity
  -> MainActivity
  -> SignDetectActivity
  -> TextToAslActivity
```

The bottom nav exists on Home and Profile. Detector and Text-to-ASL use back buttons instead of the shared bottom nav.

### Current Architecture Style

The app uses direct Android activities instead of a layered architecture.

Examples:

- `SignDetectActivity` handles camera permission, camera setup, detection state, frame analysis callbacks, UI updates, TTS, landmark toggles, and sentence accumulation.
- `TextToAslActivity` handles speech recognition, text input, phrase planning, animation queue, avatar playback timing, mode switching, and TTS.
- `ProfileActivity` handles login/signup, profile rendering, image picking, remote avatar loading, and settings UI.

This is understandable for a prototype, but it makes larger changes riskier because UI logic and system logic are tightly mixed.

## 5. Sign Language Detector Architecture

Main classes:

- `SignDetectActivity`
- `HandLandmarkerHelper`
- `LandmarkOverlayView`
- `KeypointExtractor`
- `TemporalBuffer`
- `SignClassifier`
- `ElevenLabsSpeechPlayer`
- `TtsVoiceHelper`
- `FrameRateTracker`

### Detector Flow

```text
User opens SignDetectActivity
  -> app requests camera permission
  -> CameraX starts preview
  -> CameraX image analyzer receives frames
  -> HandLandmarkerHelper converts frame to bitmap
  -> MediaPipe pose, hand, and face landmarkers run
  -> LandmarkOverlayView draws selected landmarks
  -> KeypointExtractor builds model feature vector from pose and hands
  -> TemporalBuffer stores a 30-frame sequence
  -> SignClassifier runs TensorFlow Lite inference
  -> SignDetectActivity stabilizes the prediction
  -> UI shows detected sign, confidence, sentence
  -> Speak button reads detected text aloud
```

### Camera Input

CameraX is configured with:

```text
Target resolution: 640 x 480
Image format: RGBA_8888
Backpressure: STRATEGY_KEEP_ONLY_LATEST
Default camera: front camera
```

The analyzer only processes frames while `isDetecting` is true. If a frame is already being analyzed, new frames are dropped through `frameInFlight` to avoid stacking expensive work.

### MediaPipe Processing

`HandLandmarkerHelper` initializes:

- `HandLandmarker`
- `PoseLandmarker`
- `FaceLandmarker`

Per analyzed frame:

1. `ImageProxy` is converted into a `Bitmap`.
2. Bitmap is rotated if needed.
3. Bitmap becomes an `MPImage`.
4. Pose Landmarker detects body pose.
5. Hand Landmarker detects up to 2 hands.
6. Face Landmarker detects one face if available.
7. Results are bundled into `ResultBundle`.

### Landmark Overlay

`LandmarkOverlayView` draws:

- Hand skeleton points and connections.
- Selected face guide points and face guide lines.
- Shoulder points and shoulder line from pose landmarks.

The user can toggle:

- Face/shoulder overlay with `face_recognition.png`.
- Hand overlay with `hand_recognition.png`.

These toggles only affect what is displayed. They do not stop MediaPipe detection and do not change classifier input.

### Model Feature Extraction

`KeypointExtractor` creates a fixed `258`-float array:

```text
Pose:       33 landmarks x 4 values = 132
Left hand:  21 landmarks x 3 values = 63
Right hand: 21 landmarks x 3 values = 63
Total:                              258
```

Pose values are normalized relative to the nose.

Hand values are normalized relative to each wrist.

Face landmarks are currently not included in this feature vector.

### Temporal Buffer

`TemporalBuffer` stores recent frame features.

Settings:

```text
Sequence length: 30 frames
Minimum frames before inference: 15 frames
Feature size: 258
```

When fewer than 30 frames exist, it pads the missing frames by repeating the oldest available frame.

### Classification

`SignClassifier` loads:

- `sign_classifier.tflite`
- `labels.json`

It creates a TensorFlow Lite interpreter with 4 threads.

Input shape:

```text
[1][30][258]
```

Output:

```text
One confidence score per label
```

The classifier returns the label with the highest confidence.

### Prediction Stabilization

`SignDetectActivity` applies:

```text
Confidence threshold: 0.5
Stable frames required: 2
```

If the prediction confidence is too low, the UI shows low confidence.

If the same prediction stays stable long enough, it is appended to the visible sentence.

The app keeps only the last 5 words on screen, but this has a weakness: multi-word labels like `Thank You` can be split as separate words when trimming.

### Speech Output

The detector has a speak button.

When tapped:

1. It reads the accumulated detected sentence.
2. If the sentence is empty, it tries to read the current sign.
3. It sends the text to `ElevenLabsSpeechPlayer`.
4. If ElevenLabs is not configured or fails, Android `TextToSpeech` is used.

## 6. Text to Sign Language 3D Architecture

Main classes:

- `TextToAslActivity`
- `SpeechInputManager`
- `AslTextNormalizer`
- `AslAnimationRegistry`
- `AslPhrasePlanner`
- `AslAnimationAsset`
- `AvatarPlaybackController`
- `RecentSignsStore`
- `ElevenLabsSpeechPlayer`
- `TtsVoiceHelper`

### Text-to-ASL Flow

```text
User opens TextToAslActivity
  -> WebView loads model_viewer.html
  -> AvatarPlaybackController waits for viewer ready callback
  -> AslAnimationRegistry loads asl_animations/manifest.json
  -> user types text or uses speech input
  -> speech input becomes text through Android RecognizerIntent
  -> text is normalized
  -> AslPhrasePlanner finds matching animation clips
  -> TextToAslActivity builds playback queue
  -> AvatarPlaybackController sends GLB URL to JavaScript
  -> model-viewer loads and displays the animation
  -> Handler advances through the queue with fixed timing
```

### Text Input

Typed input comes from `inputText`.

When the user taps `SIGN IT`, `submitText()` is called.

### Speech Input

Speech input uses Android's built-in speech recognition:

```text
RecognizerIntent.ACTION_RECOGNIZE_SPEECH
LANGUAGE_MODEL_FREE_FORM
Locale.US
```

The speech recognizer returns a list of possible text matches. The app uses the first match.

### Text Normalization

`AslTextNormalizer`:

- lowercases the text
- removes punctuation
- collapses extra spaces
- maps `hi` and `hey` to `hello`

Example:

```text
"Hi!!!" -> "hello"
"Nice   to meet you." -> "nice to meet you"
```

### Animation Lookup

`AslAnimationRegistry` loads `asl_animations/manifest.json`.

Each animation has:

- `id`
- `displayText`
- `asset`
- `type`
- `aliases`

`AslPhrasePlanner` searches aliases longest-first. This allows phrase matches like `nice to meet you` before individual letters are considered.

If no phrase matches, it tries to find an individual letter animation.

### Avatar Playback

`AvatarPlaybackController`:

1. Configures WebView.
2. Enables JavaScript.
3. Uses `WebViewAssetLoader` so local assets can be loaded through:

```text
https://appassets.androidplatform.net/assets/
```

4. Loads `model_viewer.html`.
5. Exposes a JavaScript bridge named `Android`.
6. Waits for `Android.onViewerReady()`.
7. Calls JavaScript:

```text
playSign('asset-url')
```

The HTML file uses `<model-viewer>` to load and show the `.glb` model.

Important limitation:

`model_viewer.html` loads `model-viewer` from `https://unpkg.com`. This means the 3D feature depends on internet access for the viewer library, even though the `.glb` animations are local.

### Playback Timing

`TextToAslActivity` uses fixed timing:

```text
Phrase clip: 2500 ms
Letter clip: 1200 ms
```

It does not currently read the real animation duration from the `.glb` file.

## 7. Shared Components Between Features

Shared speech output:

- `ElevenLabsSpeechPlayer`
- `TtsVoiceHelper`

Both Sign Detect and Text-to-ASL can speak text aloud.

Shared swipe behavior:

- `OnSwipeTouchListener`

Used by the collapsible detector bottom sheet and the Text-to-ASL bottom sheet.

Shared UI/navigation:

- `nav_bottom.xml`
- `NavTouchAnimator`

Used on Home and Profile.

Shared user/profile state:

- `SupabaseAuthManager`

Used by Home and Profile for dynamic user information.

Shared recent signs:

- `RecentSignsStore`

Text-to-ASL saves the first word of typed/spoken input. Home displays up to 6 recent words.

## 8. Profile, Auth, and Backend Flow

Main class:

- `ProfileActivity`
- `SupabaseAuthManager`

Backend:

- Supabase Auth
- Supabase REST table `public.users`
- Supabase Storage bucket `profile-images`

### Auth Flow

Signup:

```text
username + email + password
  -> Supabase /auth/v1/signup
  -> session saved locally
  -> profile row upserted into public.users
```

Login:

```text
email + password
  -> Supabase password token endpoint
  -> session saved locally
  -> public.users profile row fetched
  -> local profile cache updated
```

Profile update:

```text
username/full name/avatar
  -> if avatar is local content URI, upload to Supabase Storage
  -> get public avatar URL
  -> update Supabase Auth metadata
  -> upsert public.users row
  -> update local SharedPreferences cache
```

Profile image display:

- Local selected image is shown immediately.
- Remote avatar URL is downloaded manually with `HttpURLConnection` and displayed as bitmap.

## 9. Important Files and Their Roles

### App Entry and Navigation

`SplashActivity.java`

Shows first-time splash screen. If the user has already seen it, it skips directly to loading.

`LoadingActivity.java`

Shows animated logo, slogan, and icons before opening Home.

`MainActivity.java`

Homepage. Shows dynamic username, recent signs, feature cards, dots, avatar/profile shortcut, and bottom nav.

`FeatureCardAdapter.java`

Provides two cards for the homepage carousel: detector and text-to-ASL.

`ProfileActivity.java`

Handles login/signup, profile info, avatar image picking, Supabase profile updates, settings UI, and bottom navigation.

### Sign Detection

`SignDetectActivity.java`

Main detector screen. Controls camera, permissions, model inference, UI state, landmark toggles, sentence accumulation, and speech output.

`HandLandmarkerHelper.java`

MediaPipe wrapper. Runs hand, pose, and face landmark models on camera frames.

`LandmarkOverlayView.java`

Draws visual landmarks over the camera preview.

`KeypointExtractor.java`

Converts pose and hand landmarks into a 258-float input vector.

`TemporalBuffer.java`

Stores recent feature frames and prepares the `[1][30][258]` model input.

`SignClassifier.java`

Loads the TFLite model and label file, runs inference, and returns best label/confidence.

### Text to ASL

`TextToAslActivity.java`

Main text/voice to avatar screen. Handles typed input, speech input, planning, queue playback, replay, and TTS.

`SpeechInputManager.java`

Builds Android speech recognizer intent and checks if speech recognition is available.

`AslTextNormalizer.java`

Normalizes input text for matching.

`AslAnimationRegistry.java`

Loads the animation manifest and builds alias lookup.

`AslPhrasePlanner.java`

Maps normalized text to animation clips.

`AvatarPlaybackController.java`

Controls the WebView and JavaScript bridge for 3D avatar playback.

### Speech

`ElevenLabsSpeechPlayer.java`

Calls ElevenLabs text-to-speech API, saves returned MP3 to cache, plays it with `MediaPlayer`, and falls back to Android TTS if needed.

`TtsVoiceHelper.java`

Chooses the best available English Android TTS voice.

### Data

`RecentSignsStore.java`

Stores up to 6 recent first words from Text-to-ASL input.

`Phrase.java`, `PhraseRepository.java`

Legacy/default phrase list. Not used in the current active UI flow.

`LandmarkSampleRecorder.java`

Can record hand landmark samples to JSON files. Not used in the current active UI flow.

## 10. Current Problems or Weak Points

### Accuracy

- The detector only supports 7 labels.
- Face landmarks are detected and displayed but not used by the classifier.
- The model input is still limited to pose + hands.
- Prediction smoothing is minimal.
- Stability requirement is only 2 repeated predictions.
- The confidence threshold is hardcoded at `0.5`.
- No user calibration exists.
- No dataset feedback loop exists for wrong predictions.
- No model metadata validation checks the TFLite input shape against `labels.json`.

### Performance

- Each frame is converted from `ImageProxy` to `Bitmap`.
- Pose, hand, and face landmarkers run per analyzed frame.
- TFLite inference runs on CPU with 4 threads.
- Adding face landmarks increases per-frame workload.
- WebView swaps `.glb` sources for each sign, which can cause delay.

### Maintainability

- Activities contain too much business logic.
- There is no ViewModel/state layer.
- Detector pipeline and UI are tightly coupled.
- Text-to-ASL queue logic is inside the activity.
- `AslPlaybackQueue` exists but is not used.
- Some text in Java/XML appears encoding-corrupted, for example `â€”`, `â€¦`, and `â€¢`.
- Hardcoded UI strings are spread across Java and XML.
- WebView debugging is always enabled.

### Feature Completeness

- Text-to-ASL only supports a small phrase/letter set.
- Unsupported tokens are collected but not shown to the user.
- Detector vocabulary and animation vocabulary are not unified.
- The app does not perform true natural language to ASL grammar conversion.
- Speech recognition depends on Android recognizer availability.
- ElevenLabs depends on internet and valid API configuration.

### Backend

- Supabase calls are made through manual `HttpURLConnection`.
- Session refresh is not implemented.
- Profile image loading is manual, without an image loading library.
- Profile image storage requires correct Supabase table, bucket, and policies.

## 11. Recommended Improvements

### Detector

1. Retrain the classifier to include face landmarks and face blendshapes.
2. Add model metadata validation.
3. Add better smoothing:
   - moving average confidence
   - prediction window voting
   - longer stability for similar signs
4. Add a clear vocabulary registry shared by detector and animation system.
5. Add a sample recording workflow for collecting training data.
6. Fix front/back camera mirroring based on current lens facing.
7. Profile frame latency after adding face landmarker.

### Text-to-ASL

1. Bundle `model-viewer` locally instead of loading it from CDN.
2. Read real animation duration instead of fixed timers.
3. Show unsupported words/letters to the user.
4. Expand animation coverage.
5. Add fingerspelling fallback for unsupported words.
6. Use `AslPlaybackQueue` or remove it.

### Architecture

1. Extract detector pipeline from `SignDetectActivity`.
2. Extract prediction stabilization into its own class.
3. Extract Text-to-ASL playback queue handling from `TextToAslActivity`.
4. Add ViewModel-style screen state classes.
5. Move hardcoded strings to `strings.xml`.
6. Add tests for:
   - `AslTextNormalizer`
   - `AslPhrasePlanner`
   - `TemporalBuffer`
   - sentence accumulation
   - recent signs storage

## 12. Actual Process: Sign Language to Text/Speech

### Simple Flow

```text
Input -> Process -> Output

User performs a sign
  -> camera captures video frames
  -> MediaPipe finds hands, body, and face
  -> app extracts hand/body movement data
  -> TFLite model predicts the sign
  -> app displays text
  -> user taps speak
  -> ElevenLabs or Android TTS speaks the text
```

### What Is the Input?

The input is the live camera view of the user signing.

The user places their hands and upper body in front of the camera and performs a sign such as `Hello` or `Thank You`.

### What Does the System Capture?

The camera captures a stream of image frames. Each frame is like a picture from the camera.

The app does not directly send the whole picture to the sign classifier. Instead, it first asks MediaPipe to find important body points.

### What Happens First?

When the user taps `START`:

1. The app starts analyzing camera frames.
2. Each frame goes to `HandLandmarkerHelper`.
3. The frame is converted into a format MediaPipe can read.
4. MediaPipe searches for:
   - hands
   - body pose
   - face

### How Hand Tracking Works

MediaPipe looks at the camera frame and finds important points on the hand.

These points are called landmarks or keypoints.

For one hand, MediaPipe gives 21 hand points. These include points like:

- wrist
- thumb joints
- index finger joints
- middle finger joints
- ring finger joints
- pinky finger joints

The app can detect up to two hands.

### What Are Landmarks/Keypoints?

Landmarks are small coordinate points that describe where important body parts are on screen.

Instead of saying:

```text
"There is a hand somewhere in this image."
```

The system gets structured data like:

```text
Wrist is here.
Thumb tip is here.
Index finger tip is here.
Shoulder is here.
Nose is here.
```

This makes it easier for the AI model to understand the gesture because the model receives body movement data instead of a raw camera image.

### What Data Is Extracted?

The app extracts:

- body pose landmarks
- left hand landmarks
- right hand landmarks

The current classifier uses:

```text
33 body pose points
21 left hand points
21 right hand points
```

These are converted into a list of 258 numbers for each frame.

The app also detects face landmarks and shoulder landmarks for display, but the current sign classifier does not use face landmarks yet.

### How Does the AI Analyze the Gesture?

The app does not classify one frame alone.

It collects a short sequence of frames. This matters because signs are movements, not just hand shapes.

Example:

```text
Frame 1: hand starts near the body
Frame 2: hand moves outward
Frame 3: hand changes position
Frame 4: sign motion continues
```

The `TemporalBuffer` stores this movement history.

When enough frames are collected, the app sends the sequence to the TensorFlow Lite model.

The model receives:

```text
30 frames of landmark data
```

Then it predicts which known sign best matches the movement pattern.

### How Does the System Recognize the Gesture?

The model outputs confidence scores for every sign it knows.

Example:

```text
Hello: 0.85
Name: 0.10
You: 0.05
```

The app chooses the sign with the highest confidence.

If the confidence is too low, the app does not accept it.

If the same sign appears stable for enough frames, the app treats it as a real detected sign.

### How Does the Recognized Sign Become Text?

The model returns a label like:

```text
Hello
```

The app displays it on screen as:

```text
HELLO
```

If the sign remains stable, it is also added to the sentence area.

Example:

```text
HELLO  MY  NAME
```

### How Does Text Become Speech?

When the user taps the sound/speech button:

1. The app checks the detected sentence.
2. If a sentence exists, it uses that.
3. If no sentence exists, it tries to use the current detected sign.
4. It sends the text to ElevenLabs.
5. ElevenLabs returns an audio file.
6. The app plays the audio.
7. If ElevenLabs is unavailable, Android TTS speaks the text instead.

### Final Output to the User

The user receives:

- visual landmark tracking on the camera
- detected sign text
- confidence feedback
- accumulated sentence text
- optional spoken audio of the detected sign/sentence

Final output:

```text
Camera sign -> recognized text -> optional spoken voice
```

## 13. Actual Process: Voice/Text to Sign Language

### Simple Flow

```text
Input -> Process -> Output

User types or speaks text
  -> speech is converted to text if needed
  -> text is cleaned and normalized
  -> app searches for matching sign animation clips
  -> app creates an animation queue
  -> WebView sends the selected GLB file to model-viewer
  -> 3D avatar performs the sign
```

### What Is the Input?

The input can be:

1. Typed text
2. Spoken voice

Typed example:

```text
hello
```

Spoken example:

```text
User says: "nice to meet you"
```

### What Happens If the User Speaks?

The app opens Android's speech recognition system.

The phone listens to the user and returns text.

Example:

```text
Voice input: "nice to meet you"
Recognized text: "nice to meet you"
```

The app then treats that recognized text the same way as typed text.

### What Happens If the User Types?

The app reads the text from the input box when the user taps `SIGN IT`.

Example:

```text
Typed input: "hello world"
```

### How Does the System Process the Text?

The text goes through `AslTextNormalizer`.

This cleans the input:

- converts it to lowercase
- removes punctuation
- removes extra spaces
- maps `hi` and `hey` to `hello`

Example:

```text
"Hey!!!" -> "hello"
```

### How Does the System Find the Equivalent Sign?

The app uses `AslAnimationRegistry`.

This registry reads `asl_animations/manifest.json`, which lists the sign clips the app currently has.

Each clip has aliases.

Example:

```text
Clip: hello.glb
Aliases: hello, hi, hey
```

The phrase planner tries to find the longest matching phrase first.

Example:

```text
Input: "nice to meet you"
Matched clip: nice_to_meet_you.glb
```

If no phrase matches, the system tries to match individual letters.

Example:

```text
Input: "bag"
Queue: B -> A -> G
```

This only works for letters that have available animations.

### What Happens After Matching?

The system builds a playback queue.

Example:

```text
Input: "hello a"
Queue:
1. hello.glb
2. anim_a.glb
```

The app displays:

- the original text
- the current sign being played
- the progress number, such as `1 / 2`

It also saves the first word of the input to recent signs.

Example:

```text
Input: "hello world"
Recent sign saved: "Hello"
```

### How Does the 3D Avatar Perform the Sign?

The app uses `AvatarPlaybackController`.

This controller loads `model_viewer.html` into a WebView.

Inside the HTML is a `<model-viewer>` element.

When the app wants to play a sign, it sends the animation file path to JavaScript:

```text
playSign("hello.glb")
```

The viewer loads the `.glb` file, and the avatar animation appears on screen.

### How Are Animation Sequences Triggered?

The app plays the first animation in the queue.

Then it waits a fixed amount of time:

```text
Phrase: 2500 ms
Letter: 1200 ms
```

After the delay, it moves to the next animation.

This continues until the queue is finished.

### Final Output to the User

The user receives:

- recognized text if they used voice input
- visible typed/spoken text
- current sign name
- progress count
- animated 3D avatar performing the sign sequence
- optional spoken playback of the input text

Final output:

```text
Voice/text -> cleaned text -> matched sign clips -> 3D avatar animation
```

## 14. Summary of Current State

AppHear currently has a working prototype-level system:

- Sign detection works using camera, MediaPipe, TFLite, and landmark sequences.
- Face landmarks are now visually integrated but not yet part of the classifier.
- Text-to-ASL works by mapping text to a limited set of local 3D animation clips.
- Speech output uses ElevenLabs first and Android TTS fallback.
- Speech input uses Android speech recognition.
- Profile/login uses Supabase Auth, Supabase table data, and Supabase Storage for avatar images.

The strongest part of the system is its practical structure:

```text
MediaPipe landmarks + TFLite classifier + local GLB animation playback
```

The main next technical milestone is to turn the visual face landmark integration into real model input by retraining the detector with hand, pose, and selected face features together.
