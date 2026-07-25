"""Reduce the streaming feature set to the top-N data-richest glosses — NO re-extraction. The full
2731-class model is data-limited (~13 clips/class → ~31% top-1); training on a smaller vocabulary
of the signs with the MOST clips is the cheapest large accuracy win (pilots: 100 classes ≈ 41%/74%
vs 2731 ≈ 31%/55%). This filters + relabels the existing features_streaming/*.npz and writes a
reduced feature set + vocab that the streaming trainer/export reuse unchanged (bar a config path).

  python -m pipeline.features.reduce_vocab --n 250
  python -m pipeline.features.reduce_vocab --n 100 --smoke

Selection = the N glosses with the most TRAIN clips (data-richest → best accuracy). New label ids
are 0..N-1 assigned in alphabetical gloss order (deterministic). Memory-safe: mmap + row-index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .config import load_config

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "features.yaml"
SPLITS = ("train", "val", "test")


def run(n: int, smoke: bool, config_path: Path, wordlist: Path | None = None) -> int:
    fcfg = load_config(config_path)
    full_vocab_path = fcfg.output_root / "vocab.json"
    streaming_dir = fcfg.streaming_output_root
    # A curated --wordlist writes to a SEPARATE "conversational" tag so the data-richest
    # "features_reduced" (the currently-deployed model's data) is never overwritten — safety net.
    tag = "conversational" if wordlist is not None else "reduced"
    reduced_stream = streaming_dir.parent / f"features_streaming_{tag}"
    reduced_vocab_dir = fcfg.output_root.parent / f"features_{tag}"

    if not full_vocab_path.exists():
        print(f"[reduce] no vocab at {full_vocab_path}", file=sys.stderr)
        return 2
    full_vocab: dict[str, int] = json.loads(full_vocab_path.read_text(encoding="utf-8"))
    id_to_gloss = {i: g for g, i in full_vocab.items()}

    train_npz = streaming_dir / "train.npz"
    if not train_npz.exists():
        print(f"[reduce] no streaming features at {train_npz}", file=sys.stderr)
        return 2

    with np.load(train_npz, allow_pickle=True, mmap_mode="r") as d:
        y_train = np.asarray(d["y"])
    counts = np.bincount(y_train, minlength=len(full_vocab))

    if wordlist is not None:
        # curated selection: exactly the glosses in the file that exist in the full vocab
        requested = [ln.strip() for ln in wordlist.read_text(encoding="utf-8").splitlines() if ln.strip()]
        missing = [g for g in requested if g not in full_vocab]
        if missing:
            print(f"[reduce] WARNING {len(missing)} wordlist glosses not in vocab (skipped): "
                  f"{', '.join(missing)}", file=sys.stderr)
        selected_ids = [full_vocab[g] for g in requested if g in full_vocab]
        n = len(selected_ids)
    else:
        # data-richest: the top-N classes by TRAIN clip count
        n = min(n, int((counts > 0).sum()))
        selected_ids = [int(i) for i in np.argsort(counts)[::-1][:n]]

    # new label ids 0..N-1 in alphabetical gloss order (deterministic, vocab-stable)
    selected_glosses = sorted(id_to_gloss[int(i)] for i in selected_ids)
    new_vocab = {g: k for k, g in enumerate(selected_glosses)}
    old_to_new = {full_vocab[g]: k for g, k in new_vocab.items()}
    selected_old = np.array(sorted(old_to_new), dtype=np.int64)

    reduced_vocab_dir.mkdir(parents=True, exist_ok=True)
    (reduced_vocab_dir / "vocab.json").write_text(json.dumps(new_vocab, indent=2), encoding="utf-8")
    reduced_stream.mkdir(parents=True, exist_ok=True)

    sel_counts = counts[selected_old]
    kept_train = int(sel_counts.sum())
    print(f"[reduce] tag={tag} N={n} classes (of {len(full_vocab)}); train clips kept={kept_train} "
          f"(~{kept_train / max(n, 1):.1f}/class); median/class={int(np.median(sel_counts))}; "
          f"min={int(sel_counts.min())}")
    if smoke:
        print("[reduce] --smoke: vocab written, skipping npz filtering")
        return 0

    for split in SPLITS:
        path = streaming_dir / f"{split}.npz"
        if not path.exists():
            print(f"[reduce] skip {split} (missing)", file=sys.stderr)
            continue
        with np.load(path, allow_pickle=True, mmap_mode="r") as d:
            y = np.asarray(d["y"])
            keep = np.isin(y, selected_old)
            idx = np.where(keep)[0]
            x = np.asarray(d["X"][idx])
            fm = np.asarray(d["frame_mask"][idx])
            lengths = np.asarray(d["lengths"][idx])
            pids = np.asarray(d["participant_ids"][idx])
            y_new = np.array([old_to_new[int(v)] for v in y[idx]], dtype=np.int32)
        out = reduced_stream / f"{split}.npz"
        np.savez_compressed(
            out, X=x, frame_mask=fm, lengths=lengths, y=y_new, participant_ids=pids,
            schema_version="3.0", t_max=x.shape[1],
        )
        print(f"[reduce] {split}: {len(idx)} clips (of {len(y)}) -> {out}")

    print(f"\n[reduce] done. vocab -> {reduced_vocab_dir / 'vocab.json'}")
    print(f"[reduce] features -> {reduced_stream}")
    cfg = "train_streaming_conversational.yaml" if wordlist else "train_streaming_reduced.yaml"
    print(f"[reduce] next: retrain with model/config/{cfg}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Reduce streaming vocab to top-N data-richest glosses, "
                                            "or a curated --wordlist")
    p.add_argument("--n", type=int, default=250)
    p.add_argument("--wordlist", type=Path, default=None,
                   help="file of glosses (one per line) → curated vocab in a 'conversational' tag")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.n, args.smoke, args.config, args.wordlist)


if __name__ == "__main__":
    raise SystemExit(main())
