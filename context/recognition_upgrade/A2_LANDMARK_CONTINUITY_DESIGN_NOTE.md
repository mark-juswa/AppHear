# A2 Landmark Continuity — Design Note Only

**Status:** SUPERSEDED AFTER A1 DECISION

The A1 device and signing decisions are now complete. The active A2-0/A2-1 offline contract,
evidence inventory, frozen gates, and human-review handoff are in
`context/recognition_upgrade/A2_IDENTITY_EXPERIMENT.md`. This note remains as the pre-A1 historical
design boundary only.

If A1 is rejected or retained without solving perception dropout, A2's distinct hypothesis is a
short-gap continuity layer over actual 21-landmark hand tracks with temporal anatomical identity.
Every emitted hand state must carry:

- provenance: `DIRECT` or `RECOVERED`;
- recovery age;
- stable anatomical track ID (`LEFT`/`RIGHT` semantics defined independently of screen side);
- bounded expiry and explicit missing state.

A2 must not reuse ROI hold, pose-ROI recovery, MediaPipe VIDEO mode, or optical-flow ROI tracking.
It was not allowed to begin until A1 was classified from the frozen Baseline-vs-A1 device
benchmark. No Android A2 runtime, schema, model, threshold, or training change exists; the current
A2-1 work is an isolated offline identity experiment.
