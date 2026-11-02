# Connect two devices with a QR code (remoteConversation): concept and plan

Status: design only (2026-11-02). Nothing built. Needs the user's answers in section 9 before code.
Branch: `claude/conversation-flow-ux` (worktree `I:/AppHear-Conversation-Claude/worktree`).
It is an addition: existing screens keep working unchanged when the flag is off.

## 1. What exists today (checked in code)

| Area | Today | Consequence |
|---|---|---|
| Backend | Supabase project used for auth + `profile-images` storage, called with plain `HttpURLConnection` (`SupabaseAccountApi`, `AccountRepository`, encrypted session store) | Reuse the same project. No new vendor. |
| Real-time | Nothing (no WebSocket client, no push) | One new transport is needed. |
| Deep links | None. Only `SplashActivity` is exported (launcher) | Add one link entry point. |
| QR | No QR library | Add encode-only QR generation. Scanning is done by the phone's own camera app. |
| Text-to-ASL | `TextToAslFragment` (input + avatar), `TextToAslPlaybackController` (WebView/GLB), and `ReplyAvatarStage` (plays text with tickets, loading state, unsupported words) | The viewer screen reuses `ReplyAvatarStage`/the playback controller as is. No new avatar code. |
| Distribution | Class project; the APK is side-loaded, not on Play | Play Install Referrer (join automatically after install) does not work for side-loaded APKs. A join code is the realistic fallback. |

## 2. The idea, expanded

Two roles:
- **Host (User A)** types (or speaks, through the existing listening) on their phone.
- **Viewer (User B)** sees each message as large text and the 3D avatar signing it. The viewer
  screen shows only Text-to-ASL: no camera, no recognition.

Use cases: a hearing person at a counter (pharmacy, class, front desk) talks to a Deaf visitor
who holds their own phone at a comfortable distance; a teacher sends sentences to a student.

Optional, off by default (proposed, not required): the viewer can send a short typed reply or a
quick "Repeat / Slower / Got it" reaction, shown on the host screen. This keeps the conversation
two-way without adding recognition to the viewer.

## 3. User journey

1. **Start (Host)**: Home -> **Connect a device**. The app creates a session and shows a QR code,
   a 6-character join code (e.g. `K7P-4QM`) and "Waiting for someone to join..." (same sheet,
   pills and fonts as today). The code is valid for 10 minutes and for one viewer.
2. **Scan (Viewer)**: the viewer points their phone camera at the QR. It contains a link such as
   `https://<domain>/j/K7P4QM#<secret>`.
   - **AppHear installed**: Android opens AppHear directly on "Join conversation with <host name>?"
     -> **JOIN**.
   - **Not installed**: the link opens a small web page: "Get AppHear" (install link) and the join
     code in large letters. After installing, the viewer opens AppHear and taps **Join with a code**
     (code pre-explained on the page). Automatic join after install needs Play distribution; it
     can be added later (section 7).
3. **Connected**: both phones show "Connected". The host's QR disappears. Host types in the
   existing text field -> **SEND**. The viewer sees the text, then the avatar signs it. REPLAY
   replays; older messages stay in a scrollable list (the existing history bubbles).
4. **During**: typing indicator on the viewer ("<host> is typing..."). Delivered/seen ticks on the
   host. Messages arrive in order, exactly once.
5. **Reconnect**: if either phone loses the network or the app goes to the background, it
   rejoins the same session automatically when it comes back and fetches missed messages.
   The other side sees "Reconnecting..." then "Connected".
6. **End**: either side taps **END**. Both phones show "Conversation ended". The session cannot be
   rejoined. Messages are deleted from the server (section 6).

## 4. Edge cases

| Case | Behaviour |
|---|---|
| QR expired (10 min) or already used | Viewer: "This invite has expired. Ask for a new code." Host: **NEW CODE**. |
| Wrong join code | "Code not found." After 5 wrong tries from one device: wait 1 minute (server-side limit). |
| Third person scans the same QR | Refused: one viewer per session. |
| Poor connectivity | Outgoing messages queue locally with "Sending..."; retried with backoff; same message id, so no duplicates. |
| Viewer app closed/killed | Session stays open 30 min. Opening AppHear shows "Rejoin conversation?" and fetches missed messages. |
| Host app closed | Viewer: "Host is away" (presence). Host reopens -> session resumes. |
| Host gone for 30 min | Session ends automatically on the server; viewer shows "Conversation ended". |
| Message with words the avatar lacks | Text shows in full; avatar fingerspells or marks unsupported words, as Text-to-ASL does today. |
| Avatar still playing when the next message arrives | Messages queue; each plays in turn; the viewer can skip. |
| Phone rotated / screen locked | State kept; playback resumes on return. |
| Both phones offline at start | "No internet connection. Connect to Wi-Fi or mobile data." No offline pairing in v1 (section 7). |
| Server down | Same message as offline; nothing lost locally. |

## 5. Recommended stack

| Need | Choice | Why |
|---|---|---|
| Identity | Supabase **anonymous sign-in** for anyone not logged in; logged-in users use their account | No account needed to join. Every device still gets a real user id for access rules. |
| Session + invite | Two Postgres functions in the existing project: `create_conversation()` and `join_conversation(code, secret)` | Server decides validity. Invite secret is 128-bit random, stored hashed, single-use, 10 min expiry. |
| Messages (reliable) | Table `conversation_messages(id uuid, conversation_id, seq bigserial, sender, text, created_at)` with row-level security: only the 2 members can read/insert | Server-assigned `seq` gives order; client `id` gives exactly-once retries; missed messages = `seq > lastSeen`. |
| Live delivery | **Supabase Realtime** (WebSocket): database-change events for new messages, Presence for online/away, Broadcast for typing | Same project and auth token; no extra server to run. |
| WebSocket client | **OkHttp** (standard Android HTTP/WebSocket library) plus a small Realtime channel client (~200 lines, tested) | Smaller and fits the current hand-written `SupabaseAccountApi` style. Alternative: the `supabase-kt` SDK (adds Ktor + serialization; more features, larger). |
| QR image | ZXing `core` (encode only) | Small, offline, widely used. No camera code in the app. |
| Link into the app | Android App Link `https://<domain>/j/...` with `assetlinks.json`, plus a static landing page | Opens the app directly when installed; a web page when not. |
| Cleanup | `pg_cron` job: end sessions idle 30 min; delete messages of ended sessions after 24 h | Privacy by default. |

Security notes:
- The secret is in the URL fragment (`#...`), which browsers do not send to the web server.
- Rate limit join attempts on the server. No personal data in the URL.
- Messages are text only. No audio or video leaves the phone.
- Messages are encrypted in transit (TLS). Not end-to-end encrypted in v1; E2E can be added
  later with a key exchanged through the QR (section 7).
- Keys stay in the gitignored `gradle.properties`; the public repo gets only the SQL migration and code.

## 6. App changes (flag `remoteConversation`, debug-only, release hard-off)

- `conversation/remote/`: `RemoteSessionApi` (RPC + REST), `RealtimeClient` (OkHttp WebSocket),
  `RemoteConversation` (pure state machine: Idle, Inviting, Connected, Reconnecting, Ended;
  outgoing queue; dedupe by id; ordering by seq), `InviteLink` (build/parse/validate).
- Host screen: reuses the Text-to-ASL input and sheet styles; adds the QR card and status pill.
- Viewer screen: one new activity with the existing avatar stage, the reply text style and the
  history bubbles.
- Manifest: one exported `JoinActivity` with the App Link filter; `INTERNET` already present.
- Server: one SQL migration file (tables, RLS, functions, cron) under `supabase/migrations/`.
- Tests: host tests for the state machine, queue/retry/dedupe, invite parsing and expiry; an
  integration test against a local or test Supabase project.

## 7. Alternatives considered

- **Nearby Connections / Bluetooth / Wi-Fi Direct**: works offline and needs no server, but needs
  location/Bluetooth permissions, is slower to connect and fails across distances. Good later add-on
  for offline rooms.
- **Firebase (Firestore + Dynamic Links)**: Dynamic Links is shut down; Firestore would add a second
  backend next to Supabase.
- **Own WebSocket server**: more control, more to run and secure. Not needed at this size.
- **Automatic join after install**: Play Install Referrer once the app is on Google Play.
- **End-to-end encryption**: put a public key in the QR; encrypt message text on the phone.

## 8. Build steps (each verified before the next)

1. SQL migration + RLS tests against a test project.
2. `RemoteConversation` state machine + host tests.
3. Realtime client + session API; integration test with two test users.
4. Host screen (QR, code, status, send).
5. Viewer screen (text, avatar, history, reconnect).
6. App Link + landing page + join-by-code.
7. Two-phone checks: pairing, 50 messages in order, airplane mode for 1 min, kill and reopen,
   expired code, third scanner refused, END on each side.

## 9. Decisions needed from the user

1. Link domain for the QR and landing page (needs HTTPS hosting you control, e.g. GitHub Pages).
   Without it: QR holds the join code only (`apphear://join/...`), installed phones still open the
   app, others type the code.
2. Should the viewer be able to send short replies/reactions back (section 2)?
3. Must the host be logged in, or is anonymous use fine for both sides?
