"""Ingest ASL-recorder clips -> v3.0 streaming features mapped to the conversational 236 vocab.

Composes the SAME clip-level stage functions as the ASL Citizen pipeline (extract -> detect ->
features) so recorded clips share the exact landmark dialect. Writes ONE recorded.npz to a NEW dir;
ASL Citizen + the deployed model are untouched. Then `pipeline.ingest.merge` supplements/replaces a
gloss in the conversational feature set for retraining.

  python -m pipeline.ingest.run \
      --recorded-root "F:/ASL DATASET/ASL CITIZEN/recorded/AppHearDataset" \
      --out "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_streaming_recorded"

Recorded layout: <root>/samples/signs/<word>/<clip>.mp4 paired with <clip>.json (Stage-E sidecar
with gloss + signer_id). Clips whose gloss is not in the target vocab, or with no valid signing
span, are skipped with a logged reason (never fatal). The mp4 is re-extracted in IMAGE mode by the
same LandmarkExtractor used for ASL Citizen — the recorder's on-device landmarks are NOT used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from ..detect.config import load_config as load_detect_config
from ..detect.signals import compute_signals
from ..detect.span import detect_span
from ..extract.config import load_config as load_extract_config
from ..extract.landmarks import LandmarkExtractor
from ..features.config import load_config as load_features_config
from ..features.contract import SCHEMA_VERSION, clip_features_realtimed
from ..normalize.config import load_config as load_normalize_config

ROOT = Path(__file__).resolve().parents[2]
EXTRACT_CFG = ROOT / "pipeline" / "config" / "extract.yaml"
DETECT_CFG = ROOT / "pipeline" / "config" / "detect.yaml"
FEATURES_CFG = ROOT / "pipeline" / "config" / "features.yaml"
DEFAULT_VOCAB = Path("F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_conversational/vocab.json")


def scan_recorder_output(root: Path) -> list[dict]:
    """Find recorded clips: every <clip>.json sidecar paired with a sibling <clip>.mp4."""
    clips: list[dict] = []
    signs_dir = root / "samples" / "signs"
    for sidecar in sorted(signs_dir.rglob("*.json")):
        video = sidecar.with_suffix(".mp4")
        if not video.exists():
            print(f"[ingest] no video for {sidecar.name} — skip", file=sys.stderr)
            continue
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[ingest] bad sidecar {sidecar.name}: {e} — skip", file=sys.stderr)
            continue
        clips.append({
            "video": video,
            "gloss": meta.get("gloss"),
            "word": meta.get("word"),
            "signer_id": meta.get("signer_id", "unknown"),
        })
    return clips


def run(recorded_root: Path, out_dir: Path, vocab_path: Path) -> int:
    if not (recorded_root / "samples").exists():
        print(f"[ingest] no samples/ under {recorded_root}", file=sys.stderr)
        return 2
    vocab: dict[str, int] = json.loads(vocab_path.read_text(encoding="utf-8"))
    ex_cfg = load_extract_config(EXTRACT_CFG)        # model paths + confidences (IMAGE mode)
    det_cfg = load_detect_config(DETECT_CFG)          # D1/D2 thresholds
    ncfg = load_normalize_config(load_features_config(FEATURES_CFG).normalize_config)
    t_max = load_features_config(FEATURES_CFG).streaming_t_max

    clips = scan_recorder_output(recorded_root)
    print(f"[ingest] {len(clips)} recorded clips found; target vocab {len(vocab)} glosses")

    xs: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    lengths: list[int] = []
    ys: list[int] = []
    pids: list[str] = []
    n_ok = n_skip_gloss = n_skip_span = n_fail = 0

    with LandmarkExtractor(ex_cfg) as extractor:
        for i, c in enumerate(clips, 1):
            gloss = c["gloss"]
            if gloss is None or gloss not in vocab:
                n_skip_gloss += 1
                continue
            try:
                clip, _meta = extractor.extract(c["video"])
                signals = compute_signals(
                    clip, det_cfg.pose_landmarks, det_cfg.hand_aux_weight,
                    det_cfg.raise_margin, det_cfg.smoothing_window,
                )
                span = detect_span(signals, det_cfg)
                if not span.valid:
                    n_skip_span += 1
                    continue
                feat, fmask, length, _ = clip_features_realtimed(
                    clip.hands_image, clip.pose_image, span.onset, span.release, ncfg, t_max,
                )
                xs.append(feat)
                masks.append(fmask)
                lengths.append(length)
                ys.append(vocab[gloss])
                pids.append(str(c["signer_id"]))
                n_ok += 1
            except Exception as e:  # noqa: BLE001 — one bad clip never kills the run
                print(f"[ingest] FAILED {c['video'].name}: {e}", file=sys.stderr)
                n_fail += 1
            if i % 25 == 0:
                print(f"[ingest] {i}/{len(clips)} (ok={n_ok})")

    if not xs:
        print("[ingest] no usable clips — nothing written", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "recorded.npz"
    np.savez_compressed(
        out,
        X=np.stack(xs).astype(np.float32),
        frame_mask=np.stack(masks),
        lengths=np.array(lengths, dtype=np.int32),
        y=np.array(ys, dtype=np.int32),
        participant_ids=np.array(pids),
        schema_version=SCHEMA_VERSION,
        t_max=t_max,
    )
    # per-gloss / per-signer summary (what the merge tool will act on)
    id2g = {i: g for g, i in vocab.items()}
    from collections import Counter
    by_gloss = Counter(id2g[int(v)] for v in ys)
    print(f"\n[ingest] wrote {n_ok} clips -> {out}")
    print(f"[ingest] skipped: gloss-not-in-vocab={n_skip_gloss} no-valid-span={n_skip_span} failed={n_fail}")
    print(f"[ingest] signers: {sorted(set(pids))}")
    print("[ingest] clips per gloss: " + ", ".join(f"{g}={n}" for g, n in by_gloss.most_common()))
    print("[ingest] next: python -m pipeline.ingest.merge --recorded "
          f'"{out}" --mode supplement')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Ingest ASL-recorder clips into v3.0 streaming features")
    p.add_argument("--recorded-root", type=Path, required=True,
                   help="the AppHearDataset root copied off the phone (contains samples/)")
    p.add_argument("--out", type=Path,
                   default=Path("F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_streaming_recorded"))
    p.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB,
                   help="target vocab.json (default: conversational 236); recorded glosses map to it")
    args = p.parse_args()
    return run(args.recorded_root, args.out, args.vocab)


if __name__ == "__main__":
    raise SystemExit(main())
