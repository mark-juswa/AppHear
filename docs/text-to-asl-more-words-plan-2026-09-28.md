# Text-to-ASL word expansion plan

Status: user approved all 20 optimized word exports, including four explicit meaning phrases.

## Scope

Add 20 new Text-to-ASL input entries to the existing default-off shared-character pilot.
Keep the seven approved replacements, original 102 catalog entries and recognition vocabulary
unchanged. No S0–S8, feature-vector schema, model, training or camera change. “New word”
means a Text-to-ASL planner alias; it makes no recognition or semantic-accuracy claim.

Sixteen direct-label inputs: afternoon, any, ask, baby, bag, be, beautiful, become, begin,
boss, busy, bye, car, cold, come, fast. The source labels ASK and COME become their own
entries; existing REQUEST and COME TO HERE clips retain their own mappings.

Four explicit meaning inputs: **big horizontally** (source BIG_AS_IN_LARGE_OR_BIG_HORIZONTALLY),
**call by phone** (CALL_CALL_BY_PHONE), **call someones name** (CALL_TO_CALL_SOMEONE_S_NAME;
user may type “call someone’s name”, normalized by existing rules), and **pay me**
(PAY_TO_PAY_ME). Plain big, call and pay get no inferred mapping. No letter replacements are
included in this expansion.

## Evidence and approach

All 20 candidates are in the completed offline batch with exact decoded data/topology and
zero validator errors. A read-only decoded audit found their geometry, textures, skins and
hierarchy identical to the tested shared character. They each carry 4,674 channels. Original
source hashes and animation names/durations must be checked again during packaging.

Build a **separate 27-clip shared GLB** and manifest from the seven existing clips plus the
20 approved words, preserving every original animation accessor and source-specific hair
rest transform. Keep the phone-tested seven-clip source/output untouched. New debug property
`aslMoreWords=true` requires `aslSharedCharacter=true` and `aslAssetPilot=true`, selects a
separate package and is false by default/release. Existing seven-clip and separate-GLB pilot
remain rollbacks. Hash-check the bundle once on the IO dispatcher.

The expanded manifest uses schema 2: seven exact original overrides with their original
fallback paths, plus 20 new entries with approved aliases and no original counterpart.
When a new clip cannot load, show a per-clip failure and advance; existing entries still
retry their original asset. If the expanded package is missing/invalid, the app loads the
original catalog. No source raw GLBs are bundled for new words, avoiding a large APK.

## Gates

1. Offline compatibility and source/derived hashes, exact decoded 4,674 original channels
   per sign, hair resets, glTF structural validation and name/alias collision checks.
2. Deterministic unit tests for 20 new aliases, four explicit meanings, no plain-word
   remaps, original fallback and missing/corrupt bundle behavior. Existing player suite.
3. Build shared-expanded, seven-clip rollback and default-off; inspect APK contents/hashes,
   verify original 102 assets and recognition/model/config files unchanged.
4. Install only on connected phone with app data preserved. Compare cold load, transition
   p50/p95, paired app/WebView memory, completion/watchdog and controlled frame pacing.
   Human tests representative new words, repeats, Clear/navigation and visual meaning.
5. If the 27-clip bundle exceeds reasonable load/memory or signs render poorly, keep the
   seven-clip pilot installed and deliver the expanded APK as offline-only experimental.
   Do not activate default/release or claim phone validation without device evidence.

The phone was disconnected at plan time. Current seven-clip APK and G: delivery remain intact.
