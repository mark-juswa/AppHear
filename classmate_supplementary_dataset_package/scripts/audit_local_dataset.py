from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_vocab(path: Path) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8-sig")).keys())


def load_labels(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {norm_word(item.get("word", "")): item for item in data.get("labels", [])}


def load_experimental_includes(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {norm_word(k): str(v).strip().upper().replace(" ", "_").replace("-", "_") for k, v in data.get("include", {}).items()}

def norm_word(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def fallback_gloss(value: object) -> str:
    return str(value or "").strip().upper().replace(" ", "_").replace("-", "_")


def find_video(sidecar: Path, meta: dict, mp4_by_name: dict[str, list[Path]]) -> Path | None:
    raw = meta.get("video_file") or meta.get("video") or meta.get("mp4")
    candidates: list[Path] = []
    if raw:
        name = Path(str(raw)).name
        candidates.extend([
            sidecar.parent / name,
            sidecar.parent / "video" / name,
            sidecar.parent.parent / "video" / name,
        ])
        candidates.extend(mp4_by_name.get(name, []))
    candidates.append(sidecar.with_suffix(".mp4"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def sidecar_word(sidecar: Path, meta: dict) -> str:
    if meta.get("word"):
        return str(meta["word"])
    if meta.get("label"):
        return str(meta["label"])
    if sidecar.parent.name.lower() in {"accepted", "rejected", "video"}:
        return sidecar.parent.parent.name
    return sidecar.parent.name


def classify_schema(meta: dict) -> str:
    if "word" in meta and "gloss" in meta and "frames" not in meta:
        return "recorder_video_primary"
    if "frames" in meta:
        return "baked_258_json_use_video_only"
    return "unknown"


def build_rows(source: Path, vocab: set[str], labels: dict[str, dict], experimental: dict[str, str] | None = None) -> tuple[list[dict], list[str]]:
    experimental = experimental or {}
    effective_vocab = set(vocab) | set(experimental.values())
    mp4_by_name: dict[str, list[Path]] = defaultdict(list)
    for mp4 in source.rglob("*.mp4"):
        mp4_by_name[mp4.name].append(mp4)

    rows: list[dict] = []
    errors: list[str] = []
    for sidecar in sorted(source.rglob("*.json")):
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"parse_error,{sidecar},{exc}")
            continue
        batch = sidecar.relative_to(source).parts[0] if sidecar.relative_to(source).parts else ""
        word = sidecar_word(sidecar, meta)
        item = labels.get(norm_word(word))
        json_gloss = meta.get("gloss") or fallback_gloss(word)
        mapped_gloss = item.get("gloss") if item else None
        chosen_gloss = experimental.get(norm_word(word)) or mapped_gloss or json_gloss
        video = find_video(sidecar, meta, mp4_by_name)
        usable = bool(chosen_gloss and chosen_gloss in effective_vocab and video is not None)
        rows.append({
            "batch": batch,
            "word": word,
            "json_gloss": json_gloss,
            "mapped_gloss": mapped_gloss or "",
            "chosen_gloss": chosen_gloss or "",
            "usable": usable,
            "needs_remap": bool(json_gloss != chosen_gloss and chosen_gloss in effective_vocab),
            "skip_reason": "" if usable else ("missing_video" if video is None else "gloss_not_in_target_vocab"),
            "label_status": "experimental_include" if norm_word(word) in experimental else (item.get("status") if item else "not_in_labels_json"),
            "signer_id": meta.get("signer_id") or "unknown",
            "language": meta.get("sign_language") or meta.get("language") or "",
            "schema": classify_schema(meta),
            "sidecar": str(sidecar),
            "video": str(video) if video else "",
        })
    return rows, errors


def write_report(rows: list[dict], errors: list[str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "audit_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["batch", "word", "json_gloss", "mapped_gloss", "chosen_gloss", "usable", "needs_remap", "skip_reason", "label_status", "signer_id", "language", "schema", "sidecar", "video"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    usable = [r for r in rows if r["usable"]]
    skipped = [r for r in rows if not r["usable"]]
    remap = [r for r in rows if r["needs_remap"]]
    lines = [
        "# Local Supplementary Dataset Audit",
        "",
        f"Total JSON sidecars parsed: {total}",
        f"Usable clips after target-vocab mapping: {len(usable)}",
        f"Skipped/manual-review clips: {len(skipped)}",
        f"Clips requiring safe remap: {len(remap)}",
        f"Parse errors: {len(errors)}",
        "",
        "## By Batch",
    ]
    for batch in sorted({r["batch"] for r in rows}):
        br = [r for r in rows if r["batch"] == batch]
        lines.append(f"- Dataset {batch}: json={len(br)}, usable={sum(1 for r in br if r['usable'])}, skipped={sum(1 for r in br if not r['usable'])}, signers={len({r['signer_id'] for r in br if r['signer_id']})}")
    lines += ["", "## Usable Gloss Counts"]
    by_gloss = Counter(r["chosen_gloss"] for r in usable)
    for gloss, count in sorted(by_gloss.items()):
        signers = len({r["signer_id"] for r in usable if r["chosen_gloss"] == gloss and r["signer_id"]})
        lines.append(f"- {gloss}: {count} clips, {signers} signer(s)")
    lines += ["", "## Safe Remaps"]
    for key, count in sorted(Counter(f"{r['json_gloss']} -> {r['chosen_gloss']}" for r in remap).items()):
        lines.append(f"- {key}: {count} clips")
    lines += ["", "## Skipped / Manual Review"]
    for gloss, count in sorted(Counter(r["json_gloss"] for r in skipped).items()):
        lines.append(f"- {gloss}: {count} clips")
    if errors:
        lines += ["", "## Parse Errors"] + [f"- {e}" for e in errors[:50]]
    (out_dir / "audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local supplementary ASL datasets before AppHear ingest.")
    parser.add_argument("--source", type=Path, default=Path(r"F:\ASL DATASET\local"))
    parser.add_argument("--vocab", type=Path, default=Path("config/deployed_vocab.json"))
    parser.add_argument("--labels", type=Path, default=Path("config/labels.json"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--experimental-includes", type=Path, default=Path("config/include_experimental_labels.json"), help="optional word->gloss include overrides for local-only test classes")
    args = parser.parse_args()
    rows, errors = build_rows(args.source, load_vocab(args.vocab), load_labels(args.labels), load_experimental_includes(args.experimental_includes))
    write_report(rows, errors, args.out)
    print(f"[audit] wrote {args.out / 'audit_report.md'}")
    print(f"[audit] wrote {args.out / 'audit_manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



