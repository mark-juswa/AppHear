# ruff: noqa: E501  (the embedded HTML/CSS template keeps its natural line lengths)
"""Build the next governed Sem-Lex sign-form review package (P5-D6 process, prioritized classes).

For the top-N uncovered AppHear classes of
docs/audit/probes/word_accuracy/semlex_review_priority.csv
(low WORD_BLEND_01 recall x many Sem-Lex candidate signers) and each Sem-Lex lexical id the
full-vocabulary match matrix lists for them, up to three Sem-Lex TRAIN clips from different signers
are streamed out of the local Sem-Lex TRAIN archive (no download), next to two ASL Citizen TRAIN
reference videos of the AppHear class (governed index; the protected split files are never read).
A self-contained review.html shows them side by side with the P5-D6 decision set and exports the
decisions as CSV. English gloss equality is never treated as a decision: every row starts
UNDECIDED and nothing is used for training until a human decision exists.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
import tarfile
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PRIORITY = ROOT / "docs/audit/probes/word_accuracy/semlex_review_priority.csv"
MATRIX = Path(
    "artifacts/recognition_upgrade/p5_representation_v2/p5d4_external_data_audit_01/"
    "full_vocabulary_external_match_matrix.csv"
)
INDEX = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/dataset/index.jsonl"
)
VIDEOS = Path(r"I:\ASL CITIZEN\ASL CITIZEN\ASL_Citizen\videos")
DECISIONS = [
    "UNDECIDED",
    "ACCEPT_EXACT_FORM",
    "ACCEPT_COMPATIBLE_VARIANT",
    "REJECT_FORM_MISMATCH",
    "UNRESOLVED",
]
PER_FORM = 3
SEED = 9203


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True, help="semlex_metadata.csv")
    parser.add_argument("--archive", type=Path, required=True, help="Sem-Lex train.tar.gz")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--priority", type=Path, default=PRIORITY, help="ranked class list")
    parser.add_argument("--package", default="02", help="package number (output folder name)")
    args = parser.parse_args()
    root = args.evidence_root
    out = root / f"artifacts/semlex_review_{args.package}"
    priority = list(csv.DictReader(args.priority.open(encoding="utf-8")))[: args.top]
    matrix = {
        r["apphear_canonical_gloss"]: r
        for r in csv.DictReader((root / MATRIX).open(encoding="utf-8"))
        if r["external_dataset"] == "SEM_LEX"
    }
    meta = [
        r for r in csv.DictReader(args.metadata.open(encoding="utf-8")) if r["split"] == "train"
    ]
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in meta:
        by_label[f"{r['label_type']}:{r['label'].strip()}"].append(r)
    rng = np.random.default_rng(SEED)
    rows, wanted = [], {}
    for p in priority:
        gloss = p["gloss"]
        for lexical in matrix[gloss]["external_lexical_id"].split("|"):
            pool = by_label.get(lexical.strip(), [])
            seen, chosen = set(), []
            for k in rng.permutation(len(pool)):
                r = pool[int(k)]
                if r["signer_id"] in seen:
                    continue
                seen.add(r["signer_id"])
                chosen.append(r)
                if len(chosen) == PER_FORM:
                    break
            if not chosen:
                continue
            form = {
                f: chosen[0].get(f, "")
                for f in (
                    "Handshape",
                    "Path Movement",
                    "Repeated Movement",
                    "Major Location",
                    "Minor Location",
                    "Sign Type",
                )
            }
            clips = []
            for k, r in enumerate(chosen):
                name = f"{gloss}__{lexical.replace(':', '-')}__{k + 1}.webm"
                wanted[f"train/{r['video_id']}.webm"] = name
                clips.append(
                    {"file": f"semlex/{name}", "video_id": r["video_id"], "signer": r["signer_id"]}
                )
            rows.append(
                {
                    "gloss": gloss,
                    "semlex_lexical_id": lexical,
                    "rank": int(p["rank"]),
                    "blend_recall": p["blend_recall_independent"],
                    "candidate_signers": len({r["signer_id"] for r in pool}),
                    "candidate_clips": len(pool),
                    "asllex_form": form,
                    "clips": clips,
                }
            )
    (out / "semlex").mkdir(parents=True, exist_ok=True)
    found = 0
    with tarfile.open(args.archive, mode="r|gz") as tar:
        for member in tar:
            target = wanted.get(member.name.removeprefix("./"))
            if target is None:
                continue
            source = tar.extractfile(member)
            if source is not None:
                with (out / "semlex" / target).open("wb") as f:
                    shutil.copyfileobj(source, f)
                found += 1
            if found == len(wanted):
                break
    index = [json.loads(line) for line in (root / INDEX).open(encoding="utf-8")]
    (out / "reference").mkdir(parents=True, exist_ok=True)
    for row in rows:
        refs = sorted(
            (
                x
                for x in index
                if x["split"] == "train"
                and x["source_id"] == "ASL_CITIZEN"
                and x["canonical_gloss"] == row["gloss"]
            ),
            key=lambda x: x["sample_id"],
        )
        picked, signers = [], set()
        for x in refs:
            if x["signer_id"] not in signers:
                signers.add(x["signer_id"])
                picked.append(x)
            if len(picked) == 2:
                break
        row["references"] = []
        for k, x in enumerate(picked):
            src = VIDEOS / (x["sample_id"].split(":", 2)[2] + ".mp4")
            dst = out / "reference" / f"{row['gloss']}__{k + 1}.mp4"
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)
            row["references"].append({"file": f"reference/{dst.name}", "sample_id": x["sample_id"]})
        for c in row["clips"]:
            path = out / c["file"]
            c["present"] = path.exists()
            c["sha256"] = sha256(path) if path.exists() else None
    manifest = {
        "schema": "apphear.semlex_review_package.v2",
        "top": args.top,
        "rows": rows,
        "clips_requested": len(wanted),
        "clips_extracted": found,
        "decision_set": DECISIONS[1:],
        "protected_test_accessed": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    write_html(out, rows, args.package)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "classes": len({r["gloss"] for r in rows}),
                "clips_requested": len(wanted),
                "clips_extracted": found,
            }
        )
    )


def write_html(out: Path, rows: list[dict], package: str = "02") -> None:
    def video(f: str) -> str:
        return (
            f'<video src="{html.escape(f)}" controls loop muted playsinline preload="none"></video>'
        )

    body = []
    for k, r in enumerate(rows):
        form = "; ".join(f"{a}: {b}" for a, b in r["asllex_form"].items() if b)
        options = "".join(f"<option>{d}</option>" for d in DECISIONS)
        body.append(
            f'<section data-row="{k}"><h2>#{r["rank"]} {html.escape(r["gloss"])} '
            f"<small>vs Sem-Lex <code>{html.escape(r['semlex_lexical_id'])}</code> · "
            f"{r['candidate_signers']} signers / {r['candidate_clips']} clips · "
            f"current recall {r['blend_recall']}</small></h2>"
            f'<p class="form">Sem-Lex form metadata (first clip): {html.escape(form) or "none"}</p>'
            f'<div class="pair"><div><h3>AppHear reference (ASL Citizen)</h3>'
            f"{''.join(video(x['file']) for x in r['references'])}</div>"
            f"<div><h3>Sem-Lex candidates</h3>{''.join(video(c['file']) for c in r['clips'] if c['present'])}</div></div>"
            f"<label>Decision <select>{options}</select></label> "
            f'<label>Note <input type="text" size="50"></label></section>'
        )
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sem-Lex Form Review</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#d9d9de}}
@media (prefers-color-scheme: dark){{:root{{--bg:#151517;--fg:#ececf1;--muted:#a0a0a8;--line:#333338}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1200px;padding:16px}}
section{{border-top:1px solid var(--line);padding:12px 0}} small,.form{{color:var(--muted)}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} video{{width:48%;margin:1%;background:#000}}
@media (max-width:700px){{.pair{{grid-template-columns:1fr}}}}
button{{font:inherit;padding:6px 12px}}
</style></head><body>
<h1>Sem-Lex Form Review</h1>
<p>For each row: does the Sem-Lex form show the same sign AppHear should recognize as this word?
Same English gloss is <b>not</b> enough. ACCEPT_EXACT_FORM = same sign; ACCEPT_COMPATIBLE_VARIANT = a
legitimate variant AppHear should also accept; REJECT_FORM_MISMATCH = different sign, sense,
fingerspelling or compound; UNRESOLVED = cannot tell. Then press Export.</p>
<button id="export">Export decisions CSV</button>
{"".join(body)}
<script>
const rows = {json.dumps([{"gloss": r["gloss"], "semlex_lexical_id": r["semlex_lexical_id"]} for r in rows])};
document.getElementById('export').onclick = () => {{
  const lines = ['gloss,semlex_lexical_id,decision,note'];
  document.querySelectorAll('section').forEach(s => {{
    const r = rows[+s.dataset.row];
    const note = s.querySelector('input').value.replaceAll('"', "'");
    lines.push([r.gloss, r.semlex_lexical_id, s.querySelector('select').value, '"' + note + '"'].join(','));
  }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([lines.join('\\n')], {{type: 'text/csv'}}));
  a.download = 'semlex_review_{package}_decisions.csv';
  a.click();
}};
</script></body></html>"""
    (out / "review.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
