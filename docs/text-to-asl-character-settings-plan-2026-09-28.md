# Text-to-ASL character choice in Settings

Status: user approved this plan. Existing 27-sign phone pilot installation is separately
authorized. This is an Android non-camera Settings/Text-to-ASL feature, extending the native
application Phase 5 screen group; it changes no recognition stage S0-S8.

## Choices and scope

Add an accessible Character row to Settings with a single-choice dialog:
**Original character** and **New character**. Store the selection locally with SharedPreferences,
through a small settings repository, without a new dependency. Default to Original for this
selection experiment. Remember the choice across navigation and app restarts.

Approved user steering after first installation: show the functional settings directly on the
Profile tab without requiring Edit. Reuse one SettingsContent renderer and character dialog on
both screens. In the selector pilot, move Profile preferences above the account form and put
the character choice first. Ordinary/default Profile layout and behavior retain their order.

Original selects the existing 102-entry catalog and original GLBs. New selects the validated
27-sign shared bundle: seven existing replacements plus 20 approved new word entries (122
catalog entries overall). The new character currently covers only these 27 signs; other
existing signs still use their original assets. Explain that partial coverage in the dialog.
Choosing Original removes the 20 new direct word entries; the unchanged planner handles their
input using its existing matching/fingerspelling rules. Never promise identical vocabulary or
a new avatar for all signs. Explicit big/call/pay meanings remain as previously approved.

## Implementation and lifecycle

Keep the existing asset flags; add separate default-off debug `aslCharacterSelection` flag
requiring the expanded shared bundle. Hide the row in builds without both character choices.
Release/default APK payload stays unchanged. The selector is independent of recognition
preferences and never toggles model/perception/handedness.

Catalog selection happens off the main thread. When returning to Text-to-ASL after a changed
preference, cancel the old queue and timers, release the prior viewer, rebuild the catalog/player
once, retain typed input, and require a fresh Sign It action. Never resume an old character's
queue after switching. When unchanged, retain current lifecycle behavior. Do not preload both
characters or retain a WebView/model per option. Invalid saved values resolve to Original;
invalid new manifest resolves to the original catalog. Existing per-clip fallback remains.

## Gates and rollback

Meaningful tests cover preference resolution/availability, original vs new catalog selection,
unchanged original mappings and four explicit phrase aliases. Run the full JVM and existing
player suites; build selection-ON and default-OFF APKs, inspect expanded/ordinary payload
identity and recognition parity before installation. Install over the existing app with data
preserved; save the prior phone APK. User tests both choices, restart persistence, change after
playback, Replay/Clear/leave-reopen, representative new signs and original-only signs. Collect
app-scoped load/completion/failure logs and memory diagnostics; physical F22 and semantic gates
remain explicitly pending until run. Seven-sign and original rollback APKs remain available.

No recognition feature-vector schema or train/serve parity changes. The asset selection contract
will be imprinted in context/feature-schema.md; review and handoff/progress notes will record
actual offline/phone results. Cross-signer recognition evaluation is not a metric for this
presentation-only change; no new recognition accuracy claim is made.
