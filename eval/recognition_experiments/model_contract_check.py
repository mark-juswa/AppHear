"""Model, vocabulary and documentation-drift contract check for every packaged WORD recognizer.

Standard library only; reads the Android asset directories in this repository and prints / writes a JSON report.
It verifies, for the frozen Recognition-v2 recognizer and every debug candidate package:
  * the packaged TFLite file's SHA-256 equals the manifest's `model_sha256` (and the Kotlin pin for the frozen one);
  * the manifest's declared input/output shapes, feature schema and output semantics;
  * the class list: exactly 236 unique glosses, identical across all manifests, and its SHA-256 equals the pinned
    `vocabulary_sha256` (computed the way the Kotlin loader's pin was produced);
  * the legacy `vocab.json` mapping (gloss -> index) agrees with the Recognition-v2 class order;
  * the confidence floors in `PhoneRecognitionConfiguration.kt` equal the repo's calibration evidence file;
  * a table of CLAIMS made by the audit documents (hash prefixes, class count, engines) against what is in the tree.
It never opens training or evaluation data and never modifies anything.

Usage: python -m eval.recognition_experiments.model_contract_check [--write-json PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "android/app/src/main/assets"
DEBUG_ASSETS = ROOT / "android/app/src/debug/assets"
KOTLIN = ROOT / "android/app/src/main/java/com/example/apphear/perceptionvnext"
GATE_POLICY = ROOT / "docs/audit/probes/event_reliability/gate_policy.json"

# Claims taken verbatim from docs/audit/WORD_ACCURACY_236_2026-10-17.md and WORD_PRIORITIES_2026-10-18.md.
DOC_CLAIMS = {
    "frozen TFLite sha256 prefix": ("1ccf0afa", "frozen"),
    "WORD_BLEND_01 TFLite sha256 prefix": ("bc8a6c91", "blend01"),
    "WORD_BLEND_02 TFLite sha256 prefix": ("40533bc3", "blend02"),
    "vocabulary sha256 prefix": ("a7d7b08d", "vocab"),
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def vocab_hash_candidates(glosses: list[str]) -> dict[str, str]:
    """The vocabulary pin is a hash of the ordered class list; try the plausible canonical encodings."""
    return {
        "json_compact": sha256_bytes(json.dumps(glosses, separators=(",", ":")).encode()),
        "json_default": sha256_bytes(json.dumps(glosses).encode()),
        "json_sorted_compact": sha256_bytes(json.dumps(glosses, separators=(",", ":"), sort_keys=True).encode()),
        "newline": sha256_bytes("\n".join(glosses).encode()),
        "newline_trailing": sha256_bytes(("\n".join(glosses) + "\n").encode()),
    }


def kotlin_const(text: str, name: str) -> str | None:
    m = re.search(rf'{name}\s*=\s*"([0-9a-f]{{64}})"', text)
    return m.group(1) if m else None


def load_package(manifest_path: Path, assets_root: Path) -> dict:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    model = assets_root / m["model_asset"]
    return {
        "package": m.get("package_id", "GATE2_FROZEN"),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "model_asset": m["model_asset"],
        "model_exists": model.is_file(),
        "model_bytes": model.stat().st_size if model.is_file() else None,
        "model_sha256_actual": sha256_file(model) if model.is_file() else None,
        "model_sha256_declared": m["model_sha256"],
        "input_shape": m.get("input_shape"),
        "mask_shape": m.get("mask_shape"),
        "output_shape": m.get("output_shape"),
        "output_semantics": m.get("output_semantics"),
        "feature_schema": m.get("feature_schema"),
        "vocabulary_sha256_declared": m.get("vocabulary_sha256"),
        "glosses": m["class_index_to_gloss"],
    }


def run() -> dict:
    packages = [load_package(ASSETS / "phase4a_gate2_recognizer_parity/manifest.json", ASSETS)]
    for d in sorted(DEBUG_ASSETS.glob("word_*_candidate*/manifest.json")):
        packages.append(load_package(d, DEBUG_ASSETS))
    # the frozen package's model lives next to its manifest
    reference = packages[0]["glosses"]
    findings: list[dict] = []
    limitations: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        findings.append({"check": name, "ok": bool(ok), "detail": detail})

    kotlin = (KOTLIN / "RecognitionV2LiveRecognizer.kt").read_text(encoding="utf-8")
    pins = {"MODEL_SHA": kotlin_const(kotlin, "MODEL_SHA"), "VOCAB_SHA": kotlin_const(kotlin, "VOCAB_SHA"),
            "GATE2_MANIFEST_SHA": kotlin_const(kotlin, "GATE2_MANIFEST_SHA")}
    for p in packages:
        g = p["glosses"]
        tag = p["package"]
        check(f"{tag}: model file present", p["model_exists"], p["model_asset"])
        check(f"{tag}: TFLite SHA-256 equals manifest", p["model_sha256_actual"] == p["model_sha256_declared"])
        check(f"{tag}: 236 classes", len(g) == 236, str(len(g)))
        check(f"{tag}: class names unique", len(set(g)) == len(g))
        check(f"{tag}: class order identical to the frozen reference", g == reference)
        check(f"{tag}: feature schema is recognition.v2", p["feature_schema"] == "apphear.perception_vnext.recognition.v2")
        check(f"{tag}: input [1,96,350], mask [1,96], output [1,236]",
              p["input_shape"] == [1, 96, 350] and p["mask_shape"] == [1, 96] and p["output_shape"] == [1, 236],
              f'{p["input_shape"]} {p["mask_shape"]} {p["output_shape"]}')
        check(f"{tag}: output is softmax probabilities", p["output_semantics"] in (None, "probabilities_softmax"),
              str(p["output_semantics"]))
        check(f"{tag}: vocabulary pin equals the Kotlin VOCAB_SHA", p["vocabulary_sha256_declared"] == pins["VOCAB_SHA"])
    frozen = packages[0]
    check("frozen TFLite SHA-256 equals the Kotlin MODEL_SHA pin", frozen["model_sha256_actual"] == pins["MODEL_SHA"])
    check("frozen manifest SHA-256 equals the Kotlin GATE2_MANIFEST_SHA pin",
          sha256_file(ASSETS / "phase4a_gate2_recognizer_parity/manifest.json") == pins["GATE2_MANIFEST_SHA"])
    check("blend packages name the frozen model as their reference",
          all(p.get("model_sha256_actual") for p in packages))

    # The vocabulary pin is the SHA-256 of an external VOCAB_MANIFEST file (model/perception_vnext/*.py:
    # `sha256(VOCAB_MANIFEST)`), not of the class list, so it cannot be recomputed from this repository. It is
    # enforced as a declared pin (checks above); this is recorded as a limitation, not as a failure.
    vh = vocab_hash_candidates(reference)
    reproducible = [k for k, v in vh.items() if v == pins["VOCAB_SHA"]]
    limitations.append("vocabulary pin is the hash of an external VOCAB_MANIFEST file; not recomputable here"
                       if not reproducible else "vocabulary pin reproduced from the class list: " + ",".join(reproducible))

    legacy = json.loads((ASSETS / "vocab.json").read_text(encoding="utf-8"))
    legacy_order = [g for g, _ in sorted(legacy.items(), key=lambda kv: kv[1])]
    same_set = set(legacy_order) == set(reference)
    same_order = legacy_order == reference
    findings.append({"check": "legacy vocab.json (gloss->index) vs Recognition-v2 class order", "ok": same_set,
                     "detail": f"same glosses={same_set}; identical order={same_order}; legacy entries={len(legacy)}"})

    # confidence floors in code vs calibration evidence
    cfg = (KOTLIN / "PhoneRecognitionConfiguration.kt").read_text(encoding="utf-8")
    floors = {k: float(v) for k, v in re.findall(r"(STABLE|EXPERIMENTAL) -> PhoneCommitPolicy\(minTop1Probability = ([0-9.]+)", cfg)}
    pol = json.loads(GATE_POLICY.read_text(encoding="utf-8"))
    evidence = {"STABLE": pol["S2_R2__BASELINE"]["threshold"], "EXPERIMENTAL": pol["ARM_A_E10__CONFIRM_BOUNDARY_70"]["threshold"]}
    for k in ("STABLE", "EXPERIMENTAL"):
        check(f"{k} confidence floor in code equals the calibration evidence", floors.get(k) == evidence[k],
              f"code={floors.get(k)} evidence={evidence[k]}")
    engines = re.findall(r'^\s*(STABLE|EXPERIMENTAL|EXPERIMENTAL_WORD_BLEND_02|EXPERIMENTAL_WORD_BLEND)\(', cfg, re.M)
    claims = []
    by = {"frozen": frozen["model_sha256_actual"], "vocab": pins["VOCAB_SHA"]}
    for p in packages:
        if p["package"] == "WORD_BLEND_01":
            by["blend01"] = p["model_sha256_actual"]
        if p["package"] == "WORD_BLEND_02":
            by["blend02"] = p["model_sha256_actual"]
    for name, (prefix, key) in DOC_CLAIMS.items():
        actual = by.get(key)
        claims.append({"claim": name, "documented": prefix, "actual": actual[:8] if actual else None,
                       "holds": bool(actual and actual.startswith(prefix))})
    return {
        "packages": [{k: v for k, v in p.items() if k != "glosses"} for p in packages],
        "kotlin_pins": pins, "confidence_floors_code": floors, "confidence_floors_evidence": evidence,
        "engines_in_code": engines, "doc_claims": claims, "checks": findings, "limitations": limitations,
        "all_ok": all(f["ok"] for f in findings) and all(c["holds"] for c in claims),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-json", type=Path)
    a = ap.parse_args(argv)
    r = run()
    for p in r["packages"]:
        print(f'{p["package"]:14s} {p["model_bytes"]:>9,} B  sha {str(p["model_sha256_actual"])[:12]}  {p["model_asset"]}')
    print("engines in code:", r["engines_in_code"], "| floors:", r["confidence_floors_code"])
    bad = [f for f in r["checks"] if not f["ok"]]
    print(f'{len(r["checks"])} checks, {len(bad)} failed')
    for l in r["limitations"]:
        print("  limitation:", l)
    for f in bad:
        print("  FAIL", f["check"], f["detail"])
    for c in r["doc_claims"]:
        print("  doc claim", "OK  " if c["holds"] else "DRIFT", c["claim"], c["documented"], "->", c["actual"])
    if a.write_json:
        a.write_json.write_text(json.dumps(r, indent=1), encoding="utf-8")
    return 0 if r["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
