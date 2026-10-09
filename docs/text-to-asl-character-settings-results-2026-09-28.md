# Text-to-ASL character choice

Status: implemented, offline-validated and installed on the user's M2101K7AG. Two targeted
Android instrumentation tests passed. User confirmed direct Profile visibility and both
characters work. Full control/app-restart, remaining signs and sustained performance checks
remain pending; default/release remain OFF.

## User flow

Profile → Text-to-ASL character opens a single-choice dialog for Original character
or New character. Initial/invalid preference is Original. The selection is saved locally and
read when reopening Text-to-ASL. Original loads the unchanged 102-entry catalog. New loads
122 entries, using the 27-animation shared bundle for seven existing replacements plus 20 new
word entries. Other signs and idle keep their existing assets. The Settings description explains
this coverage and vocabulary difference. The four explicit meanings remain big horizontally,
call by phone, call someone's name and pay me; plain big/call/pay get no inferred mapping.

The preference does not change recognition, camera, models, accounts or speech settings. It
adds no dependency. The row reuses existing Settings visuals, semantic colors, typography and
spacing/touch tokens. Its vertical layout wraps longer copy and selected labels. TalkBack sees
the current selection and the tap action; physical large-font/TalkBack checks are still pending.

After first installation the user reported having to tap Edit to reach the working settings.
The selector pilot now puts the functional preferences above Profile's account form, with
character choice first, using one SettingsContent renderer on Profile and Settings. The existing
Settings page remains reachable. Ordinary/default Profile ordering and passive rows are unchanged.

## Implementation and validation

`AslCharacterChoice` safely resolves stable original/new preference IDs. `AslCharacterSettings`
persists only this choice in SharedPreferences text_to_asl/character. The loader selects original
or expanded assets on IO. A changed choice cancels the old queue/job/timers, retains typed input
and releases the previous player document before constructing one new player. This also handles
navigation which destroys/recreates the view on a retained fragment. No old queue resumes after
changing character. No simultaneous two-character residency or second persistent WebView is added.
The existing pilot completion player is used for both choices in this flagged build; default
ordinary playback stays unchanged. Manifest and per-clip original fallback policy stay intact.

Build the selector pilot with:

```powershell
cd android
.\gradlew.bat testDebugUnitTest assembleDebug -PaslAssetPilot=true -PaslSharedCharacter=true -PaslMoreWords=true -PaslCharacterSelection=true --console=plain --no-daemon --max-workers=2
```

The fourth property requires the expanded bundle; it defaults false and release is always false.
Without it, existing pilots ignore this saved preference and retain their previous behavior. With
all asset flags off, the row is hidden and experimental GLBs/decoders/player are excluded.

- Selector-ON and all-flags-OFF builds: 105 JVM tests each, zero failures/errors; assembleDebug pass.
- Existing deterministic player suite: eight tests pass.
- APK verification: original 102 GLBs unchanged in both; one experimental GLB in selector build,
  none in ordinary build. All 234 packaged asset entries match the approved 27-sign APK byte-for-byte,
  including recognition/model/config assets. No new assets, permissions or activity exports.
- Physical targeted instrumentation: OK (2 tests), 0.55 seconds initially and 0.54 seconds after
  the Profile correction. Actual AssetManager catalogs are
  102/122, exact approved meaning phrases plan correctly, original-only mappings remain unchanged,
  saved preference survives repository recreation and unknown preference resolves to Original.
  The test restores the prior preference after running; this is not an app-restart/UI validation.
- Prior installed APK backed up as installed-before-settings.apk. Both installations used install -r
  to retain app data. MainActivity is not exported; launch uses the existing SplashActivity route.
- Final ordinary build output is all flags OFF; the phone runs the saved selector-ON APK.

Evidence: artifacts/text_to_asl_character_settings_20260928/. Delivery:
G:\3d Characters\android_character_choice_20260928 (selector APK, prior phone APK and ordinary
rollback APK, reports). The GLB is the same 36.05 MiB approved derivative; no conversion was rerun.
The final selector APK is apphear-character-choice-profile.apk; apphear-character-choice.apk
is the earlier version which required opening the separate Settings page. The corrected ordinary
rollback is apphear-default-profile-rollback.apk. Earlier builds are retained as history.

Human result on corrected build: “Visible directly; both characters work.” Scoped logs independently
show New catalog122 and completion of ALL, AFTERNOON, BAG and PAY ME, then Original catalog102
and completion of old ALL/A/B clips. No watchdog advances or reported failures in the captured
session. The first observed shared-bundle request took 7,361 ms; first-sequence same-bundle
transitions were64/66/67 ms (p50 66, p95 about67 ms,n3). These are small uncontrolled diagnostics,
not a general load/frame/memory guarantee. App-restart persistence, full controls and the
remaining new phrase meanings are still pending. The temporary instrumentation companion was
removed; scoped log capture stopped. The installed app and its data remain.

## Review and remaining gates

Plan alignment: PASS. System integrity: PASS (presentation-only settings, IO catalog, single player,
unchanged recognition payload and original mappings). Production readiness: pending physical gates.
Critical issues: 0 found offline. Important open gates: 2 — human per-sign/selector/lifecycle checks
and controlled first-load, frame, memory/thermal testing on target phones. Minor: 0 identified.
Recommendation: retain as a flagged phone pilot; do not enable ordinary/release builds yet.
Recognition cross-signer accuracy and feature-vector schema are not changed or re-evaluated by
these presentation checks. Full F22 smoke remains pending, rather than silently claimed passed.

Developer-run check: choose New and play all afternoon bag big horizontally call by phone
call someone's name pay me; choose Original and play all brother family. Verify selected preference
after closing/reopening the app; exercise Replay, Clear halfway and leave/reopen. Observe that
original-only signs retain existing character and that switching never resumes an old queue.
Keep the previous phone APK available if first load, decoding or controls fail. Raw scoped logs
will record completion/failure/watchdog callbacks; no phone rendering/performance claim follows
from file-size or instrumentation results alone.
