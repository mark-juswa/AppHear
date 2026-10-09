"""Import approved standalone Original Character animations; never alter originals."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

QUALIFIED: dict[str, tuple[str, list[str]]] = {
    "CALL__TO_CALL_SOMEONE_S_NAME": (
        "call_someones_name",
        ["call someones name", "call to call someones name"],
    ),
    "HARD__SOLID": ("hard_solid", ["hard solid", "solid"]),
    "KEEP__PRESERVE": ("keep_preserve", ["keep preserve", "preserve"]),
    "LETTER__MAIL": ("letter_mail", ["letter mail", "mail"]),
    "MEAN__MEANING_OR_DEFINITION_OF_SOMETHING": (
        "mean_meaning",
        ["mean meaning", "meaning", "definition of something"],
    ),
    "MEET__TO_MEET_MANY_PEOPLE": (
        "meet_many_people",
        ["meet many people", "meet to meet many people"],
    ),
    "MOVE__TO_MOVE_TO_NEW_LOCATION": (
        "move_new_location",
        ["move new location", "move to new location"],
    ),
    "PAY__TO_PAY_SOMEONE": ("pay_someone", ["pay someone", "pay to pay someone"]),
    "PLAY__TO_PLAY_A_GAME": ("play_game", ["play a game", "play game", "play to play a game"]),
    "RIGHT__DIRECTION": ("right_direction", ["right direction"]),
    "SHOP__GOING_TO_STORE_TO_BUY_GOODS": ("shop", ["shop", "shop going to store to buy goods"]),
    "SHOW__TO_SHOW_SOMEONE": ("show_someone", ["show someone", "show to show someone"]),
    "STORE__TO_SAVE": ("store_save", ["store save", "save"]),
    "TURN__TURN_AROUND": ("turn_around", ["turn around", "turn turn around"]),
    "WHAT__RHETORICAL_WHAT": ("what_rhetorical", ["what rhetorical", "rhetorical what"]),
}


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def import_batch(app: Path, source: Path) -> dict[str, object]:
    original_path = app / "android/app/src/main/assets/asl_animations/manifest.json"
    original_hash = digest(original_path)
    original = json.loads(original_path.read_text())["clips"]
    alias_map = {
        normalized(a): c["id"] for c in original for a in [c["id"], c["displayText"], *c["aliases"]]
    }
    base_by_id = {c["id"]: c for c in original}
    target = app / "android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1"
    target.mkdir(parents=True, exist_ok=True)
    replacements: list[dict[str, object]] = []
    additions: list[dict[str, object]] = []
    with zipfile.ZipFile(source) as archive:
        top = sorted(
            (i for i in archive.infolist() if not i.is_dir() and len(Path(i.filename).parts) == 2),
            key=lambda i: i.filename,
        )
        assert len(top) == 204
        for item in top:
            name = Path(item.filename).stem
            assert re.fullmatch(r"[A-Z_]+", name)
            if name == "STAND":
                continue
            with archive.open(item) as stream:
                magic, version, length = struct.unpack("<III", stream.read(12))
                size, chunk_type = struct.unpack("<II", stream.read(8))
                assert (
                    magic == 0x46546C67
                    and version == 2
                    and length == item.file_size
                    and chunk_type == 0x4E4F534A
                )
                document = json.loads(stream.read(size))
            animations = document["animations"]
            assert len(animations) == 1
            times = [document["accessors"][s["input"]] for s in animations[0]["samplers"]]
            duration = max(a["max"][0] for a in times) - min(a["min"][0] for a in times)
            assert 0 < duration <= 10
            destination = target / (name.lower() + ".glb")
            with archive.open(item) as stream, destination.open("wb") as output:
                while block := stream.read(1024 * 1024):
                    output.write(block)
            common: dict[str, object] = {
                "sourceName": name,
                "sourceZipPath": item.filename,
                "asset": "asl_animations/original_words_v1/" + destination.name,
                "animationName": animations[0]["name"],
                "durationMs": round(duration * 1000),
                "sha256": digest(destination),
                "bytes": item.file_size,
            }
            plain = normalized(re.sub(r"_+", " ", name))
            if plain in alias_map:
                identity = alias_map[plain]
                assert base_by_id[identity]["type"] in ("word", "phrase")
                replacements.append(
                    {**common, "id": identity, "fallbackAsset": base_by_id[identity]["asset"]}
                )
            else:
                identity, aliases = QUALIFIED.get(name, (name.lower(), [plain]))
                additions.append(
                    {
                        **common,
                        "id": identity,
                        "displayText": aliases[0].title(),
                        "type": "word",
                        "aliases": aliases,
                    }
                )
    assert len(replacements) == 32 and len(additions) == 171
    full = original + additions
    identities: set[str] = set()
    final_aliases: dict[str, str] = {}
    for clip in full:
        identity = str(clip["id"])
        assert identity not in identities, identity
        identities.add(identity)
        for value in [identity, str(clip["displayText"]), *clip["aliases"]]:
            key = normalized(value)
            assert key not in final_aliases or final_aliases[key] == identity, (key, identity)
            final_aliases[key] = identity
    result: dict[str, object] = {
        "schemaVersion": 1,
        "packageId": "original-word-batch-v1",
        "sourceZipSha256": digest(source),
        "baseManifestSha256": original_hash,
        "standExcluded": True,
        "replacements": replacements,
        "newClips": additions,
    }
    manifest = target / "manifest.json"
    manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert digest(original_path) == original_hash
    return {
        "manifest_sha256": digest(manifest),
        "replacements": 32,
        "additions": 171,
        "catalog_entries": len(full),
        "payload_files": 203,
        "payload_bytes": sum(int(str(c["bytes"])) for c in replacements + additions),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    receipt = import_batch(args.app_root, args.zip)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
