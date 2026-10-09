"""Prepare the P5-D6 metadata-only human Sem-Lex review package."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
D5 = BASE / "p5d5_semlex_form_review_01"
OUT = BASE / "p5d6_semlex_human_review_01"
POST_REVIEW = ROOT / "model/p5d6_apply_human_semlex_review.py"
PROGRESS = ROOT / "context/progress-tracker.md"
PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
REVIEW_STATES = {"REVIEW_COMPATIBLE_VARIANT", "REVIEW_FORM_REQUIRED"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, data: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(data[0]) if data else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_d5() -> int:
    manifest = json.loads((D5 / "artifact_hash_manifest.json").read_text(encoding="utf-8"))
    checked = 0
    for item in manifest["artifacts"]:
        path = ROOT / item["path"] if item.get("role") == "supporting_code" else D5 / item["path"]
        if sha256(path) != item["sha256"]:
            raise RuntimeError(f"P5-D5 artifact hash mismatch: {path}")
        checked += 1
    if not json.loads((D5 / "p5d5_integrity.json").read_text(encoding="utf-8"))["passed"]:
        raise RuntimeError("P5-D5 integrity did not pass")
    return checked


def ref_strength(record: dict[str, str]) -> int:
    if record["signbank_reference_ids"] or record["asllvd_references"]:
        return 2
    if record["asllex_references"]:
        return 1
    return 0


def reason_flags(record: dict[str, str]) -> str:
    flags: list[str] = []
    if record["qualification_state"] == "REVIEW_FORM_REQUIRED":
        flags.extend(["SAME_ENGLISH_GLOSS_FORM_NOT_PROVEN", "SEMANTIC_SENSE_REQUIRES_CONFIRMATION", "ONE_VS_TWO_HANDED_FORM_REQUIRES_CONFIRMATION"])
    else:
        flags.append("POTENTIAL_LEXICAL_VARIANT")
        if "|" in record["semlex_lexical_ids"]:
            flags.append("MULTIPLE_LEXICAL_IDS_FOR_GLOSS")
        if "|" in record["asllvd_references"]:
            flags.append("ASLLVD_VARIANT_REFERENCE_EXISTS")
        flags.append("ONE_VS_TWO_HANDED_FORM_REQUIRES_CONFIRMATION")
    return "|".join(flags)


def safe(value: str) -> str:
    return value if value else "NOT_AVAILABLE"


def signbank_pages(ids: str) -> str:
    if not ids:
        return "NOT_AVAILABLE"
    return "https://aslsignbank.haskins.yale.edu/"


def build_viewer(decisions: list[dict[str, Any]]) -> None:
    payload = json.dumps(decisions, ensure_ascii=True).replace("</", "<\\/")
    document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AppHear P5-D6 Sem-Lex Review</title><style>
body{font:16px system-ui;margin:0;background:#f5f7fa;color:#17202a}.wrap{max-width:900px;margin:24px auto;padding:0 18px}.card{background:white;border:1px solid #ccd4dd;border-radius:12px;padding:24px;box-shadow:0 3px 12px #0001}dt{font-weight:700;margin-top:12px}dd{margin:3px 0 0}.choices{display:grid;gap:8px;margin:20px 0}.choices label{border:1px solid #ccd4dd;border-radius:8px;padding:10px}.controls,.reviewer-fields{display:flex;gap:8px;flex-wrap:wrap}.reviewer-fields label{flex:1;min-width:220px}button,input{padding:9px 12px}textarea{width:100%;min-height:70px}.warn{background:#fff4cc;padding:10px;border-radius:8px}.progress{margin-bottom:12px}a{color:#0757a5;word-break:break-all}
</style></head><body><div class="wrap"><h1>Sem-Lex Human Form Review</h1><p class="warn"><strong>English gloss equality is not sufficient.</strong> Decide whether the actual Sem-Lex lexical form belongs in the intended AppHear class. The canonical CSV remains the governed artifact.</p><div id="app"></div></div><script>
const items=__PAYLOAD__;const choices=['ACCEPT_EXACT_FORM','ACCEPT_COMPATIBLE_VARIANT','REJECT_FORM_MISMATCH','UNRESOLVED'];let i=0;const saved=JSON.parse(localStorage.getItem('p5d6-decisions')||'{}');
function esc(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}function links(s){return String(s||'').split('|').map(x=>x.startsWith('http')?`<a href="${esc(x)}" target="_blank">${esc(x)}</a>`:esc(x)).join('<br>')}
function save(){localStorage.setItem('p5d6-decisions',JSON.stringify(saved))}function render(){const x=items[i],s=saved[x.class_id]||{};document.getElementById('app').innerHTML=`<div class="progress">Item ${i+1} of ${items.length} · rank ${x.review_rank}</div><div class="card"><h2>${esc(x.canonical_gloss)}</h2><dl><dt>Deficit</dt><dd>${esc(x.coverage_deficit_level)}</dd><dt>Current coverage</dt><dd>${x.current_clips} clips · ${x.current_unique_signers} signers · effective ${x.current_effective_signers}</dd><dt>Sem-Lex</dt><dd>${esc(x.semlex_lexical_id)} · ${esc(x.semlex_gloss)} · ${x.semlex_candidate_train_clips} TRAIN clips · ${x.semlex_candidate_signers} signers</dd><dt>Reason</dt><dd>${esc(x.review_reason)}</dd><dt>ASL-LEX</dt><dd>${links(x.asllex_page)}</dd><dt>SignBank</dt><dd>${esc(x.signbank_reference)}<br>${links(x.signbank_page)}</dd><dt>ASLLVD</dt><dd>${esc(x.asllvd_reference)}<br>${links(x.asllvd_page)}</dd></dl><p><strong>Does the Sem-Lex lexical form represent the same AppHear sign class we intend the recognizer to learn?</strong></p><div class="choices">${choices.map(c=>`<label><input type="radio" name="d" value="${c}" ${s.decision===c?'checked':''}> ${c}</label>`).join('')}</div><label>Human notes<br><textarea id="notes">${esc(s.notes||'')}</textarea></label><div class="reviewer-fields"><label>Reviewer<br><input id="reviewer" value="${esc(s.reviewer||'')}"></label><label>Review date<br><input id="date" type="date" value="${esc(s.date||'')}"></label></div><div class="controls"><button id="prev">Previous</button><button id="next">Save & next</button><button id="export">Export completed canonical CSV</button></div></div>`;document.querySelectorAll('[name=d]').forEach(e=>e.onchange=store);document.getElementById('prev').onclick=()=>{store();i=Math.max(0,i-1);render()};document.getElementById('next').onclick=()=>{store();i=Math.min(items.length-1,i+1);render()};document.getElementById('export').onclick=exportCsv}
function store(){const x=items[i],d=document.querySelector('[name=d]:checked');saved[x.class_id]={decision:d?d.value:'',notes:document.getElementById('notes').value,reviewer:document.getElementById('reviewer').value,date:document.getElementById('date').value};save()}function q(v){return '"'+String(v??'').replaceAll('"','""')+'"'}function exportCsv(){store();const heads=['review_rank','class_id','canonical_gloss','coverage_deficit_level','semlex_lexical_id','semlex_gloss','semlex_candidate_train_clips','semlex_candidate_signers','asllex_reference','signbank_reference','asllvd_reference','other_authoritative_reference','review_reason','human_decision','human_notes','reviewer','review_date'];const lines=[heads.join(',')];for(const x of items){const s=saved[x.class_id]||{};const values=heads.map(h=>h==='human_decision'?(s.decision||''):h==='human_notes'?(s.notes||''):h==='reviewer'?(s.reviewer||''):h==='review_date'?(s.date||''):(x[h]??''));lines.push(values.map(q).join(','))}const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{type:'text/csv'}));a.download='semlex_human_decision_sheet_completed.csv';a.click();URL.revokeObjectURL(a.href)}render();
</script></body></html>""".replace("__PAYLOAD__", payload)
    (OUT / "semlex_review_viewer.html").write_text(document, encoding="utf-8")


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "review_batches").mkdir(parents=True, exist_ok=True)
    d5_checked = verify_d5()
    required_inputs = [
        "p5d5_target_70_classes.csv", "semlex_target_class_qualification.csv",
        "semlex_authoritative_lexical_evidence.csv", "semlex_human_review_queue.csv",
        "semlex_review_pending_projection.csv", "semlex_strict_coverage_projection.csv",
        "semlex_acquisition_value.json",
    ]
    source_before = {name: sha256(D5 / name) for name in required_inputs}
    source_before["progress_tracker"] = sha256(PROGRESS)
    if source_before["progress_tracker"] != PROGRESS_SHA:
        raise RuntimeError("progress-tracker governed hash mismatch")

    target = rows(D5 / "p5d5_target_70_classes.csv")
    qualification = rows(D5 / "semlex_target_class_qualification.csv")
    evidence = {int(r["apphear_class_id"]): r for r in rows(D5 / "semlex_authoritative_lexical_evidence.csv")}
    review = [r for r in qualification if r["qualification_state"] in REVIEW_STATES]
    exact = [r for r in qualification if r["qualification_state"] == "ACCEPT_METADATA_EXACT"]
    if len(target) != 70 or len(review) != 68 or len(exact) != 2:
        raise RuntimeError("P5D6_BLOCKED_REVIEW_QUEUE_MISMATCH")
    target_by_id = {int(r["class_id"]): r for r in target}

    review.sort(key=lambda r: (
        0 if r["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT" else 1,
        -int(r["semlex_train_unique_signers"]),
        float(target_by_id[int(r["apphear_class_id"])]["current_effective_signers"]),
        -ref_strength(r), int(r["apphear_class_id"]),
    ))
    order: list[dict[str, Any]] = []
    matrix: list[dict[str, Any]] = []
    readiness: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for rank, record in enumerate(review, 1):
        cid = int(record["apphear_class_id"])
        current = target_by_id[cid]
        evidence_row = evidence[cid]
        strength_value = ref_strength(record)
        ready = strength_value == 2
        partial = strength_value == 1
        metadata_only = strength_value == 0
        raw_required = not ready
        readiness_state = "AUTHORITATIVE_REFERENCE_READY" if ready else "PARTIAL_REFERENCE_EVIDENCE" if partial else "METADATA_ONLY_EVIDENCE"
        common = {
            "review_rank": rank, "class_id": cid, "canonical_gloss": record["apphear_gloss"],
            "coverage_deficit_level": record["coverage_deficit_level"],
            "current_clips": int(current["current_clips"]), "current_unique_signers": int(current["current_unique_signers"]),
            "current_effective_signers": float(current["current_effective_signers"]),
            "semlex_lexical_id": record["semlex_lexical_ids"], "semlex_gloss": record["semlex_glosses"],
            "semlex_candidate_train_clips": int(record["semlex_train_clip_count"]),
            "semlex_candidate_signers": int(record["semlex_train_unique_signers"]),
            "potential_signer_gain": int(record["semlex_train_unique_signers"]),
            "d5_qualification_state": record["qualification_state"],
        }
        order.append(common)
        flags = reason_flags(record)
        matrix.append({
            **common, "apphear_intended_lexical_label": record["apphear_gloss"],
            "semlex_supplied_lexical_ids": record["semlex_lexical_ids"],
            "asllex_reference": safe(record["asllex_references"]),
            "asllex_page": "https://asl-lex.org/visualization/" if record["asllex_references"] else "NOT_AVAILABLE",
            "signbank_reference": safe(record["signbank_reference_ids"]),
            "signbank_page": signbank_pages(record["signbank_reference_ids"]),
            "asllvd_reference": safe(record["asllvd_references"]),
            "asllvd_page": "https://www.bu.edu/asllrp/av/dai-asllvd.html" if record["asllvd_references"] else "NOT_AVAILABLE",
            "semlex_official_reference": "https://github.com/leekezar/SemLex",
            "previous_governed_human_review": safe(evidence_row["governed_human_review_evidence"]),
            "review_reason": flags, "readiness_state": readiness_state,
            "visual_confirmation_requires_raw_access": raw_required,
            "human_question": f"Does the Sem-Lex lexical form for '{record['semlex_lexical_ids']}' represent the same AppHear sign class intended by {record['apphear_gloss']}?",
        })
        readiness.append({
            "review_rank": rank, "class_id": cid, "canonical_gloss": record["apphear_gloss"],
            "readiness_state": readiness_state, "authoritative_reference_ready": ready,
            "partial_reference_evidence": partial, "metadata_only_evidence": metadata_only,
            "visual_confirmation_requires_raw_access": raw_required,
            "readiness_is_not_acceptance": True,
        })
        decisions.append({
            "review_rank": rank, "class_id": cid, "canonical_gloss": record["apphear_gloss"],
            "coverage_deficit_level": record["coverage_deficit_level"],
            "semlex_lexical_id": record["semlex_lexical_ids"], "semlex_gloss": record["semlex_glosses"],
            "semlex_candidate_train_clips": int(record["semlex_train_clip_count"]),
            "semlex_candidate_signers": int(record["semlex_train_unique_signers"]),
            "asllex_reference": safe(record["asllex_references"]),
            "signbank_reference": safe(record["signbank_reference_ids"]),
            "asllvd_reference": safe(record["asllvd_references"]),
            "other_authoritative_reference": "https://github.com/leekezar/SemLex",
            "review_reason": flags, "human_decision": "", "human_notes": "", "reviewer": "", "review_date": "",
        })
    write_csv(OUT / "p5d6_review_order.csv", order)
    write_csv(OUT / "semlex_review_evidence_matrix.csv", matrix)
    write_csv(OUT / "semlex_review_readiness.csv", readiness)
    write_csv(OUT / "semlex_human_decision_sheet.csv", decisions)

    guide = """# P5-D6 Human Sem-Lex Review Guide

For each row, answer one question:

> Does the Sem-Lex lexical form represent the same AppHear sign class we intend the recognizer to learn?

English gloss equality is **not sufficient**. `MOVE` matching `MOVE`, for example, does not prove that the lexical/sign form is compatible.

## Allowed decisions

- `ACCEPT_EXACT_FORM` — the same lexical sign form intended by AppHear.
- `ACCEPT_COMPATIBLE_VARIANT` — a legitimate ASL lexical variant that AppHear should intentionally recognize as the same application class. This **expands the class definition**.
- `REJECT_FORM_MISMATCH` — another form/sense, fingerspelling, incompatible compound, or unwanted variant.
- `UNRESOLVED` — available evidence is insufficient. Do not force a decision.

## Workflow

1. Follow the deterministic review rank or batches.
2. Inspect authoritative ASL-LEX, SignBank, and ASLLVD references where present.
3. Compare the intended AppHear form using project-owned human knowledge/reference material; do not use model predictions.
4. Fill only `human_decision`, `human_notes`, `reviewer`, and `review_date` in a **copy** of `semlex_human_decision_sheet.csv`.
5. Do not change identifiers, candidate counts, or review order.
6. If public references are insufficient, use `UNRESOLVED`; raw Sem-Lex access is not authorized by this package.

The HTML viewer is optional convenience. The CSV decision sheet is canonical.
"""
    (OUT / "P5D6_HUMAN_REVIEW_GUIDE.md").write_text(guide, encoding="utf-8")

    for batch_index, start in enumerate((0, 20, 40, 60), 1):
        subset = matrix[start:start + 20]
        lines = [f"# P5-D6 Sem-Lex Review Batch {batch_index}", "", f"Rows {start + 1}-{start + len(subset)} of 68. No decisions are prefilled.", ""]
        for item in subset:
            lines.extend([
                f"## {item['review_rank']}. {item['canonical_gloss']}", "",
                f"- Deficit: `{item['coverage_deficit_level']}`",
                f"- Current coverage: {item['current_clips']} clips, {item['current_unique_signers']} signers, effective signers {item['current_effective_signers']}",
                f"- Sem-Lex: `{item['semlex_lexical_id']}` / `{item['semlex_gloss']}`; {item['semlex_candidate_train_clips']} TRAIN clips; potential signer gain {item['potential_signer_gain']}",
                f"- Review reason: `{item['review_reason']}`",
                f"- ASL-LEX: {item['asllex_reference']} — {item['asllex_page']}",
                f"- SignBank: {item['signbank_reference']} — {item['signbank_page']}",
                f"- ASLLVD: {item['asllvd_reference']} — {item['asllvd_page']}",
                f"- Human question: **{item['human_question']}**", "",
                "Decision: ____________________", "",
            ])
        (OUT / "review_batches" / f"batch_{batch_index:02d}.md").write_text("\n".join(lines), encoding="utf-8")

    build_viewer([{**decisions[index], "current_clips": order[index]["current_clips"], "current_unique_signers": order[index]["current_unique_signers"], "current_effective_signers": order[index]["current_effective_signers"], "asllex_page": matrix[index]["asllex_page"], "signbank_page": matrix[index]["signbank_page"], "asllvd_page": matrix[index]["asllvd_page"]} for index in range(len(order))])

    decision_contract = {
        "status": "PREREGISTERED_NOT_APPLIED", "allowed_human_decisions": ["ACCEPT_EXACT_FORM", "ACCEPT_COMPATIBLE_VARIANT", "REJECT_FORM_MISMATCH", "UNRESOLVED"],
        "classification_precedence": [
            {"classification": "SEMLEX_REVIEW_INCOMPLETE", "rule": "unresolved classes >=14 OR unresolved critical classes >=8"},
            {"classification": "SEMLEX_RAW_ACQUISITION_JUSTIFIED", "rule": "accepted classes >=47 AND accepted critical >=27 AND accepted high >=20 AND median accepted signer gain >=11"},
            {"classification": "SEMLEX_RAW_ACQUISITION_TARGETED_ONLY", "rule": "accepted classes >=7 and at least one accepted critical class"},
            {"classification": "SEMLEX_RAW_ACQUISITION_NOT_JUSTIFIED", "rule": "all other completed-review outcomes"},
        ],
        "threshold_basis": "fixed before review from the 70-class target, two-thirds broad-coverage rule, 20% unresolved-importance rule, 10% targeted-value floor, and D5 p25 signer-gain reference of 11",
        "popsign": {"status": "EXCLUDED_FROM_APPHEAR_SUPPLEMENTATION", "reason": "MODALITY_MISMATCH_ONE_HAND_RECORDING_CONSTRAINT"},
        "no_human_decision_made_in_p5d6": True,
    }
    write_json(OUT / "p5d6_post_review_decision_contract.json", decision_contract)
    write_json(OUT / "p5d6_next_gate.json", {"recommended_next_action": "HUMAN COMPLETES SEMLEX REVIEW DECISION SHEET", "next_computational_gate": "APPLY_COMPLETED_HUMAN_SEMLEX_REVIEW", "executed": False})

    ready_count = sum(r["authoritative_reference_ready"] for r in readiness)
    partial_count = sum(r["partial_reference_evidence"] for r in readiness)
    metadata_count = sum(r["metadata_only_evidence"] for r in readiness)
    raw_count = sum(r["visual_confirmation_requires_raw_access"] for r in readiness)
    result = f"""# P5-D6 Human Sem-Lex Review Package Result

## Package status

The frozen 68-row D5 review queue was reconstructed exactly: 38 critical and 30 high-deficit classes. The two prior `ACCEPT_METADATA_EXACT` classes are excluded. Every human decision field is blank.

## Readiness

- Authoritative-reference ready now: {ready_count}
- Partial-reference evidence: {partial_count}
- Metadata-only evidence: {metadata_count}
- Visual confirmation requiring future raw access: {raw_count} (overlaps partial/metadata-only; no access performed)

Readiness describes available evidence, not lexical acceptance.

## Review tools

- Canonical decision sheet: `semlex_human_decision_sheet.csv`
- Evidence matrix: `semlex_review_evidence_matrix.csv`
- Deterministic batches: 20 / 20 / 20 / 8
- Optional static viewer: `semlex_review_viewer.html`; browser-local choices can be exported, but the governed CSV remains canonical
- Post-review calculator: `model/p5d6_apply_human_semlex_review.py` — prepared, not executed

## Governance

No raw media, DWPose, V2, merge, training, protected-test, PopSign, Android, or context action occurred. PopSign remains excluded for `MODALITY_MISMATCH_ONE_HAND_RECORDING_CONSTRAINT`.
"""
    (OUT / "P5D6_HUMAN_REVIEW_PACKAGE_RESULT.md").write_text(result, encoding="utf-8")

    source_after = {name: sha256(D5 / name) for name in required_inputs}
    source_after["progress_tracker"] = sha256(PROGRESS)
    blank_fields = all(not row[field] for row in decisions for field in ("human_decision", "human_notes", "reviewer", "review_date"))
    integrity = {
        "passed": source_before == source_after and len(review) == 68 and len(exact) == 2 and blank_fields,
        "d5_artifact_hashes_verified": d5_checked, "source_hashes_before": source_before, "source_hashes_after": source_after,
        "original_target_classes": 70, "already_exact_excluded": 2, "human_review_rows": 68,
        "critical_review_rows": sum(r["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT" for r in review),
        "high_review_rows": sum(r["coverage_deficit_level"] == "HIGH_COVERAGE_DEFICIT" for r in review),
        "human_decisions_prefilled": 0, "blank_reviewer_fields_verified": blank_fields,
        "review_batches": [20, 20, 20, 8], "raw_media_downloaded": False, "semlex_archive_downloaded": False,
        "dwpose": "NONE", "v2_created": False, "external_merge": False, "training": False,
        "protected_test_accessed": False, "popsign_used": False, "android_modified": False,
        "context_files_modified": False, "progress_tracker_untouched": source_before["progress_tracker"] == source_after["progress_tracker"],
        "review_readiness": {"authoritative_reference_ready": ready_count, "partial_reference": partial_count, "metadata_only": metadata_count, "raw_access_required": raw_count},
    }
    write_json(OUT / "p5d6_integrity.json", integrity)

    artifact_rows = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            artifact_rows.append({"path": str(path.relative_to(OUT)).replace("\\", "/"), "sha256": sha256(path), "bytes": path.stat().st_size})
    for code in (Path(__file__), POST_REVIEW):
        artifact_rows.append({"path": str(code.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(code), "bytes": code.stat().st_size, "role": "supporting_code"})
    write_json(OUT / "artifact_hash_manifest.json", {"algorithm": "SHA-256", "artifacts": artifact_rows})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build"])
    args = parser.parse_args()
    if args.command == "build":
        build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
