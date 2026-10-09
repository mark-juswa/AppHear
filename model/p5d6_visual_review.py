"""Prepare a local side-by-side AppHear/Sem-Lex human review viewer.

Uses only existing local raw media. It does not run DWPose, generate V2,
merge datasets, train, or access protected test data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tarfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade"
D6 = BASE / "p5_representation_v2/p5d6_semlex_human_review_01"
OUT = BASE / "p5_representation_v2/p5d6_semlex_visual_review_01"
ARCHIVE = Path(r"G:\SEM LEX\train.tar.gz")
MEDIA_ROOT = Path(r"G:\SEM LEX\AppHear_P5D6_visual_review")
APPHEAR_MEDIA = MEDIA_ROOT / "apphear"
SEMLEX_MEDIA = MEDIA_ROOT / "semlex"
SEMLEX_META = Path(r"D:\Downloads\semlex_metadata.csv")
MANIFEST = BASE / "phase1_full_vocab/manifest_01/canonical_manifest.csv"
PROGRESS = ROOT / "context/progress-tracker.md"
PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable(value: str) -> str:
    return hashlib.sha256(("P5D6_VISUAL_V1|" + value).encode()).hexdigest()


def norm(value: Any) -> str:
    import re
    text = re.sub(r"\s*\d+$", "", str(value).strip().lower())
    return re.sub(r"[^a-z0-9]", "", text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, data: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def verify_inputs() -> None:
    if not ARCHIVE.is_file():
        raise RuntimeError(f"Missing Sem-Lex archive: {ARCHIVE}")
    if sha(PROGRESS) != PROGRESS_SHA:
        raise RuntimeError("progress-tracker hash mismatch")
    d6 = json.loads((D6 / "p5d6_integrity.json").read_text(encoding="utf-8"))
    if not d6["passed"] or d6["human_review_rows"] != 68:
        raise RuntimeError("P5-D6 integrity failed")


def prepare() -> None:
    verify_inputs()
    OUT.mkdir(parents=True, exist_ok=True)
    APPHEAR_MEDIA.mkdir(parents=True, exist_ok=True)
    SEMLEX_MEDIA.mkdir(parents=True, exist_ok=True)
    order = read_csv(D6 / "p5d6_review_order.csv")
    sheet = {r["class_id"]: r for r in read_csv(D6 / "semlex_human_decision_sheet.csv")}

    sem = pd.read_csv(SEMLEX_META, low_memory=False)
    sem = sem[sem["split"].astype(str).str.lower() == "train"].copy()
    sem["_norm"] = sem["label"].map(norm)
    app = [r for r in read_csv(MANIFEST) if r["role"] in ("primary_train", "supplement_train")]
    app_by_gloss: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in app:
        app_by_gloss[row["canonical_gloss"]].append(row)

    selections: list[dict[str, Any]] = []
    viewer: list[dict[str, Any]] = []
    members: list[str] = []
    for row in order:
        cid, gloss = row["class_id"], row["canonical_gloss"]
        group = sem[sem["_norm"] == norm(gloss)].copy()
        group["_key"] = group.apply(lambda r: stable(f"{cid}|{r['signer_id']}|{r['video_id']}"), axis=1)
        chosen_sem = []
        for signer, signer_group in group.groupby("signer_id"):
            first = signer_group.sort_values("_key").iloc[0]
            chosen_sem.append((stable(f"{cid}|signer|{signer}"), first))
        chosen_sem = [item[1] for item in sorted(chosen_sem, key=lambda x: x[0])[:3]]

        chosen_app = []
        seen = set()
        for candidate in sorted(app_by_gloss[gloss], key=lambda r: stable(f"{cid}|{r['signer_group_id']}|{r['sample_id']}")):
            if candidate["signer_group_id"] in seen or not Path(candidate["raw_video_path"]).is_file():
                continue
            chosen_app.append(candidate)
            seen.add(candidate["signer_group_id"])
            if len(chosen_app) == 2:
                break

        app_files, sem_files = [], []
        for index, candidate in enumerate(chosen_app, 1):
            source = Path(candidate["raw_video_path"])
            target = APPHEAR_MEDIA / f"rank_{int(row['review_rank']):02d}_{cid}_{index}{source.suffix.lower()}"
            if not target.exists() or target.stat().st_size != source.stat().st_size:
                shutil.copy2(source, target)
            app_files.append(target.as_uri())
            selections.append({"review_rank": row["review_rank"], "class_id": cid, "canonical_gloss": gloss,
                               "side": "APPHEAR", "slot": index, "sample_id": candidate["sample_id"],
                               "signer_id": candidate["signer_group_id"], "source_path_or_member": str(source),
                               "viewer_media_path": str(target)})
        for index, candidate in enumerate(chosen_sem, 1):
            video_id = str(candidate["video_id"])
            member = f"./train/{video_id}.webm"
            target = SEMLEX_MEDIA / f"rank_{int(row['review_rank']):02d}_{cid}_{index}.webm"
            sem_files.append(target.as_uri())
            members.append(member)
            selections.append({"review_rank": row["review_rank"], "class_id": cid, "canonical_gloss": gloss,
                               "side": "SEMLEX", "slot": index, "sample_id": video_id,
                               "signer_id": str(candidate["signer_id"]), "source_path_or_member": member,
                               "viewer_media_path": str(target)})
        viewer.append({**row, **sheet[cid], "apphear_videos": app_files, "semlex_videos": sem_files})
    missing_semlex = [item["class_id"] for item in viewer if not item["semlex_videos"]]
    if len(viewer) != 68 or missing_semlex:
        raise RuntimeError(
            f"Expected 68 classes with at least one Sem-Lex selection each; "
            f"got {len(viewer)} classes and missing selections for {missing_semlex}"
        )
    write_csv(OUT / "visual_review_selection.csv", selections)
    (OUT / "semlex_archive_members.txt").write_text("\n".join(members) + "\n", encoding="utf-8")
    (OUT / "visual_review_data.json").write_text(json.dumps(viewer, indent=2) + "\n", encoding="utf-8")
    build_html(viewer)
    write_integrity("PREPARED_MEDIA_EXTRACTION_PENDING")


def extract() -> None:
    verify_inputs()
    selection_path = OUT / "visual_review_selection.csv"
    all_selection = read_csv(selection_path)
    selection = [row for row in all_selection if row["side"] == "SEMLEX"]
    missing_by_class: dict[str, list[dict[str, str]]] = defaultdict(list)
    used_signers: dict[str, set[str]] = defaultdict(set)
    remaining: dict[str, dict[str, str]] = {}
    for row in selection:
        target = Path(row["viewer_media_path"])
        if target.is_file() and target.stat().st_size > 0:
            used_signers[row["class_id"]].add(row["signer_id"])
        else:
            missing_by_class[row["class_id"]].append(row)
            remaining[row["source_path_or_member"]] = row

    if not remaining:
        print("All 200 selected Sem-Lex review clips are already extracted.")
        write_integrity("READY_FOR_HUMAN_VISUAL_REVIEW")
        return

    # Some Sem-Lex metadata rows do not have a corresponding raw archive member.
    # Build same-class alternatives; archive order deterministically decides which
    # available distinct-signer alternative fills each missing review slot.
    sem = pd.read_csv(SEMLEX_META, low_memory=False)
    sem = sem[sem["split"].astype(str).str.lower() == "train"].copy()
    sem["_norm"] = sem["label"].map(norm)
    selected_members = {row["source_path_or_member"] for row in selection}
    fallback_by_member: dict[str, dict[str, str]] = {}
    for class_id, slots in missing_by_class.items():
        gloss = slots[0]["canonical_gloss"]
        candidates = sem[sem["_norm"] == norm(gloss)].copy()
        candidates["_key"] = candidates.apply(
            lambda row: stable(f"fallback|{class_id}|{row['signer_id']}|{row['video_id']}"), axis=1
        )
        for _, candidate in candidates.sort_values("_key").iterrows():
            video_id = str(candidate["video_id"])
            member_name = f"./train/{video_id}.webm"
            if member_name in selected_members:
                continue
            fallback_by_member[member_name] = {
                "class_id": class_id,
                "video_id": video_id,
                "signer_id": str(candidate["signer_id"]),
            }

    replacements = 0
    extracted_now = 0
    last_percent = -1
    last_report = 0.0

    def extract_member(archive: tarfile.TarFile, member: tarfile.TarInfo, target: Path) -> None:
        source = archive.extractfile(member)
        if source is None:
            raise RuntimeError(f"Could not read archive member {member.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".partial")
        with source, partial.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
        if partial.stat().st_size != member.size:
            raise RuntimeError(f"Incomplete extraction for {member.name}")
        partial.replace(target)

    with tarfile.open(ARCHIVE, "r:gz") as archive:
        for member in archive:
            normalized = "./" + member.name.lstrip("./")
            now = time.monotonic()
            compressed = getattr(archive.fileobj, "fileobj", None)
            compressed_position = compressed.tell() if compressed is not None else 0
            percent = min(100, int(100 * compressed_position / ARCHIVE.stat().st_size))
            if percent > last_percent or now - last_report >= 5:
                print(
                    f"\rScanning archive: {percent:3d}% | extracted this run: {extracted_now} "
                    f"| still needed: {len(remaining)}",
                    end="",
                    flush=True,
                )
                last_percent = percent
                last_report = now

            row = remaining.get(normalized)
            if row is not None:
                extract_member(archive, member, Path(row["viewer_media_path"]))
                used_signers[row["class_id"]].add(row["signer_id"])
                missing_by_class[row["class_id"]].remove(row)
                del remaining[normalized]
                extracted_now += 1
            else:
                fallback = fallback_by_member.get(normalized)
                if fallback is not None:
                    class_id = fallback["class_id"]
                    slots = missing_by_class.get(class_id, [])
                    if slots and fallback["signer_id"] not in used_signers[class_id]:
                        slot = slots.pop(0)
                        old_member = slot["source_path_or_member"]
                        extract_member(archive, member, Path(slot["viewer_media_path"]))
                        remaining.pop(old_member, None)
                        slot["sample_id"] = fallback["video_id"]
                        slot["signer_id"] = fallback["signer_id"]
                        slot["source_path_or_member"] = normalized
                        used_signers[class_id].add(fallback["signer_id"])
                        replacements += 1
                        extracted_now += 1
                        # Persist each substitution immediately so a stopped scan
                        # cannot leave a fallback video paired with stale metadata.
                        write_csv(selection_path, all_selection)
            if not remaining:
                break
    print()
    if remaining:
        raise RuntimeError(f"Missing {len(remaining)} selected Sem-Lex archive members")
    if replacements:
        write_csv(selection_path, all_selection)
        print(f"Replaced {replacements} metadata-only selections with available same-class clips.")
    write_integrity("READY_FOR_HUMAN_VISUAL_REVIEW")


def build_html(items: list[dict[str, Any]]) -> None:
    payload = json.dumps(items).replace("</", "<\\/")
    html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AppHear Sem-Lex Visual Review</title><style>
body{font:15px system-ui;margin:0;background:#f4f6f8;color:#17202a}.wrap{max-width:1200px;margin:18px auto;padding:0 16px}.card{background:#fff;border:1px solid #ccd5df;border-radius:12px;padding:20px}.videos{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{background:#f8fafc;border-radius:10px;padding:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}video{width:100%;max-height:260px;background:#111}.choices{display:grid;gap:7px;margin:16px 0}.choices label{border:1px solid #ccd5df;border-radius:7px;padding:9px}.controls,.fields{display:flex;gap:8px;flex-wrap:wrap}.fields label{flex:1}button,input{padding:8px 11px}textarea{width:100%;min-height:65px}.warn{background:#fff1bd;padding:10px;border-radius:8px}@media(max-width:800px){.videos{grid-template-columns:1fr}}
</style></head><body><div class="wrap"><h1>AppHear ↔ Sem-Lex Visual Form Review</h1><p class="warn">Compare the actual motion, handshape, number of hands, orientation, location, and meaning. English gloss equality is not enough.</p><div id="app"></div></div><script>
const items=__DATA__,choices=['ACCEPT_EXACT_FORM','ACCEPT_COMPATIBLE_VARIANT','REJECT_FORM_MISMATCH','UNRESOLVED'];let i=0;const saved=JSON.parse(localStorage.getItem('p5d6-visual-decisions')||'{}');function e(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}function vids(paths){return paths.map(p=>`<video controls preload="metadata" src="${e(p)}"></video>`).join('')}function save(){localStorage.setItem('p5d6-visual-decisions',JSON.stringify(saved))}function store(){const x=items[i],d=document.querySelector('[name=d]:checked');saved[x.class_id]={decision:d?d.value:'',notes:document.getElementById('notes').value,reviewer:document.getElementById('reviewer').value,date:document.getElementById('date').value};save()}function render(){const x=items[i],s=saved[x.class_id]||{};document.getElementById('app').innerHTML=`<p>Item ${i+1} of ${items.length} · rank ${x.review_rank}</p><div class="card"><h2>${e(x.canonical_gloss)}</h2><p>${e(x.coverage_deficit_level)} · AppHear ${x.current_clips} clips/${x.current_unique_signers} signers · Sem-Lex ${x.semlex_candidate_train_clips} clips/${x.semlex_candidate_signers} signers</p><div class="videos"><section class="panel"><h3>Existing AppHear TRAIN examples</h3><div class="grid">${vids(x.apphear_videos)}</div></section><section class="panel"><h3>Sem-Lex TRAIN candidates</h3><div class="grid">${vids(x.semlex_videos)}</div></section></div><p><strong>Are the Sem-Lex signs the same intended AppHear class?</strong></p><div class="choices">${choices.map(c=>`<label><input type="radio" name="d" value="${c}" ${s.decision===c?'checked':''}> ${c}</label>`).join('')}</div><label>Notes<br><textarea id="notes">${e(s.notes||'')}</textarea></label><div class="fields"><label>Reviewer<br><input id="reviewer" value="${e(s.reviewer||'')}"></label><label>Date<br><input id="date" type="date" value="${e(s.date||'')}"></label></div><div class="controls"><button id="prev">Previous</button><button id="next">Save & next</button><button id="export">Export completed CSV</button></div></div>`;document.querySelectorAll('[name=d]').forEach(n=>n.onchange=store);document.getElementById('prev').onclick=()=>{store();i=Math.max(0,i-1);render()};document.getElementById('next').onclick=()=>{store();i=Math.min(items.length-1,i+1);render()};document.getElementById('export').onclick=exportCsv}function q(v){return '"'+String(v??'').replaceAll('"','""')+'"'}function exportCsv(){store();const heads=['review_rank','class_id','canonical_gloss','coverage_deficit_level','semlex_lexical_id','semlex_gloss','semlex_candidate_train_clips','semlex_candidate_signers','asllex_reference','signbank_reference','asllvd_reference','other_authoritative_reference','review_reason','human_decision','human_notes','reviewer','review_date'],lines=[heads.join(',')];for(const x of items){const s=saved[x.class_id]||{};lines.push(heads.map(h=>q(h==='human_decision'?(s.decision||''):h==='human_notes'?(s.notes||''):h==='reviewer'?(s.reviewer||''):h==='review_date'?(s.date||''):(x[h]??''))).join(','))}const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{type:'text/csv'}));a.download='semlex_human_decision_sheet_completed.csv';a.click();URL.revokeObjectURL(a.href)}render();
</script></body></html>""".replace("__DATA__", payload)
    (OUT / "semlex_visual_review_viewer.html").write_text(html, encoding="utf-8")


def write_integrity(status: str) -> None:
    media = list(SEMLEX_MEDIA.glob("*.webm"))
    app = list(APPHEAR_MEDIA.glob("*"))
    selection_path = OUT / "visual_review_selection.csv"
    selected_semlex = (
        sum(1 for row in read_csv(selection_path) if row["side"] == "SEMLEX")
        if selection_path.is_file()
        else 0
    )
    value = {"status": status, "review_classes": 68, "selected_semlex_clips": selected_semlex,
             "extracted_semlex_clips": len(media), "copied_apphear_train_clips": len(app),
             "semlex_archive": str(ARCHIVE), "semlex_archive_bytes": ARCHIVE.stat().st_size,
             "visual_review_media_root": str(MEDIA_ROOT),
             "raw_media_downloaded_by_tool": False, "dwpose": "NONE", "v2_generated": False,
             "external_merge": False, "training": False, "protected_test_accessed": False,
             "progress_tracker_untouched": sha(PROGRESS) == PROGRESS_SHA}
    (OUT / "visual_review_integrity.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "extract"])
    args = parser.parse_args()
    prepare() if args.command == "prepare" else extract()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
