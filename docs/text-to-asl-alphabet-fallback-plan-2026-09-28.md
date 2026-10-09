# Text-to-ASL complete alphabet fallback plan

Status: approved by user on 2026-09-29; implementation is tracked separately in the results report.

## Overview and terms

This is native Android Text-to-ASL planning and asset stabilization (T1/T8), not the S0–S8 recognition pipeline. A **known sign** is a whole-word or phrase catalog match at word boundaries. **Fingerspelling** means playing one dedicated letter animation for each normalized A–Z character of an unknown word. **Complete fallback** means the entire unknown word is spelled in order; playing only available letters is a failure. **Original/New** are the existing Profile character choices, not separate vocabularies promised to have identical coverage.

## Inspection result

The current planner checks aliases and then consumes an unmatched input one character at a time. It only has A and B letter entries. For example, `cat` currently queues A while C and T are reported unsupported; `zzz` queues nothing. This is not full-word fingerspelling. Suffixes of an unmatched token can also become a catalog match during character consumption. The original 102-entry catalog has no C–Z letter clips. The New catalog overlays A/B and 20 new words but likewise has no C–Z letter entries. The alias `i` belongs to the existing I/Me pronoun sign and must remain that way for standalone `I`.

All 26 optimized A–Z files exist in the completed batch, totaling 308.16 MiB as individual GLBs. Read-only checks show that C–Z have one named letter animation each, 4,674 animation channels, 1,575 nodes, three skins with 341/875/342 joints, 12 meshes and eight textures. Their scene/skin/mesh/texture/sampler JSON matches A; only the already-known hair rest transform differs by source. This supports a shared-bundle experiment, but decoded geometry, textures, bind matrices and every animation track must still be verified before packaging. No phone performance or visual claim follows from this structural check.

## Recommended behavior and implementation

1. Keep longest whole-word/phrase matches at word boundaries, including existing Original signs inherited in the New catalog. With New selected, `hello` still plays the Original HELLO sign, as the user requested. If a token has no match anywhere in that selected catalog, plan the **entire token** as dedicated letters in order. Never use a word alias such as pronoun I to stand in for a letter inside an unknown word. Existing direct `I` still resolves to I/Me. Keep current normalization unless a separate product change is approved.
2. Resolve letters by `Type.LETTER` and an explicit letter identity, separate from the ordinary alias map, so letter I cannot collide with pronoun I. Keep current A/B letter signs and direct word/phrase aliases unchanged. If even one letter is unavailable, report the whole token unsupported rather than silently signing a partial word. Replay/Clear use the planned queue as today.
3. Append C–Z as exact animations to a **separate** derivative of the tested 27-sign-plus-idle shared GLB, only if decoded resource/rig equality and per-channel exactness pass. Preserve the existing 28 animations, idle, original 102 GLBs, all fallback paths and the installed APK as rollback. A raw 24-file addition would add roughly 285 MiB of duplicated character assets and is not appropriate for the phone pilot.
4. Add a distinct default-off alphabet flag and guarded manifest entries. The loader must reject wrong path/hash/profile/animation/letter identity and retain the prior catalog if the derivative is invalid. Keep the new bundle in the existing bounded two-viewer player; no new model viewer or runtime dependency.
5. Gate on 26-letter source hashes, exact decoded animation/rendering parity, glTF validation, APK contents, word/phrase and letter planner cases (including New `cat` → C-A-T, Original `cat` → unsupported whole token, New `hello` → Original HELLO, `I`, `I love you`, `be`, and mixed known/unknown input), full JVM/player tests, and a default-off APK. Then install the flagged pilot with data retained and test alphabet sequence, unknown words, known signs, Replay/Clear and Original/New switching on the attached phone. Measure cold load, warm letter transitions and app plus WebView memory; retain the current phone APK for immediate rollback.

## Character scope and decisions

The user confirmed that Original and New must each use their own vocabulary and letter assets; do not borrow New letters while Original is selected. The Original catalog has only A/B assets. Enable complete A–Z fingerspelling for **New** and report an entire unsupported word when Original cannot spell it until matching Original C–Z assets are available. Do not pretend that Original can spell every unknown word.

New currently inherits the 102 Original entries, so HELLO plays the Original sign even when New is selected. The user explicitly chose to keep that behavior for now. Only words without any available GLB in the selected catalog are fingerspelled by New letters. No old-only word filter or vocabulary removal is planned.

## Contract and gate

This changes only the Text-to-ASL presentation/catalog contract and planner. It does not change recognition `schema_version`, S4/F train/serve parity, or cross-signer recognition metrics. Record the alphabet manifest and fallback contract with `/imprint` after implementation and run `/review` before phone rollout. Production/default and release stay unchanged until physical performance and visual checks pass.
