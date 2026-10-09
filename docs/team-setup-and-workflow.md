# Team setup and safe workflow

## Clone the actual shared version

```powershell
git clone --branch codex/team-handoff-2026-10-09 https://github.com/mark-juswa/AppHear.git AppHear
Set-Location -LiteralPath '.\AppHear'
git status --short
python .\tools\handoff\verify_shared_state.py
```

Use a fresh clone; never overlay another teammate's dirty checkout. Assets are ordinary Git objects, not LFS
pointers. Initial clone is large (the new GLBs alone total737MiB uncompressed, plus prior assets/history).
No exact download-size/time prediction is provided. No ZIP download/re-import is needed to build.

## Android

Use JDK17, Android SDK36/build tools compatible with checked-in AGP8.11.2 and Gradle8.13;
actual versions are checked in `android/gradle/libs.versions.toml` and wrapper properties.
Android Studio opens the `android` folder. Create ignored `android/local.properties` with your own
`sdk.dir=C:/Users/YOU/AppData/Local/Android/Sdk` (or correct installed SDK location).
Set JAVA_HOME to your JDK17; run `java -version`. Do not copy the supervisor's SDK/credentials files.

```powershell
& .\tools\android\build_working_baseline.ps1 -Configuration fake -OriginalWords
```

This wrapper validates frozen model package hashes, runs JVM tests and builds debug and instrumented-test APKs.
It supplies the actual experimental flags. Plain `assembleDebug` does NOT enable this full application candidate.
`fake` explicitly blanks service credentials and uses the deterministic test Context Assist provider;
it is not evidence of live Gemini, profile backend or ElevenLabs service availability.
The Original extension flag is optional; omit -OriginalWords for the frozen102-entry Original rollback.
Default/release feature flags remain OFF. Do not change release defaults just to make the demo appear.

For real services, obtain configuration through a separate approved private channel and use ignored
`android/gradle.properties` or process environment. Relevant names: APPHEAR_GEMINI_API_KEY,
APPHEAR_CONTEXT_ASSIST_API_KEY, APPHEAR_SUPABASE_URL/APPHEAR_SUPABASE_ANON_KEY,
APPHEAR_ELEVENLABS_API_KEY (voice/model names per build.gradle.kts). Never commit actual values.
`-Configuration private -OriginalWords` uses the existing private provider selection. These debug APKs can
contain keys in BuildConfig; keep them local. This is NOT a secure production credential-distribution solution.

Install the fake build on an authorized test phone with `adb install -r` (retain app data), then test Text-to-ASL
with Original chosen in Settings. Recognition requires camera permission. Device command:

```powershell
adb install -r .\android\app\build\outputs\apk\debug\app-debug.apk
adb install -r .\android\app\build\outputs\apk\androidTest\debug\app-debug-androidTest.apk
adb shell am instrument -w -e class com.example.apphear.OriginalWordBatchInstrumentedTest com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
adb shell am instrument -w -e class 'com.example.apphear.coordination.RecognitionCoordinationInstrumentedTest#actualOwnerAutomaticEntryConfirmedSpellingAndWordPreservation' com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
```

Run playback and ownership tests separately to avoid the observed activity-focus timeout. Device performance
must be measured on your device; Xiaomi results are not a promise for another phone.

## Research, without launching training

Python3.11 was used; final V2.1 environment recorded TensorFlow2.21.0/Keras3.15.0.
`requirements.txt` is intentionally unpinned legacy guidance, not a proven cross-platform lockfile.
See `evidence/team_handoff_20261009/research_environment_observed.json` for installed research versions.
Create a separate virtualenv and install project requirements compatible with your OS. The checked-in
history/environment files are authoritative for reproducing each run. Do not assume different dependency
versions give bit-identical resumes. No Python environment is needed for Android except the optional hash checker.

Focused source tests (NumPy/pytest required; see their dependencies):

```powershell
python -m pytest tests/test_fingerspelling_prefix_beam.py tests/test_fingerspelling_single_letter.py
```

Do NOT run training/preflight/acquisition blindly: research defaults still refer to original I: storage,
cached foundation raw/features, selected model locations and original code hashes. Read the external-artifact
guide, provision data through an approved channel, map storage explicitly and validate lineage first.

## Team workflow

Review/merge the shared PR before declaring main current. Preserve October9/October5 tags and branches.
Work on `codex/<feature>` branches; use PRs, scoped commits, no force push or blanket git add of local data.
Read AGENTS + current-state documents first; retain WORD protection. Label experimental results and distinguish
held-out offline CER from live/isolated-letter accuracy. Every runtime change needs flags, host regression,
parity where applicable and device engineering checks. Update context/progress/decision/evidence together.
