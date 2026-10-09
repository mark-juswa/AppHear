"""Verify shared model/catalog/research byte contracts without data access or training."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    checked = 0
    package = ROOT / "packages/fingerspelling_continuous_v2_1_01"
    for entry in json.loads((package / "package_inventory.json").read_text())["files"]:
        assert sha(package / entry["path"]) == entry["sha256"], entry["path"]
        checked += 1
    catalog = (
        ROOT
        / "android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/manifest.json"
    )
    assert sha(catalog) == "4c08af4d1257ebb0b85258cd52c99cd54f0c66233b095cab28174f8296d88717"
    config = json.loads(catalog.read_text())
    assert len(config["replacements"]) == 32 and len(config["newClips"]) == 171
    assert config["standExcluded"]
    for clip in config["replacements"] + config["newClips"]:
        assert (
            sha(ROOT / "android/app/src/aslOriginalWords/assets" / clip["asset"]) == clip["sha256"]
        ), clip["id"]
        checked += 1
    inventory = ROOT / "evidence/team_handoff_20261009/import_inventory.json"
    for entry in json.loads(inventory.read_text()):
        assert sha(ROOT / entry["path"]) == entry["sha256"], entry["path"]
        checked += 1
    foundation = ROOT / "datasets/fingerspelling/foundation_01/tranche_manifest.json"
    assert sha(foundation) == "6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e"
    print(
        json.dumps(
            {
                "status": "TEAM_SHARED_STATE_HASH_PASS",
                "hashes_checked": checked,
                "training_started": False,
                "test_payload_accessed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
