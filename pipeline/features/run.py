"""Stage-F builder: compose N1-N3 -> N4 -> v3.0 feature vectors for the accepted clips in a
split, stack them, and persist one .npz per split + a shared vocab.

  python -m pipeline.features.run --split val --build-vocab     # build vocab from this split
  python -m pipeline.features.run --split test                  # reuse existing vocab

In production, build the vocab once on --split train, then run val/test without --build-vocab.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from ..detect.schema import SpanSidecar
from ..extract.schema import ClipLandmarks
from ..normalize.config import load_config as load_normalize_config
from ..quality.config import load_config as load_quality_config
from ..quality.gate import evaluate_quality
from .config import FeaturesConfig, load_config
from .contract import FEATURE_DIM, SCHEMA_VERSION, clip_features

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "features.yaml"


def _vocab_path(fcfg: FeaturesConfig) -> Path:
    return fcfg.output_root / "vocab.json"


def run(split: str, build_vocab: bool, limit: int | None, config_path: Path) -> int:
    fcfg = load_config(config_path)
    ncfg = load_normalize_config(fcfg.normalize_config)
    qcfg = load_quality_config(fcfg.quality_config)
    t_len = qcfg.resample_T

    in_dir = qcfg.input_root / split
    npz_files = sorted(in_dir.glob("*.npz"))
    if not npz_files:
        print(f"[features] no clips in {in_dir} — run stages E and D first", file=sys.stderr)
        return 2
    if limit is not None:
        npz_files = npz_files[:limit]

    feats: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    glosses: list[str] = []
    pids: list[str] = []
    n_seen = n_skipped_q = n_failed = 0

    for npz_path in npz_files:
        cid = npz_path.stem
        span_path = qcfg.spans_root / split / f"{cid}.span.json"
        if not span_path.exists():
            continue
        n_seen += 1
        try:
            clip = ClipLandmarks.load(npz_path)
            span = SpanSidecar.load(span_path)
            if fcfg.accepted_only:
                res = evaluate_quality(
                    clip.hand_score,
                    clip.pose_score,
                    span.onset,
                    span.release,
                    span.valid,
                    span.native_fps,
                    qcfg,
                )
                if not res.accept:
                    n_skipped_q += 1
                    continue
            feature, mask, _ = clip_features(
                clip.hands_image, clip.pose_image, span.onset, span.release, ncfg, t_len
            )
            feats.append(feature)
            masks.append(mask)
            glosses.append(span.gloss)
            pids.append(span.participant_id)
        except Exception as err:  # noqa: BLE001
            print(f"[features] FAILED {cid}: {err}", file=sys.stderr)
            n_failed += 1

    # vocab
    fcfg.output_root.mkdir(parents=True, exist_ok=True)
    vpath = _vocab_path(fcfg)
    if build_vocab:
        vocab = {g: i for i, g in enumerate(sorted(set(glosses)))}
        vpath.write_text(json.dumps(vocab, indent=2), encoding="utf-8")
    elif vpath.exists():
        vocab = json.loads(vpath.read_text(encoding="utf-8"))
    else:
        print(
            f"[features] no vocab at {vpath} — run one split with --build-vocab first",
            file=sys.stderr,
        )
        return 2

    # map labels, dropping OOV glosses
    keep = [i for i, g in enumerate(glosses) if g in vocab]
    n_oov = len(glosses) - len(keep)
    if not keep:
        print("[features] no clips with an in-vocab gloss", file=sys.stderr)
        return 2

    x = np.stack([feats[i] for i in keep]).astype(np.float32)  # (N, T, 258)
    m = np.stack([masks[i] for i in keep]).astype(np.float32)  # (N, T, 2)
    y = np.array([vocab[glosses[i]] for i in keep], dtype=np.int32)
    participants = np.array([pids[i] for i in keep])

    out_path = fcfg.output_root / f"{split}.npz"
    np.savez_compressed(
        out_path,
        X=x,
        mask=m,
        y=y,
        participant_ids=participants,
        schema_version=SCHEMA_VERSION,
    )
    _report(split, fcfg, x, m, y, vocab, n_seen, n_skipped_q, n_oov, n_failed, out_path)
    return 0


def _report(
    split: str,
    fcfg: FeaturesConfig,
    x: np.ndarray,
    m: np.ndarray,
    y: np.ndarray,
    vocab: dict,
    n_seen: int,
    n_skipped_q: int,
    n_oov: int,
    n_failed: int,
    out_path: Path,
) -> None:
    has_nan = bool(np.isnan(x).any())
    print(f"\n=== F feature build ({split}, schema v{fcfg.schema_version}) ===")
    print(f"clips seen={n_seen}  Q-skipped={n_skipped_q}  OOV-skipped={n_oov}  failed={n_failed}")
    print(f"X shape={x.shape} (expect (...,{FEATURE_DIM}))  vocab={len(vocab)} glosses")
    print(f"X has NaN: {has_nan} (MUST be False)  range=[{x.min():.3f}, {x.max():.3f}]")
    print(f"presence mask mean (L,R)={m.reshape(-1, 2).mean(axis=0).round(3).tolist()}")
    print(f"-> {out_path}")
    assert not has_nan, "feature matrix contains NaN — imputation failed"
    assert x.shape[-1] == FEATURE_DIM


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 stage-F v3.0 feature builder")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--build-vocab", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.split, args.build_vocab, args.limit, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
