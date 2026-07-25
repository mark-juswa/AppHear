"""Build or verify the frozen signer-split manifest (artifacts/splits.json).

python -m pipeline.splits.run                 # build + write + report
python -m pipeline.splits.run --verify        # rebuild, compare to pinned, fail on drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..extract.config import load_config as load_extract_config
from .registry import SplitManifest, build_manifest, verify_disjoint

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "artifacts" / "splits.json"
DEFAULT_EXTRACT_CONFIG = REPO_ROOT / "pipeline" / "config" / "extract.yaml"


def _splits_dir() -> Path:
    return load_extract_config(DEFAULT_EXTRACT_CONFIG).splits_dir


def _report(manifest: SplitManifest) -> None:
    print("\n=== signer-split manifest ===")
    print(f"source={manifest.source}  hash={manifest.content_hash}")
    total_signers = len(manifest.participant_split)
    total_clips = sum(c["clips"] for c in manifest.counts.values())
    for split in ("train", "val", "test"):
        c = manifest.counts[split]
        print(f"  {split:<6} signers={c['signers']:>3}  clips={c['clips']:>6}")
    print(f"  total  signers={total_signers:>3}  clips={total_clips:>6}")
    print("disjoint: OK (a signer is in exactly one split)")


def build(manifest_path: Path) -> int:
    splits_dir = _splits_dir()
    if not splits_dir.exists():
        print(f"[splits] splits dir not found: {splits_dir}", file=sys.stderr)
        return 2
    manifest = build_manifest(splits_dir)
    manifest.save(manifest_path)
    _report(manifest)
    print(f"-> {manifest_path}")
    return 0


def verify(manifest_path: Path) -> int:
    splits_dir = _splits_dir()
    overlap = verify_disjoint(splits_dir)
    if overlap:
        print(f"[splits] LEAKAGE: signers in multiple splits: {overlap}", file=sys.stderr)
        return 1
    if not manifest_path.exists():
        print(f"[splits] no pinned manifest at {manifest_path} — run build first", file=sys.stderr)
        return 2
    pinned = SplitManifest.load(manifest_path)
    rebuilt = build_manifest(splits_dir)
    if pinned.content_hash != rebuilt.content_hash:
        print(
            f"[splits] DRIFT: pinned hash {pinned.content_hash} != rebuilt "
            f"{rebuilt.content_hash} — the official CSVs changed",
            file=sys.stderr,
        )
        return 1
    print(f"[splits] verified: disjoint + matches pinned manifest (hash {pinned.content_hash})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 signer-split manifest build/verify")
    p.add_argument(
        "--verify", action="store_true", help="verify pinned manifest instead of building"
    )
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = p.parse_args()
    return verify(args.manifest) if args.verify else build(args.manifest)


if __name__ == "__main__":
    raise SystemExit(main())
