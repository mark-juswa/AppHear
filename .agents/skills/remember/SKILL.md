---
name: remember
description: Save what matters at the end of an AppHear 3 session so the next session picks up exactly where you left off, or restore that context at the start of a new session. Keeps continuity without re-explaining. Never stores secrets.
---

AI has no memory between sessions — each starts blank. This skill persists and restores the
session state that isn't already obvious from the code, keeping AppHear 3 continuous.

Two modes: `/remember save` (session end) and `/remember restore` (session start).

## Security boundary (both modes)

Never store credentials, API keys, tokens, passwords, connection strings, cookies, or any
secret-looking value. If unsure whether something is sensitive, omit or redact it.

## Save mode — `/remember save`

Capture what the next session needs and cannot infer from the repo:
- **What was built** — exact files/features/stages completed.
- **Decisions made** — architectural/eval choices locked in (also mirror these into
  `context/progress-tracker.md` § Decisions Made).
- **Problems solved** — issues resolved, so they aren't re-litigated.
- **Current state** — what works, what's partial, what's broken (be exact).
- **Next session starts with** — one concrete, ready-to-start action.
- **Open questions** — unresolved items (mirror into progress-tracker Open items).

Exclude anything visible in the code, already in the `context/` files, or in `docs/`.

Write to `memory.md` in the project root using the format below. Then **also update
`context/progress-tracker.md`** (status line + feature checkboxes) so the two stay in sync. Do
a final sensitive-content check before writing. If `memory.md` exists, confirm before
overwriting.

```markdown
# Memory — [Feature or Session Name]

Last updated: [date and time]

## What was built
[Specific files, stages, features]

## Decisions made
[Architectural / eval choices locked in]

## Problems solved
[Issues resolved this session]

## Current state
[Exact status — working, partial, broken]

## Next session starts with
[First actionable task]

## Open questions
[Unresolved items]
```

## Restore mode — `/remember restore`

1. Read `memory.md` in the project root (if present).
2. Read `context/progress-tracker.md` (authoritative status + decisions) and follow the
   `AGENTS.md` reading order for the rest of the context.
3. Summarize where things stand — what's done, what's next, open questions — without echoing
   any secret-looking value.
4. Confirm with the developer before proceeding to build.

## Principle

Every session ends with `/remember save`; every session starts with `/remember restore`.
`context/progress-tracker.md` is the durable record; `memory.md` is the session handoff.
Consistent use is what makes continuity work.
