# 04 — Confirmation & Sentence Builder

*Deliverable §8.4: specify the confirmation + sentence-builder design so the
[lesson e](docs/05-v2-lessons-map.md) leak cannot recur.*

---

## The failure we are designing against (lesson e)

On cross-signer data, **v2's confirmation policy dropped ~50% of *correct* signs as "none"**
(~42% confirmed / ~50% silently dropped). The recognizer was not the bottleneck — the commit
policy was. Root causes, and the design responses:

| Root cause in v2 | Response in AppHear 3 |
|------------------|-----------------------|
| A single conservative confidence threshold | Evidence *accumulation* + a **tuned operating point**, not one constant |
| Threshold picked on training-signer data | Operating point fit on **held-out signers** with its own eval |
| Posteriors miscalibrated cross-signer (overconfident on train, underconfident on new signers → dropped) | **Temperature-scaling calibration** on held-out signers |
| One-frame argmax discarded temporal evidence | Accumulate over the sign's frames before committing |
| "Dropped as none" was invisible | The drop rate of *correct* signs is a **first-class tracked metric** |

**Guiding principle:** confirmation is a component with inputs, outputs, a metric, and an
offline eval — **not an afterthought threshold.**

---

## S7 — Confirmation design

### Input
Time-indexed, **calibrated** per-class posteriors from [S6](docs/01-system-architecture.md)
(including the blank / no-sign class once on the CTC path).

### Calibration (prerequisite, do this first)
Fit a single **temperature `T`** (and optionally per-class bias) by minimizing NLL on the
**held-out-signer** validation set. Miscalibration is a large part of why v2 dropped correct
signs; an uncalibrated posterior makes any threshold meaningless. Calibration is re-fit
whenever the model changes and is itself reported (reliability diagram / ECE).

### Evidence accumulation (instead of one-frame argmax)
Maintain a running **log-posterior accumulator** over the active span:
```
A_c ← Σ_t  log p_calibrated(c | frame_t)     over the current sign's frames
```
Track the top-1 class `c*` and runner-up `c₂` of `A`.

### Commit gate (all must hold → commit `c*`)
1. **Evidence:** `A_{c*}` exceeds the operating-point threshold `θ_commit`.
2. **Margin (FP guard):** `A_{c*} − A_{c₂} ≥ θ_margin` — top-1 must beat the runner-up, not
   just cross an absolute bar. This is the primary false-positive guard.
3. **Stability:** `c*` has been the top class for `≥ k` consecutive frames — kills
   single-frame spikes.
4. **Phase sanity:** commit is allowed around the **hold/release** phase from
   [S5](docs/01-system-architecture.md), not mid-onset — prevents premature commits on the
   entry transition.

If the gate isn't met by release, the decision is **"wait for more evidence"** — but the
accumulator's state is *logged*, so a would-have-been-correct-but-dropped sign is visible in
telemetry (directly measuring the v2 leak) instead of silently vanishing.

### The three tunables and how they're set
`θ_commit`, `θ_margin`, `k` are **not** hand-picked. They are chosen by sweeping the
operating curve on held-out signers (below) and picking the point that meets the target
false-positive rate. Exposed as `confirm.operating_point` for A/B rollout.

### CTC-path variant (Phase 2)
On the CTC path the blank symbol supplies "no sign" natively. Confirmation becomes: detect a
**posterior peak** for a non-blank gloss, apply the same margin + stability gates against
blank and the runner-up gloss, and commit. Same policy, cleaner substrate — which is why the
encoder was designed blank-aware from Phase 0 ([doc 03](docs/03-model-architecture.md)).

### Metric & offline eval (this is what makes the leak un-repeatable)
On **held-out signers**, produce the operating curve:
- **x-axis:** false-positive commit rate (wrong or spurious commits per unit time),
- **y-axis:** **correct-commit rate** = fraction of true signs correctly committed,
- and explicitly report the **"correct-but-dropped" rate** — the v2 failure — as its own
  number at each operating point.

The chosen operating point is whatever **maximizes correct-commit rate at the target FP
rate.** v2 sat at ~42% correct-commit because nobody drew this curve; drawing it, on
held-out signers, is the fix.

---

## S8 — Sentence Builder

### Responsibility
Turn the stream of committed glosses into fluent, ordered, de-duplicated output. **This
stage owns the top-line system metric.**

### Input / Output
Committed gloss token stream (with timestamps) → human-readable phrase / sentence.

### Modes (`sentence.mode`, increasing capability)
1. **Raw passthrough** — emit glosses in commit order. The measurement baseline; always
   available as fallback.
2. **Smoothing / de-duplication** — collapse the same gloss committed twice by a lingering
   hold; drop stray singletons that violate temporal spacing (a new sign can't legitimately
   arrive faster than ~400 ms in fluent signing, anchor #2 — so sub-threshold repeats are
   duplicates, not new signs). Enforce minimum inter-gloss spacing from the timing budget.
3. **LM-assisted gloss→text** — a **small on-device n-gram / lightweight LM** over the gloss
   vocabulary that (a) reorders ASL gloss toward fluent target-language word order and
   (b) supplies function words ASL omits. Shared with the Phase-2 CTC beam decoder so the
   same language prior helps recognition and generation.

### Constraint: no cloud in the critical path (§7)
The LM is on-device (small n-gram or a tiny quantized model). A larger cloud LM may be
offered as an **optional, off-critical-path** post-editor for a finished sentence, never
inline — and behind a flag, opt-in, since it breaks the on-device guarantee.

### Metric (top-line)
**End-to-end phrase-level accuracy on held-out signers** signing real phrases —
gloss/word error rate (WER-style). Per [lesson f](docs/05-v2-lessons-map.md), this
end-to-end number is the one reported; per-window recognition accuracy is diagnostic only.

### Tradeoff
More aggressive LM rewriting improves fluency but can *hallucinate* — inserting words the
signer never signed, which for an accessibility tool is a trust failure worse than a clumsy
literal gloss. So modes are staged: literal-but-faithful is the default; LM rewriting is
opt-in and evaluated for **insertion rate**, not just fluency.
