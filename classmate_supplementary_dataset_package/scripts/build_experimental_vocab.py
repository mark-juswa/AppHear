from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from audit_local_dataset import load_experimental_includes


def main() -> int:
    parser = argparse.ArgumentParser(description="Create expanded vocab for experimental local-only labels.")
    parser.add_argument("--base-vocab", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--experimental-includes", type=Path, default=Path("config/include_experimental_labels.json"))
    args = parser.parse_args()

    vocab: dict[str, int] = json.loads(args.base_vocab.read_text(encoding="utf-8-sig"))
    expanded = dict(vocab)
    for gloss in sorted(set(load_experimental_includes(args.experimental_includes).values())):
        if gloss not in expanded:
            expanded[gloss] = len(expanded)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "vocab.json").write_text(json.dumps(expanded, indent=2), encoding="utf-8")
    # Keep a copy of the base vocab for traceability.
    shutil.copy2(args.base_vocab, args.out_dir / "base_deployed_vocab.json")
    added = [g for g in expanded if g not in vocab]
    print(f"[vocab] base={len(vocab)} expanded={len(expanded)} added={added}")
    print(f"[vocab] wrote {args.out_dir / 'vocab.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

