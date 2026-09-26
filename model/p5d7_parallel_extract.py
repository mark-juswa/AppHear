"""Launch exact frame-by-frame P5-D7 workers over a staged manifest."""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading


def relay(prefix: str, stream) -> None:
    for line in iter(stream.readline, ""):
        print(f"[{prefix}] {line.rstrip()}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2))
    parser.add_argument("--torch-threads", type=int, default=0)
    args = parser.parse_args()
    processes = []
    threads = []
    for index in range(args.workers):
        command = [sys.executable, "-m", "model.p5d7_semlex_extract_v2", "extract-staged",
                   "--manifest", args.manifest, "--output-root", args.output_root,
                   "--shard-count", str(args.workers), "--shard-index", str(index),
                   "--frame-batch-size", "1", "--torch-threads", str(args.torch_threads)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, bufsize=1)
        processes.append(process)
        thread = threading.Thread(target=relay, args=(f"worker-{index}", process.stdout), daemon=True)
        thread.start(); threads.append(thread)
    codes = [process.wait() for process in processes]
    for thread in threads: thread.join()
    print(f"worker exit codes: {codes}", flush=True)
    return 0 if all(code == 0 for code in codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
