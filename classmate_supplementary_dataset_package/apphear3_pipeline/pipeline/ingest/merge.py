"""Merge ingested recorder clips into the conversational streaming feature set for retraining.

Recorded clips are added to the TRAIN split only — val/test stay pure ASL Citizen so cross-signer
evaluation still measures generalization to held-out signers (not to the local recording signers).
Writes to a NEW dir; features_streaming_conversational (and ASL Citizen) are untouched.

  # add recorded clips alongside ASL Citizen (safe default — best for data-poor glosses)
  python -m pipeline.ingest.merge --recorded ".../features_streaming_recorded/recorded.npz" --mode supplement

  # replace ASL Citizen's clips for the recorded glosses with the recorded ones (use only when
  # the ASL Citizen clips for those signs are genuinely wrong; risks cross-signer generalization)
  python -m pipeline.ingest.merge --recorded ".../recorded.npz" --mode replace

Then retrain on the new dir (clone train_streaming_conversational.yaml, point features_dir at it).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

BASE = Path("F:/ASL DATASET/ASL CITIZEN/derived/apphear3")
CONV = BASE / "features_streaming_conversational"
VOCAB = BASE / "features_conversational" / "vocab.json"
SPLITS = ("train", "val", "test")


def _load(npz: Path) -> dict[str, np.ndarray]:
    with np.load(npz, allow_pickle=True) as d:
        return {k: np.asarray(d[k]) for k in d.files}


def run(recorded_npz: Path, mode: str, conv_dir: Path, out_dir: Path, vocab_path: Path) -> int:
    rec = _load(recorded_npz)
    vocab: dict[str, int] = json.loads(vocab_path.read_text(encoding="utf-8"))
    id2g = {i: g for g, i in vocab.items()}
    rec_glosses = sorted({id2g[int(v)] for v in rec["y"]})
    print(f"[merge] recorded: {len(rec['y'])} clips across glosses {rec_glosses}")

    out_dir.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        src = _load(conv_dir / f"{split}.npz")
        if split != "train":
            # val/test unchanged (kept pure ASL Citizen cross-signer)
            np.savez_compressed(out_dir / f"{split}.npz", **src)
            print(f"[merge] {split}: {len(src['y'])} (unchanged)")
            continue

        if mode == "replace":
            rec_ids = set(int(v) for v in rec["y"])
            keep = ~np.isin(src["y"], list(rec_ids))
            n_removed = int((~keep).sum())
            base = {k: (src[k][keep] if k in ("X", "frame_mask", "lengths", "y", "participant_ids")
                        else src[k]) for k in src}
            print(f"[merge] train: removed {n_removed} ASL Citizen clips for {rec_glosses}")
        else:  # supplement
            base = {k: src[k] for k in src}

        merged = {
            "X": np.concatenate([base["X"], rec["X"]]).astype(np.float32),
            "frame_mask": np.concatenate([base["frame_mask"], rec["frame_mask"]]),
            "lengths": np.concatenate([base["lengths"], rec["lengths"]]).astype(np.int32),
            "y": np.concatenate([base["y"], rec["y"]]).astype(np.int32),
            "participant_ids": np.concatenate([base["participant_ids"], rec["participant_ids"]]),
            "schema_version": "3.0",
            "t_max": int(src["t_max"]) if "t_max" in src else 96,
        }
        np.savez_compressed(out_dir / f"{split}.npz", **merged)
        print(f"[merge] train: {len(base['y'])} + {len(rec['y'])} recorded = {len(merged['y'])} clips")

    print(f"\n[merge] done ({mode}) -> {out_dir}")
    print("[merge] retrain: clone model/config/train_streaming_conversational.yaml, set "
          f'features_dir="{out_dir}", output_dir to a NEW run dir, then train in .venv.')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Merge recorded clips into conversational features")
    p.add_argument("--recorded", type=Path, required=True, help="features_streaming_recorded/recorded.npz")
    p.add_argument("--mode", choices=["supplement", "replace"], default="supplement")
    p.add_argument("--conv-dir", type=Path, default=CONV)
    p.add_argument("--out", type=Path, default=None,
                   help="output feature dir (default: <conv>_plus for supplement / _replaced for replace)")
    p.add_argument("--vocab", type=Path, default=VOCAB)
    args = p.parse_args()
    out = args.out or (BASE / ("features_streaming_conversational_"
                               + ("replaced" if args.mode == "replace" else "plus")))
    return run(args.recorded, args.mode, args.conv_dir, out, args.vocab)


if __name__ == "__main__":
    raise SystemExit(main())
