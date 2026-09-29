# Established account-flow restoration — approved 2026-09-28

Layout correction is explicitly requested: Your Profile heading, AppHear user card, then
Preference / Your Setting and its functional rows. Remove the previous runtime reordering.
Character selection remains on Profile beneath the user section, without an Edit prerequisite.

The initial separate-screen proposal is withdrawn after user direction to inspect the established
UI first. Inspected context/design/settigns.jpg, settings_preference.jpg and read-only reference
AppHear2 activity_profile.xml / ProfileActivity.java. The reference edits inline in the same card:
full name and username become enabled; email remains disabled; EDIT PROFILE changes to SAVE PROFILE.
Avatar picking is part of the edit flow. No separate profile-editor destination exists there.
Reference account saves and avatar upload require Supabase sign-in, absent in AppHear3 at inspection.

User confirmed: “Restore the established account flow.”
Do not invent a new editor, treat email as locally editable, imply verified sign-in, or copy the
old backend/session code without checking its contract. The user card must remain above preferences
as requested regardless of this choice. Character preference remains directly below the user card.

Add an independent default-off profileAccounts debug flag. Test pilot enables it together
with existing character flags. Ordinary/release retain guest settings access with account actions
hidden; no Edit button should navigate to Preferences. Recognition and asset
payload stay unchanged. No feature-vector schema or train/serve change.

This is native migration Phase 7 account integration using existing Kotlin/XML and platform HTTPS
and JSON APIs, with no new SDK. Restore reference Login/Register tabs, email/password, registration
username/confirmation, Remember me and Logout. The guest card remains visible above preferences;
its action opens the established auth panel. Signed-in edits use the existing card inline.

Auth REST contract: password login, signup, refresh, GET/PUT user and local-scope logout. Identity
comes from the authenticated Auth user; username/full_name/avatar_url use the same user_metadata
keys as the reference. Metadata is display data, never authorization. Do not introduce writes to
the undocumented public users table or assume its RLS. Existing reference saves already populate
Auth metadata. Avatar uploads use profile-images and user-ID-scoped random JPEG paths. Policy
denials keep the draft and report a safe error; storage policy/public delivery remains a live gate.

Remember me stores encrypted sessions with Android Keystore AES/GCM, bound to backend URL and
excluded from cloud/device backup. Unchecked sessions stay in memory. Never persist passwords,
print tokens or expose backend responses. Serialize restore/refresh/save/logout, refresh rotated
tokens on expiry/401, clear invalid sessions and preserve cached identity during network failures.
Email confirmation is a normal signup outcome; do not disable it or retry blind login. Logout
revokes only this session, clears local state even offline, and explains incomplete server revocation.

Current BuildConfig contains a configured HTTPS address but DNS fails on this host, including
unsandboxed read-only probes. Auth settings, zero-row profile-column and bucket checks could not
reach the server. No account/data mutation was made. User will check/reactivate the existing project.

Offline gate: fake-API tests for confirmation/login/refresh/401/offline/logout/storage failures and
validation, ON/OFF compile/full JVM regression, player tests and asset parity. Synthetic Keystore
round-trip instrumentation only. Device gate: layout, login, inline save/cancel/avatar, remembered
and unchecked restart, Logout/relogin, character preference regression. Live tests require reachable
backend and user interaction; do not create artificial accounts or request credentials in chat.
Install with -r after offline checks, retain previous selector APK rollback; imprint/review/remember.
No recognition, feature-vector/parity, model, camera or sign payload changes.

Official sources: https://github.com/supabase/auth/blob/master/openapi.yaml,
https://supabase.com/docs/guides/auth/sessions,
https://supabase.com/docs/guides/auth/managing-user-data,
https://developer.android.com/privacy-and-security/keystore.

Completion update: pilot installed, ON/OFF124 JVM and five isolated phone tests pass; user confirms
correct section order and established Login/Register UI. Backend now resolves and Auth settings
respond200; authenticated avatar policy remains unverified. User elected to test live account
actions later. See profile-account-restoration-results-2026-09-28.md for the current state.
