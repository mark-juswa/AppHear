# Frozen continuous fingerspelling package

Byte-identical runtime and parity files from the reviewed October 9 application.
Runtime: V2.1 epoch034 geometry-only, Adapter v1 (405 features), FP32.
The continuous held-letter path uses the exact singleton CTC decoder and frozen
stabilization policy. Prefix beam width10 / blank penalty0.5 remains the bounded
sequence reference. No visual residual is attached.

`android_assets` contains the model, manifest and continuous policy.
`parity_assets` contains synthetic/governed reference fixtures for instrumented
parity tests, not camera recordings or TEST payload. Hashes are in
`package_inventory.json`. Do not replace these files for a new experiment;
create a separate package identity instead.

Build using `tools/android/build_working_baseline.ps1` from the repository root.
Service credentials and Android SDK configuration are supplied locally and are
not part of this package. Private credential-bearing APKs must not be published.
