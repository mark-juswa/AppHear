"""Audit shipped GLB mappings and prepare reference-only review inventories.

No videos are downloaded, no animations generated, and no dictionary is activated.
Public research metadata paths are supplied explicitly and remain outside the APK.
"""
import argparse
import collections
import csv
import hashlib
import json
import pathlib
import re
import struct
import xml.etree.ElementTree as ET

ANDROID = pathlib.Path(__file__).resolve().parents[1]


def normalize(text):
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower().replace("’", "'").replace("'", "")).split())


def read_json(path):
    return json.loads(path.read_bytes())


def selected_entries():
    base = read_json(ANDROID / "app/src/main/assets/asl_animations/manifest.json")["clips"]
    by_id = {entry["id"]: entry for entry in base}
    batch = read_json(ANDROID / "app/src/aslOriginalWords/assets/asl_animations/original_words_v1/manifest.json")
    original = [dict(by_id[e["id"]], **{k: v for k, v in e.items() if k != "id"}) for e in batch["replacements"]]
    original += batch["newClips"]
    new = read_json(ANDROID / "app/src/aslAlphabet/assets/asl_animations/vnext/manifest.json")
    female = [dict(by_id[e["id"]], **{k: v for k, v in e.items() if k != "id"}) for e in new["clips"]]
    female += new["newClips"]
    female += [dict(e, aliases=[e["displayText"].lower()]) for e in new["letters"]]
    return base, {"ORIGINAL_HUMAN": original, "NEW_HUMAN": female}


def audit(entries, profile):
    rows, aliases = [], collections.defaultdict(set)
    source_set = "aslOriginalWords" if profile == "ORIGINAL_HUMAN" else "aslAlphabet"
    cached = {}
    for entry in entries:
        path = ANDROID / "app/src" / source_set / "assets" / entry["asset"]
        if path.exists() and path not in cached:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                header = stream.read(20)
                magic, version, size, length, chunk = struct.unpack("<IIIII", header)
                assert magic == 0x46546C67 and version == 2 and chunk == 0x4E4F534A and size == path.stat().st_size
                content = stream.read(length)
                gltf = json.loads(content)
                digest.update(header)
                digest.update(content)
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            cached[path] = (digest.hexdigest(), {a.get("name") for a in gltf.get("animations", [])}, gltf)
        valid = path.exists() and cached[path][0] == entry["sha256"] and entry["animationName"] in cached[path][1]
        for alias in entry.get("aliases", []):
            aliases[normalize(alias)].add(entry["id"])
        gltf = cached[path][2] if path in cached else {}
        morph_channels = sum(c["target"]["path"] == "weights" for a in gltf.get("animations", []) for c in a.get("channels", []))
        rows.append({"id": entry["id"], "english": entry.get("displayText", entry["id"]),
                     "aliases": entry.get("aliases", []), "type": entry.get("type", by_type(entry)),
                     "avatarProfile": profile, "asset": entry["asset"], "animationName": entry["animationName"],
                     "sha256": entry["sha256"], "structurallyValid": valid,
                     "status": "MAPPED" if valid else "UNSUPPORTED", "playbackEvidence": None,
                     "linguisticallyValidated": False, "nonManualReview": "not documented",
                     "morphAnimationChannelCount": morph_channels})
    return {"entries": rows, "signMotionCount": len(rows), "structurallyValidMotions": sum(r["structurallyValid"] for r in rows),
            "types": dict(collections.Counter(r["type"] for r in rows)),
            "multiwordAliases": sum(any(" " in normalize(a) for a in r["aliases"]) for r in rows),
            "duplicateIds": [key for key, n in collections.Counter(r["id"] for r in rows).items() if n > 1],
            "duplicateNormalizedAliases": {a: sorted(ids) for a, ids in aliases.items() if len(ids) > 1},
            "newPlaybackEvidenceCount": 0, "linguisticallyValidatedCount": 0,
            "neutralPoseCount": 1}


def by_type(entry):
    return "letter" if entry["id"].startswith("letter_") else "word"


def reference_inventory(research, catalogs):
    wlasl = read_json(research / "WLASL_v0.3.json")
    classes = {normalize(e["gloss"]): e for e in wlasl}
    known = {normalize(a) for values in catalogs.values() for e in values for a in e.get("aliases", [])}
    categories = {
        "family": "family parents brother sister grandmother grandfather aunt uncle cousin husband wife son daughter marriage wedding relative",
        "questions": "who whose why which how question answer explain understand remember forget know learn repeat again same different meaning",
        "food_drink": "water milk coffee tea juice bread rice meat chicken fish egg eggs apple banana orange fruit vegetable sugar salt breakfast lunch dinner restaurant cook hungry thirsty delicious eat drink food cheese soup salad sandwich pizza potato butter kitchen",
        "emotions": "happy sad angry afraid scared excited tired worry worried lonely bored love hate like dislike feel feeling emotion enjoy smile laugh cry calm nervous surprise disappointed",
        "school": "school student teacher college university class lesson homework book read write study paper pencil pen computer language deaf hearing speak practice test exam mathematics science library education teach work job office meeting business boss money pay price buy sell store market shop",
        "transport": "car bus train bicycle bike airplane travel drive walk stop street road station airport ticket arrive leave destination traffic taxi transportation boat truck parking trip vacation hotel map city town home house apartment room door window",
        "health_assistance": "help hospital doctor nurse medicine pain sick hurt emergency police fire danger safe safety healthy health support bathroom toilet wash clean soap bathroom need want please sorry patient ambulance insurance accident problem difficult easy",
        "time_daily": "time today tomorrow yesterday morning afternoon evening night week month year day hour minute second late early soon later before after now sleep wake bed finish start begin end wait open close rain snow cold hot weather clothes coat shirt shoes pants bathroom telephone phone battery charger internet email address appointment birthday holiday schedule Monday Tuesday Wednesday Thursday Friday Saturday Sunday weekend season summer winter spring fall date calendar",
        "greetings": "hello welcome goodbye thank thanks greeting introduction name nice meet visit friend friendship people person man woman boy girl baby child children everyone community",
    }
    candidates, seen = [], set()
    for category, words in categories.items():
        for word in words.lower().split():
            if word in seen or word in known or word not in classes:
                continue
            seen.add(word)
            entry = classes[word]
            samples = entry["instances"]
            candidates.append({"english": word, "category": category, "status": "CANDIDATE", "avatarAsset": None,
                "linguisticallyValidated": False, "wlaslGloss": entry["gloss"], "referenceCount": len(samples),
                "referenceExamples": [{key: sample[key] for key in ["video_id", "url", "source", "variation_id", "frame_start", "frame_end"]} for sample in samples[:2]],
                "referenceMediaAvailability": "not checked; videos not downloaded", "license": "C-UDA computational use; WLASL academic/noncommercial statement",
                "requiredWork": "permission and sense/variant review; compatible motion asset; playback and qualified ASL review"})
    # Balance the research shortlist across categories rather than filling it with food alone.
    by_category = {category: [item for item in candidates if item["category"] == category] for category in categories}
    selected = []
    while len(selected) < 50 and any(by_category.values()):
        for bucket in by_category.values():
            if bucket and len(selected) < 50:
                selected.append(bucket.pop(0))
    candidates = selected
    ecv = ET.parse(research / "asl.ecv").getroot()
    signs = [(e.attrib["CVE_ID"], e.find("CVE_VALUE").text, e.find("CVE_VALUE").attrib.get("DESCRIPTION", "")) for e in ecv.findall(".//CV_ENTRY_ML")]
    for item in candidates:
        word = item["english"]
        item["signbankReferences"] = [{"id": identifier, "idGloss": gloss,
            "entryUrl": f"https://aslsignbank.com/dictionary/gloss/{identifier}.html"}
            for identifier, gloss, description in signs
            if normalize(gloss) == word or word in {normalize(x) for x in description.split(',')}]
        item["variantNote"] = "Multiple Signbank references are lexical alternatives, not interchangeable mapped animations."
        item["aslLexCrossReference"] = "not mapped; official OSF download inaccessible in this session"
    return candidates, len(wlasl), sum(len(e["instances"]) for e in wlasl), len(signs)


def phrase_inventory(research):
    with (research / "how2sign_realigned_test.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    phrases = [
        ("What is your name?", "Ask the addressee's name"), ("How are you?", "Ask about wellbeing"),
        ("Where are you going?", "Ask a destination"), ("Thank you", "Express gratitude"),
        ("Good morning", "Morning greeting"), ("I need help", "Request assistance"),
        ("I am hungry", "State hunger"), ("I am a student", "State student identity"),
        ("Can you help me?", "Request help, rather than merely ask ability"), ("What time is it?", "Ask current time"),
        ("Nice to meet you", "Express pleasure at introduction"), ("See you tomorrow", "Part with an anticipated tomorrow encounter"),
        ("Please help me", "Politely request assistance"), ("I do not understand", "State lack of comprehension"),
        ("Please repeat", "Ask for repetition"), ("I am sorry", "Apologize; sense/context must be reviewed"),
        ("You are welcome", "Respond to gratitude"), ("I feel sick", "State illness"),
        ("I need water", "Request water"), ("Where is the bathroom?", "Ask bathroom location"),
    ]
    result = []
    for text, meaning in phrases:
        needle = normalize(text)
        matches = [{"row": index+2, "sentenceId": r["SENTENCE_ID"], "videoId": r["VIDEO_ID"],
                    "startSeconds": r["START_REALIGNED"], "endSeconds": r["END_REALIGNED"]}
                   for index, r in enumerate(rows) if needle in normalize(r["SENTENCE"])]
        result.append({"english": text, "meaningForReview": meaning, "status": "CANDIDATE", "gloss": [], "signIds": [],
                       "linguisticallyValidated": False, "requiredNonManualMarkers": "requires qualified review",
                       "how2signTestMatches": matches[:3], "referenceMatchCount": len(matches),
                       "referenceNote": "English substring locator only; not an ASL gloss or verified aligned expression"})
    greetings = [{"row": n+2, "sentenceId": r["SENTENCE_ID"], "startSeconds": r["START_REALIGNED"], "endSeconds": r["END_REALIGNED"]}
                 for n,r in enumerate(rows) if normalize(r["SENTENCE"]) == "hi"]
    return result, len(rows), greetings[:3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--research-dir", type=pathlib.Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    base, catalogs = selected_entries()
    audits = {profile: audit(entries, profile) for profile, entries in catalogs.items()}
    result = {"scope": "ASL Text-to-Sign engineering inventory; not linguistic validation", "baseMixedCatalogEntries": len(base), "catalogs": audits}
    (args.output / "vocabulary-audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (args.output / "vocabulary-audit.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["profile","id","english","type","asset","animation","structurally_valid","status","linguistically_validated"])
        for profile, audit_result in audits.items():
            for row in audit_result["entries"]:
                writer.writerow([profile,row["id"],row["english"],row["type"],row["asset"],row["animationName"],row["structurallyValid"],row["status"],False])
    if args.research_dir:
        candidates, words, references, signs = reference_inventory(args.research_dir, catalogs)
        phrases, sentences, greetings = phrase_inventory(args.research_dir)
        research = {"wlaslClassesInspected": words, "wlaslReferenceInstances": references, "signbankEcvEntriesInspected": signs,
                    "how2signTestRowsInspected": sentences, "wordCandidates": candidates, "phraseCandidates": phrases,
                    "how2signGreetingLocators": greetings, "newAssetsAdded": 0, "newValidatedWords": 0, "newValidatedPhrases": 0,
                    "sourceSnapshots": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.research_dir.iterdir() if p.is_file()}}
        (args.output / "research-candidates.json").write_text(json.dumps(research, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Research-only candidates:",len(candidates),"words;",len(phrases),"English phrase targets.")
    for profile, values in audits.items():
        print(profile,values["signMotionCount"],"mappings;",values["structurallyValidMotions"],"valid GLB actions;",values["types"])
        assert not values["duplicateIds"] and not values["duplicateNormalizedAliases"]
        assert values["signMotionCount"] == values["structurallyValidMotions"]


if __name__ == "__main__":
    main()
