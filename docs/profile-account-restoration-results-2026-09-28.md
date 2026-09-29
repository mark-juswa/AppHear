# Profile/account restoration — 2026-09-28

Approved scope: restore the established account flow after inspecting the actual screenshot,
reference XML and ProfileActivity, rather than inventing a separate/local editor. Plan:
[profile-local-edit-plan-2026-09-28.md](profile-local-edit-plan-2026-09-28.md) (historical filename).

## Result and behavior

Restored Your/Profile → AppHear user card → Preference/Your Setting. Character choice remains the
first preference below the card, without an Edit prerequisite. Removed Edit→Settings routing and
the visible deferred-auth placeholder. Guest action opens the reference Login/Register panel;
signed-in Edit enables full name/username in the same card and becomes Save Profile. Email stays
read-only. Cancel discards the draft; avatar picking, remembered login and Logout are wired.

Account data layer uses Supabase Auth v1 with platform HTTPS/JSON; no new SDK/dependency. The same
username/full_name/avatar_url metadata keys preserve reference profile compatibility without
unverified writes to the old public users table. Existing-account email/password login and
registration are explicit user actions. Email confirmation returns a normal instruction to
verify and then log in; no blind fallback login or weakening of backend confirmation. Metadata
is display-only, never authorization. Only anon/publishable client keys are accepted by the client.

Remembered access/refresh sessions use backend-bound AES/GCM Android Keystore encryption,
excluded from cloud/device backup. Unchecked sessions stay in memory; passwords never persist.
Serialized IO prevents parallel refresh races and commits rotated tokens even after navigation.
Logout requests local-scope revocation and always clears this phone's identity, reporting if
server revocation could not be confirmed. Network errors preserve cached profile with a safe
message; invalid sessions clear. Bounded avatar image preparation/upload runs on IO and only
loads public avatar URLs from the configured backend's profile-images path, without redirects.

Independent debug property `-PprofileAccounts=true`, default/release false. The phone pilot also
enables the four approved character properties. OFF keeps guest preferences and hides misleading
Edit/Logout actions. The standard app-debug.apk build output ends OFF. No recognition/perception,
model, camera, schema-3.0 feature math, train/serve, sign-planner/player or GLB payload edits.

## Validation

- Pilot ON and ordinary OFF: 124 JVM tests each, zero failures/errors; 19 new account cases cover
  login, unchecked/remembered persistence, password whitespace, confirmation, rotated refresh,
  concurrent operations, unauthorized retry, invalid/offline sessions, inline metadata saving,
  logout, secure-storage failure, validation and failed/oversized avatars.
- Eight existing deterministic player tests pass.
- APK verification: one unchanged 27-animation shared GLB, seven replacements/20 added meanings,
  original102 exact in both APKs; default excludes all pilot payload. All234 asset entries exactly
  equal the prior approved selector APK. No new character conversion or semantic mapping.
- Static/profile resource checks: user card before preferences, read-only email, auth hidden
  initially, password view-state saving disabled, session excluded from cloud and device transfer.
- Reference mascot copied exactly (286112 bytes); reference files were not modified.
- Physical synthetic security/layout and actual catalog/preference tests: 5/5 PASS on M2101K7AG
  Android12, 1.47s. Pilot installed with -r and data retained; test companion removed afterward.
  The app was relaunched through exported SplashActivity; no scoped AndroidRuntime errors observed.
  User confirmed the section order and Login/Register design look correct, including returning
  to guest. Live account behavior remains pending. These tests never contact
  Supabase or create real accounts, and use separate synthetic preferences/Keystore alias.

Pilot/rollback APKs and machine-readable reports: `artifacts/profile_accounts_20260928/`.
Pilot SHA256: `4d93ab216fec41e4139c649204337af73ee4c69aef65d10099fc1745e54bc1fe`.
Ordinary rollback SHA256: `32b6dd0be2be99790a30631f2c4a9ac73df6aea182b2b66b7754a697ed82323c`.
Both APKs 322.82 MiB (incremental packaging retains padding; central-directory inspection verifies
default pilot exclusion). Previous selector APK is retained as `previous-character-choice.apk`.
Install with `adb install -r` to preserve the approved local character preference.

## Review — project /review workflow

Plan alignment PASS for the implemented reference UI/account client; system integrity PASS:
optional account IO is outside recognition, no new dependency or feature-vector contract. Offline
readiness PASS; production readiness CONDITIONAL/PENDING. Critical implementation issues: 0.
Important gates: 2 — (1) live Auth/storage policy/public avatar delivery,
(2) signed-in phone account/lifecycle acceptance. User passed guest/auth visual acceptance.
Minor release item: orphan avatar objects
can remain when an upload succeeds but the subsequent metadata update fails; backend cleanup policy
is not defined locally. Recommendation: flagged UI pilot only; keep production/default/release OFF
until live gates pass. Existing broad recognition F22/performance gates are not claimed passed.

## Backend boundary and next verification

Initial configured-backend probes were unreachable; user chose to check/reactivate the project.
Final unsandboxed read-only probe: DNS resolves, Auth settings HTTP200, email login enabled,
signup enabled and email auto-confirm currently true (configuration not changed by the agent).
Users select=id,email,username,full_name,avatar_url&limit=0 HTTP200 verifies column availability
only, not RLS or any user data. Anonymous profile-images bucket lookup HTTP400 is inconclusive;
authenticated policy/upload/public delivery still needs checking. Current client key was verified
as public anon (value never printed). No backend mutation was made by the agent.
User explicitly deferred live login/Save/Cancel/reopen testing until later. Keep pilot/default
state as installed and do not treat visual acceptance as live account acceptance.
Do not confuse a compiling client or synthetic security tests with live account validation.

When reachable: user logs in with an existing account on the phone, edits/saves/cancels the existing
fields, verifies restart with Remember me and memory-only behavior unchecked, uploads an avatar,
logs out/relogs in, and checks Original/New character playback. Registration can be checked using
the user's intended account; never request credentials in chat or create arbitrary accounts.
Verify profile-images insert policy is scoped to auth.uid(), bucket delivery matches public URL,
and confirmation-email verification works. No admin/table-policy changes are currently authorized.

Protocol sources: [Supabase Auth REST specification](https://github.com/supabase/auth/blob/master/openapi.yaml),
[sessions](https://supabase.com/docs/guides/auth/sessions),
[profile metadata](https://supabase.com/docs/guides/auth/managing-user-data),
[Android Keystore](https://developer.android.com/privacy-and-security/keystore).
