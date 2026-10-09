"""Create bounded RU-D7 evidence contact sheets without modifying captured images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--session-id", default="ru_d7_phone_bc_01")
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    attempts: list[tuple[int, Path, dict[str, object]]] = []
    for metadata_path in args.attempt_root.rglob("metadata.json"):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("session_id") == args.session_id:
            attempts.append((int(metadata["capture_order"]), metadata_path.parent, metadata))

    for order, directory, metadata in sorted(attempts):
        frames = sorted((directory / "evidence").glob("frame_*.jpg"))
        if not frames:
            continue
        sample_count = min(args.samples, len(frames))
        indices = sorted(
            {
                round(index * (len(frames) - 1) / max(sample_count - 1, 1))
                for index in range(sample_count)
            }
        )
        selected = [frames[index] for index in indices]
        thumb_width = 240
        label_height = 28
        thumbs = []
        for path in selected:
            with Image.open(path) as source:
                image = source.convert("RGB")
            height = round(image.height * thumb_width / image.width)
            image = image.resize((thumb_width, height))
            canvas = Image.new("RGB", (thumb_width, height + label_height), "white")
            canvas.paste(image, (0, label_height))
            ImageDraw.Draw(canvas).text((6, 6), path.stem.replace("frame_", "frame "), fill="black")
            thumbs.append(canvas)
        columns = 4
        rows = (len(thumbs) + columns - 1) // columns
        cell_height = max(image.height for image in thumbs)
        header_height = 34
        sheet = Image.new(
            "RGB", (columns * thumb_width, header_height + rows * cell_height), "white"
        )
        title = f"{order:02d} {metadata['ground_truth']} {metadata.get('repetition_id', '')}"
        ImageDraw.Draw(sheet).text((8, 8), title, fill="black")
        for index, image in enumerate(thumbs):
            x = (index % columns) * thumb_width
            y = header_height + (index // columns) * cell_height
            sheet.paste(image, (x, y))
        sheet.save(
            args.output
            / f"{order:02d}_{metadata['ground_truth']}_{metadata.get('repetition_id', '')}.jpg",
            quality=88,
        )

    print(f"contact_sheets={len(attempts)} output={args.output.resolve()}")


if __name__ == "__main__":
    main()
