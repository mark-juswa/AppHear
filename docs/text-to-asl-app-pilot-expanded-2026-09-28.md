# Expanded Text-to-ASL asset pilot

User requested more asset replacements after the three-clip pilot. Four additional exact-ID matches
are included: **ALL, BROTHER, CHILD, CITY**. Pilot total: **A, B, ALL, BROTHER, CHILD, CITY, FAMILY**.
All other clips retain the original character asset. Current catalog IDs/aliases/planning remain
unchanged, including pronoun I, WHOLE and COME TO HERE; no new vocabulary is introduced.

Seven source GLBs total **83.14 MiB** before APK compression. Only debug builds using
`-PaslAssetPilot=true` include them. Ordinary/release builds retain original payload/player.
All original assets are kept in pilot builds for fallback. The existing bounded player/cache and
local decoder implementation is reused. Hashing now covers seven files on the IO dispatcher;
startup cost still needs phone measurement.

## Repeatable staging

```powershell
# From the project root: inspect selection, then stage exact-ID matches.
python .\tools\text_to_asl_assets\stage_pilot.py --plan
python .\tools\text_to_asl_assets\stage_pilot.py
# From android/: build the expanded pilot or the ordinary rollback.
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug -PaslAssetPilot=true
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug -PaslAssetPilot=false
```

The staging command verifies source/output hashes and batch decoded-data validation, refuses differing
existing derivatives and unreferenced leftover GLBs, and atomically updates the pilot manifest.
It depends on the existing machine-local assessment inventory/batch artifacts. Its selection is
limited to exact source IDs matching existing WORD/LETTER IDs. New `sourceId` metadata is also
checked by the runtime loader; missing/invalid overrides retain original assets.

The other 44 optimized source signs have no exact eligible current catalog match. Mapping BIG to
LARGE, ASK to REQUEST, or COME to COME TO HERE is not inferred automatically. Letter-I stays distinct
from existing pronoun I. HELLO/THEM older-generation exports and SORRY remain excluded as before.
Adding unmatched vocabulary is a separate contract change, beyond this focused replacement scope.

The previous three-clip APK delivery is retained. Expanded APKs/results are delivered in a separate
`G:\3d Characters\android_pilot_7_20260928` folder; see its build-verification report for exact sizes,
checksums and test results. No phone install or broader default activation occurs.

Both ON/OFF builds and full JVM suites passed: **99 tests, zero failures/errors** in each mode.
All six existing player tests passed. Expanded pilot APK: **379.86 MiB**; default/rollback:
**307.88 MiB**. APK inspection verifies every pilot payload matches source, exactly seven GLBs
are bundled, all 102 original GLBs are byte-identical in both APKs, and default excludes pilot
payload. The final `app-debug.apk` in the ordinary build output is flag OFF.

## Review and remaining validation

Plan alignment PASS for expanded exact-match replacements. System integrity PASS: original catalog,
planner, recognition/perception/camera/model/config/production vocabulary remain unchanged. Production
readiness stays pending, with two important gates: actual WebView rendering/decoder/fallback/lifecycle
validation and phone cold/warm p50/p95, peak memory and frame pacing. Critical issues: 0. Minor: 1,
unchanged old idle/remaining signs produce a mixed-character pilot. User explicitly deferred device
testing; additional signs have not been visually or semantically approved in the app.

Use the phone validation checklist in `docs/text-to-asl-app-pilot-2026-09-28.md` when ready, adding
`all brother child city family` and repeats/clear/rapid input/navigation tests. Recommendation:
retain disabled-by-default expansion with fallback; measure before default activation or more rollout.


## Subsequent phone validation

The deferred-device status above is historical. User later authorized physical testing;
see [phone pilot report](text-to-asl-phone-pilot-2026-09-28.md) for the corrected completion
handling, direct user confirmation, measured memory/decode costs and remaining rollout gates.
Use the corrected android_pilot_phone_tested_20260928 delivery rather than the older APKs.
