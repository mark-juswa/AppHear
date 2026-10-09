"""Read-only completion verification for P5-D7 Sem-Lex outputs."""
from __future__ import annotations

import argparse
import json

from model.p5d7_semlex_extract_v2 import platform_path, verify_outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    result = verify_outputs(platform_path(args.manifest), platform_path(args.output_root))
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
