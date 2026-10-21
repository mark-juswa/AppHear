"""Build the sentence-assist offline evaluation set (`eval/sentence_assist/cases_v1.jsonl`).

Each case is one Deaf turn as the Recognition screen would hold it: the RECOGNIZED glosses,
optional per-sign Top-5 evidence, the hearing message it answers, and the intended concepts
used for scoring. Categories:
- clean / question / pronoun: correct recognitions of everyday replies and questions.
- noisy_real: Stage 3 phone pilot sequences with their recorded Top-5 (docs/...stage3-pilot.json).
- perturbed_insert / perturbed_substitute / perturbed_delete: seeded recognition errors applied
  to clean cases; the rendering must keep exactly what was recognized, not "repair" it.
- context_mismatch: replies that do not fit the hearing message; context must not override signs.
- swap_help: Top-1 wrong, intended sign inside the substitution bounds (a swap can help).
- swap_decoy: Top-1 correct, a context-plausible alternative inside the bounds (a swap harms).
- long / repeated / negation: correct recognitions of 6-8 sign turns, non-consecutive repeats
  (ASL pronoun copy) and signed negation, whose polarity must not flip.
Swap cases are partly hand-written and partly generated (seeded): half use a context-plausible
confusion, half a random vocabulary sign, always inside the Context Assist substitution bounds,
so the "never replace a correct sign" gate has enough events (about 50) to measure 2 %.
Rebuild with `python -m tools.sentence_assist.build_cases`; output is deterministic.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

VOCABULARY = Path("android/app/src/main/assets/phase4a_gate2_recognizer_parity/manifest.json")
PILOT = Path("docs/conversation-phrase-assist-stage3-pilot.json")
OUTPUT = Path("eval/sentence_assist/cases_v1.jsonl")
SEED = 20261021
SUBSTITUTION_POLICY = Path("android/app/src/main/assets/context_phrase_assist_policy.json")
PERTURBED_PER_KIND = 8
GENERATED_DECOYS = 44
GENERATED_HELP = 14
CONFIDENT = 0.9
FILLERS = ["BAD", "WHICH", "ENOUGH", "BETWEEN", "WHILE"]
Case = dict[str, Any]

CLEAN: list[tuple[str | None, list[str], str]] = [
    ("How are you?", ["GOOD"], "pronoun"),
    ("How are you?", ["TIRED"], "pronoun"),
    ("How are you?", ["SICK"], "pronoun"),
    ("How are you?", ["GOOD", "YOU"], "clean"),
    ("Where are you going?", ["GO", "HOME"], "clean"),
    ("Where are you going?", ["GO", "SCHOOL"], "clean"),
    ("Where are you going?", ["GO", "WORK"], "clean"),
    ("Where are you going?", ["GO", "RESTAURANT", "FRIEND"], "clean"),
    ("What do you want to eat?", ["WANT2", "MEAT1"], "clean"),
    ("What do you want to eat?", ["EAT1", "CAKE"], "clean"),
    ("Do you like school?", ["YES", "LIKE", "SCHOOL"], "clean"),
    ("Do you like school?", ["NO", "LIKE"], "clean"),
    ("Are you tired?", ["YES", "NEED", "SLEEP"], "clean"),
    ("Are you tired?", ["NO", "TIRED"], "clean"),
    ("Where do you live?", ["LIVE2", "HERE"], "clean"),
    ("When is the party?", ["PARTY1", "TOMORROW", "NIGHT1"], "clean"),
    ("Can you help me?", ["YES", "HELP", "YOU"], "clean"),
    ("Can you help me?", ["SORRY", "BUSY", "NOW"], "clean"),
    ("How is your family?", ["FAMILY", "GOOD"], "clean"),
    ("How is your family?", ["MOTHER", "SICK"], "clean"),
    ("Do you have children?", ["YES", "CHILD", "ONE"], "clean"),
    ("What did you do yesterday?", ["YESTERDAY", "WATCH", "MOVIE1"], "clean"),
    ("What did you do yesterday?", ["YESTERDAY", "WORK", "HARD"], "clean"),
    (None, ["HELLO", "NICE", "MEET", "YOU"], "clean"),
    (None, ["PLEASE", "WAIT"], "clean"),
    (None, ["BYE", "SEE", "TOMORROW"], "clean"),
    (None, ["CONGRATULATIONS"], "clean"),
    (None, ["DONTKNOW"], "pronoun"),
    ("Do you want water?", ["YES", "PLEASE"], "clean"),
    ("Where is your car?", ["CAR", "HOME"], "clean"),
    ("Hi!", ["HELLO", "GOOD", "MORNING", "YOU", "HOW1"], "question"),
    (None, ["YOU", "GO", "WHERE"], "question"),
    (None, ["YOU", "LIVE2", "WHERE"], "question"),
    (None, ["WHAT1", "YOU", "WANT2"], "question"),
    (None, ["HOW1", "YOU"], "question"),
    (None, ["WHY", "YOU", "SAD"], "question"),
    (None, ["WHO", "TEACHER"], "question"),
    # Long turns (6-8 signs): real turns can run long (Stage 3 T02 committed 10 events).
    (
        "What did you do yesterday?",
        ["YESTERDAY", "FAMILY", "GO", "RESTAURANT", "EAT1", "MEAT1"],
        "long",
    ),
    (None, ["TOMORROW", "MORNING", "GO", "SCHOOL", "THEN", "WORK", "NIGHT1"], "long"),
    ("Where do you live?", ["MOTHER", "FATHER", "LIVE2", "HOUSE", "BIG", "NEW", "CITY2"], "long"),
    (None, ["YOU", "WANT2", "GO", "MOVIE1", "TOMORROW", "NIGHT1", "WITH", "FRIEND"], "long"),
    (None, ["TEACHER", "TELL", "STUDENT", "READ", "BOOK", "TODAY", "PLEASE"], "long"),
    (
        "Are you coming to the party?",
        ["SORRY", "CANNOT", "COME", "PARTY1", "TOMORROW", "BUSY", "WORK"],
        "long",
    ),
    (
        "Why were you away?",
        ["LAST", "WEEK", "SICK", "HOSPITAL1", "NOW", "GOOD"],
        "long",
    ),
    (None, ["MANY", "PEOPLE", "COME", "HOUSE", "TODAY", "HAPPY", "CONGRATULATIONS"], "long"),
    # Non-consecutive repeats, including ASL pronoun copy at the end of a sentence.
    (None, ["YOU", "GO", "WHERE", "YOU"], "repeated"),
    (None, ["YOU", "LIKE", "COOK", "YOU"], "repeated"),
    ("Where are your parents?", ["THEY1", "GO", "HOME", "THEY1"], "repeated"),
    ("Are you hungry?", ["YES", "WE", "EAT1", "NOW", "WE"], "repeated"),
    ("How was work?", ["WORK", "HARD", "TODAY", "WORK"], "repeated"),
    # Negation: polarity must come only from a signed NO/NEVER/CANNOT/DONTKNOW and must not flip.
    ("Do you want to go?", ["NO", "WANT2", "GO"], "negation"),
    ("Do you eat meat?", ["NEVER", "EAT1", "MEAT1"], "negation"),
    ("See you tomorrow?", ["CANNOT", "COME", "TOMORROW"], "negation"),
    ("Where is the school?", ["DONTKNOW", "WHERE"], "negation"),
    ("Can you talk now?", ["NO", "TIME", "NOW"], "negation"),
    ("Do you like cold weather?", ["NO", "LIKE", "COLD"], "negation"),
    ("Are you happy?", ["NO", "HAPPY"], "negation"),
    ("Are you tired?", ["NO"], "negation"),
    ("Are you tired?", ["YES"], "negation"),
]

MISMATCH: list[tuple[str, list[str]]] = [
    ("Where are you going?", ["MOTHER", "SICK"]),
    ("How are you?", ["CAR", "NEW"]),
    ("What do you want to eat?", ["TOMORROW", "SCHOOL"]),
    ("Do you like school?", ["WANT2", "EAT1"]),
    ("Are you tired?", ["MONEY1", "NEED"]),
    ("How is your family?", ["WORK", "BUSY"]),
]

# (hearing, intended, index of the uncertain sign, Top-1 shown, Top-1 score, intended score).
SWAP_HELP: list[tuple[str | None, list[str], int, str, float, float]] = [
    ("How are you?", ["GOOD"], 0, "HOT", 0.48, 0.44),
    ("Where are you going?", ["GO", "SCHOOL"], 1, "TABLE", 0.47, 0.43),
    ("Are you tired?", ["YES", "TIRED"], 1, "LIVE2", 0.45, 0.41),
    ("What do you want to eat?", ["WANT2", "CAKE"], 1, "CAR", 0.50, 0.46),
    ("Do you like school?", ["YES", "LIKE"], 1, "LEAVE", 0.48, 0.45),
    (None, ["HELLO", "NICE", "MEET", "YOU"], 2, "MEAT1", 0.50, 0.47),
]
# (hearing, intended, index, context-plausible wrong alternative, Top-1 score, alternative score).
SWAP_DECOY: list[tuple[str | None, list[str], int, str, float, float]] = [
    ("Where are you going?", ["GO", "HOME"], 1, "WORK", 0.50, 0.46),
    ("How are you?", ["TIRED"], 0, "GOOD", 0.49, 0.45),
    ("Are you tired?", ["NO"], 0, "YES", 0.52, 0.48),
    ("What do you want to eat?", ["MEAT1"], 0, "CAKE", 0.50, 0.46),
    ("Do you like school?", ["YES", "LIKE", "SCHOOL"], 2, "WORK", 0.50, 0.46),
    ("How is your family?", ["FAMILY", "SICK"], 1, "GOOD", 0.47, 0.44),
]


# Context-plausible confusions: tempting replacements a language model might prefer.
PLAUSIBLE: dict[str, list[str]] = {
    "GOOD": ["BAD", "TIRED", "SICK", "HAPPY"], "TIRED": ["GOOD", "SICK", "HAPPY"],
    "SICK": ["GOOD", "TIRED"], "HOME": ["WORK", "SCHOOL", "HOUSE"], "SCHOOL": ["WORK", "HOME"],
    "WORK": ["SCHOOL", "HOME"], "YES": ["NO"], "NO": ["YES"], "LIKE": ["HATE", "WANT2", "LOVE"],
    "WANT2": ["NEED", "LIKE"], "NEED": ["WANT2"], "TOMORROW": ["YESTERDAY", "TODAY"],
    "YESTERDAY": ["TOMORROW", "TODAY"], "TODAY": ["TOMORROW", "YESTERDAY"],
    "MEAT1": ["CAKE", "WATER"], "CAKE": ["MEAT1"], "MOTHER": ["FATHER", "SISTER"],
    "FATHER": ["MOTHER", "BROTHER"], "HELLO": ["BYE"], "BYE": ["HELLO"], "GO": ["COME", "LEAVE"],
    "COME": ["GO"], "HERE": ["HOME"], "NOW": ["TODAY"], "SLEEP": ["EAT1"],
    "EAT1": ["DRINK2", "SLEEP"], "HAPPY": ["SAD"], "SAD": ["HAPPY"], "BUSY": ["FREE"],
    "BIG": ["SMALL"], "NEW": ["OLD"], "HOT": ["COLD"], "COLD": ["HOT"],
    "NIGHT1": ["MORNING", "AFTERNOON"], "MORNING": ["NIGHT1", "AFTERNOON"],
    "FRIEND": ["FAMILY"], "WATCH": ["SEE", "READ"], "MOVIE1": ["BOOK"], "HARD": ["EASY"],
    "NEVER": ["ALWAYS"], "CANNOT": ["WANT2"],
    "WHERE": ["WHEN", "WHO"], "WHO": ["WHAT1"], "WHY": ["HOW1"], "HOW1": ["WHY"],
    "TEACHER": ["STUDENT"], "STUDENT": ["TEACHER"], "READ": ["WRITE"], "BOOK": ["PAPER"],
    "YOU": ["WE"], "WE": ["YOU", "THEY1"], "THEY1": ["WE"], "PLEASE": ["SORRY"],
    "SORRY": ["PLEASE"], "HELP": ["TAKE"], "LIVE2": ["WORK"], "HOUSE": ["HOME"],
}  # fmt: skip


def substitution_bounds() -> dict[str, float]:
    return json.loads(SUBSTITUTION_POLICY.read_text(encoding="utf-8"))


def within_bounds(top1: float, other: float, bounds: dict[str, float]) -> bool:
    """Same changed-event rule as SubstitutionBounds / PhraseMatcher."""
    return (
        top1 <= bounds["maximum_contradicting_top1"]
        and top1 - other <= bounds["maximum_changed_score_gap"]
        and not (top1 > 0 and other / top1 < bounds["minimum_changed_score_ratio"])
    )


def fillers(exclude: set[str], count: int) -> list[str]:
    return [f for f in FILLERS if f not in exclude][:count]


def collapse(glosses: list[str]) -> list[str]:
    return [g for i, g in enumerate(glosses) if i == 0 or glosses[i - 1] != g]


def confident(gloss: str, turn: list[str]) -> dict[str, Any]:
    others = fillers({gloss, *turn}, 2)
    return {"gloss": gloss, "topK": [[gloss, CONFIDENT], *[[f, 0.02] for f in others]]}


def uncertain(
    shown: str, other: str, top1: float, other_score: float, turn: list[str]
) -> dict[str, Any]:
    tail = fillers({shown, other, *turn}, 1)
    return {
        "gloss": shown,
        "topK": [[shown, top1], [other, other_score], *[[f, 0.03] for f in tail]],
    }


def case(
    case_id: str,
    category: str,
    hearing: str | None,
    glosses: list[str],
    intended: list[str],
    source: str,
    evidence: list[dict[str, Any]] | None = None,
    intended_by_event: list[str | None] | None = None,
) -> Case:
    return {
        "id": case_id,
        "category": category,
        "hearing": hearing,
        "glosses": glosses,
        "evidence": evidence,
        "intendedByEvent": intended_by_event,
        "intended": intended,
        "source": source,
    }


def pilot_cases() -> list[Case]:
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    cases: list[Case] = []
    for attempt in pilot["physicalAttempts"]:
        events = attempt.get("committedEvents")
        if not events:
            continue  # T02 overflowed; its event-level evidence was not retained.
        by_event: dict[int, str] = {}
        classification = attempt.get("classification") or {}
        for association in classification.get("eventAssociations", []):
            by_event[association["eventId"]] = association["intended"]
        for retry in classification.get("deliberateRetry", []):
            by_event[retry["eventId"]] = retry["intended"]
        evidence = [
            {"gloss": e["top1"], "topK": [[k["label"], round(k["score"], 6)] for k in e["topK"]]}
            for e in events
        ]
        cases.append(
            case(
                f"real-{attempt['attemptId'].lower()}",
                "noisy_real",
                attempt["prompt"],
                collapse([e["top1"] for e in events]),
                list(attempt["intendedConcepts"]),
                f"stage3:{attempt['attemptId']}",
                evidence,
                [by_event.get(e["eventId"]) for e in events],
            )
        )
    return cases


def swap_cases(
    rows: list[tuple[str | None, list[str], int, str, float, float]], category: str, decoy: bool
) -> list[Case]:
    cases: list[Case] = []
    for number, (hearing, intended, index, other, top1_score, other_score) in enumerate(rows, 1):
        evidence = [confident(g, intended) for g in intended]
        if decoy:
            evidence[index] = uncertain(intended[index], other, top1_score, other_score, intended)
        else:
            evidence[index] = uncertain(other, intended[index], top1_score, other_score, intended)
        glosses = collapse([event["gloss"] for event in evidence])
        cases.append(
            case(
                f"{category.replace('_', '-')}-{number:02d}",
                category,
                hearing,
                glosses,
                intended,
                "synthetic",
                evidence,
                list(intended),
            )
        )
    return cases


def generated_swaps(
    vocabulary: list[str], decoy: bool, count: int, rng: random.Random
) -> list[Case]:
    """Half plausible confusions, half random signs, all inside the substitution bounds."""
    bounds = substitution_bounds()
    slots = [
        (hearing, list(glosses), i) for hearing, glosses, _ in CLEAN for i in range(len(glosses))
    ]
    rng.shuffle(slots)
    category = "swap_decoy" if decoy else "swap_help"
    cases: list[Case] = []
    for number in range(1, count + 1):
        want_plausible = number <= count // 2
        while True:
            hearing, intended, index = slots.pop()
            sign = intended[index]
            options = [g for g in PLAUSIBLE.get(sign, []) if g not in intended]
            if want_plausible and not options:
                continue
            pool = options if want_plausible else [g for g in vocabulary if g not in intended]
            other = rng.choice(pool)
            break
        top1 = round(rng.uniform(0.40, 0.58), 3)
        other_score = round(top1 - rng.uniform(0.01, 0.07), 3)
        if not within_bounds(top1, other_score, bounds):
            raise ValueError(f"generated swap outside bounds: {top1} {other_score}")
        evidence = [confident(g, intended) for g in intended]
        if decoy:
            evidence[index] = uncertain(sign, other, top1, other_score, intended)
        else:
            evidence[index] = uncertain(other, sign, top1, other_score, intended)
        kind = "plausible" if want_plausible else "random"
        cases.append(
            case(
                f"{category.replace('_', '-')}-gen-{number:02d}",
                category,
                hearing,
                collapse([event["gloss"] for event in evidence]),
                intended,
                f"synthetic:generated:{kind}:seed{SEED}",
                evidence,
                list(intended),
            )
        )
    return cases


def perturbed_cases(vocabulary: list[str], rng: random.Random) -> list[Case]:
    pool = [(h, g) for h, g, _ in CLEAN if len(g) >= 2]
    cases: list[Case] = []
    for kind in ("insert", "substitute", "delete"):
        for number in range(1, PERTURBED_PER_KIND + 1):
            hearing, intended = pool[rng.randrange(len(pool))]
            glosses = list(intended)
            position = rng.randrange(len(glosses))
            noise = rng.choice([g for g in vocabulary if g not in intended])
            if kind == "insert":
                glosses.insert(rng.randrange(len(glosses) + 1), noise)
            elif kind == "substitute":
                glosses[position] = noise
            else:
                del glosses[position]
            cases.append(
                case(
                    f"perturbed-{kind}-{number:02d}",
                    f"perturbed_{kind}",
                    hearing,
                    collapse(glosses),
                    list(intended),
                    f"perturbation:seed{SEED}",
                )
            )
    return cases


def build() -> list[Case]:
    vocabulary: list[str] = json.loads(VOCABULARY.read_text(encoding="utf-8"))[
        "class_index_to_gloss"
    ]
    rng = random.Random(SEED)
    cases: list[Case] = []
    for number, (hearing, glosses, category) in enumerate(CLEAN, 1):
        cases.append(
            case(f"{category}-{number:02d}", category, hearing, glosses, glosses, "handwritten")
        )
    for number, (hearing, glosses) in enumerate(MISMATCH, 1):
        cases.append(
            case(
                f"mismatch-{number:02d}",
                "context_mismatch",
                hearing,
                glosses,
                glosses,
                "handwritten",
            )
        )
    cases += pilot_cases()
    cases += swap_cases(SWAP_HELP, "swap_help", decoy=False)
    cases += swap_cases(SWAP_DECOY, "swap_decoy", decoy=True)
    generator = random.Random(SEED + 1)
    cases += generated_swaps(vocabulary, decoy=True, count=GENERATED_DECOYS, rng=generator)
    cases += generated_swaps(vocabulary, decoy=False, count=GENERATED_HELP, rng=generator)
    cases += perturbed_cases(vocabulary, rng)
    known = set(vocabulary)
    for item in cases:
        signs = set(item["glosses"]) | set(item["intended"])
        for event in item["evidence"] or []:
            signs |= {label for label, _ in event["topK"]}
        unknown = signs - known
        if unknown:
            raise ValueError(f"{item['id']} uses glosses outside the vocabulary: {sorted(unknown)}")
    ids = [item["id"] for item in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ids")
    return cases


def main() -> int:
    cases = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    counts: dict[str, int] = {}
    for item in cases:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    print(f"Wrote {OUTPUT}: {len(cases)} cases {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
