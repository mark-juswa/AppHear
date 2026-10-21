"""Build the sentence-assist gloss lexicon from the recognizer's own label manifest.

The lexicon lists, for every recognizer gloss, the English word forms a rendering may use for
that sign. The grounding validator accepts a rendered word only when it is a form of a signed
gloss, a closed-class grammar word, or an allowed inferred pronoun, so this file defines what
"adds no content" means. Forms deliberately exclude comparatives/superlatives and possessives,
which add meaning. Rebuild with:

    python -m tools.sentence_assist.build_lexicon
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ASSETS = Path("android/app/src/main/assets")
VOCABULARY_ASSET = "phase4a_gate2_recognizer_parity/manifest.json"
OUTPUT = ASSETS / "sentence_assist" / "lexicon_v1.json"

# Closed-class words a rendering may add without a sign: articles, copula/auxiliaries,
# infinitive/locative particles and dummy subjects. Negation is NOT here: "not" requires NO,
# NEVER, CANNOT or DONTKNOW to have been signed.
GRAMMAR_WORDS = sorted(
    {
        "a", "an", "the", "am", "is", "are", "was", "were", "be", "been", "being",
        "do", "does", "did", "to", "of", "at", "in", "on", "it", "there", "will", "would",
        "and", "'s", "'ve", "'d",
    }
)  # fmt: skip
# Subject/object pronouns a rendering may infer (the vocabulary has no I/ME sign). Possessives
# are excluded: "my father" asserts possession that nobody signed.
INFERABLE_PRONOUNS = sorted({"i", "me", "you", "we", "us"})

EXPLICIT: dict[str, list[str]] = {
    "ABOUT2": ["about"], "AND": ["and"], "AT": ["at"], "BECAUSE": ["because"],
    "BETWEEN": ["between"], "BOTH": ["both"], "BUT": ["but"], "EACH": ["each"],
    "ENOUGH": ["enough"], "FEW": ["few"], "FOR": ["for"], "FROM": ["from"], "IF": ["if"],
    "IN": ["in"], "ON": ["on"], "OR": ["or"], "OVER": ["over"], "TO": ["to"],
    "UNDER": ["under"], "WITH": ["with"], "WHILE": ["while"], "THEN": ["then"],
    "WHEN": ["when"], "WHERE": ["where"], "WHICH": ["which"], "WHO": ["who"], "WHY": ["why"],
    "WHAT1": ["what"], "HOW1": ["how"], "YOU": ["you"], "YOUR": ["your", "yours"],
    "WE": ["we"], "US": ["us"], "OUR": ["our", "ours"], "THEY1": ["they", "them"],
    "ALL": ["all"], "ANY": ["any"], "SOME": ["some"], "MANY": ["many"], "MUCH": ["much"],
    "MORE": ["more"], "MOST": ["most"], "VERY": ["very"], "ONE": ["one"],
    "ALWAYS": ["always"], "NEVER": ["never"], "OFTEN": ["often"], "SOMETIMES": ["sometimes"],
    "NOW": ["now"], "STILL": ["still"], "HERE": ["here"], "AGAIN": ["again"],
    "TODAY": ["today"], "TOMORROW": ["tomorrow"], "YESTERDAY": ["yesterday"],
    "YES": ["yes", "yeah"], "NO": ["no", "not"], "CANNOT": ["can not"],
    "DONTKNOW": ["do not know"], "TOOMUCH": ["too much"], "HELLO": ["hello", "hi", "hey"],
    "BYE": ["bye", "goodbye", "good bye"], "CONGRATULATIONS": ["congratulations", "congrats"],
    "PLEASE": ["please"], "SORRY": ["sorry"], "WELCOME2": ["welcome"], "RIGHT3": ["right"],
    "LAST": ["last"], "FIRST": ["first"], "NEXT": ["next"], "SAME2": ["same"],
    "SPECIAL1": ["special"], "FREE": ["free"], "WHOLE": ["whole"],
    "IMPORTANT": ["important"], "DIFFERENT": ["different"],
    "CONFUSED1": ["confused", "confusing", "confuse", "confuses"], "SLOW": ["slow", "slowly"],
    "PEOPLE": ["people"], "PERSON": ["person", "persons", "people"],
    "CLOTHES": ["clothes"], "CHILD": ["child", "children"], "MAN": ["man", "men"],
    "WIFE": ["wife", "wives"], "KID": ["kid", "kids"],
}  # fmt: skip

ADJECTIVES = {
    "BAD", "BIG", "BUSY", "COLD", "EASY", "FAST", "GOOD", "HAPPY", "HARD", "HOT", "NEW",
    "NICE", "OLD", "READY", "SAD", "SICK", "SMALL", "STRONG", "SURE", "TIRED", "YOUNG",
}  # fmt: skip
NOUNS = {
    "AFTERNOON", "BABY1", "BAG2", "BED2", "BOOK", "BREAKFAST1", "BROTHER", "CAKE", "CAR",
    "CHAIR", "CITY2", "COMPUTER", "COUNTRY", "DAY", "DINNER1", "DOOR", "FAMILY", "FATHER",
    "FRIEND", "GIFT", "HOME", "HOSPITAL1", "HOUR", "HOUSE", "HUSBAND", "KEY", "LETTER2",
    "LUNCH1", "MEAT1", "MONEY1", "MONTH", "MORNING", "MOTHER", "MOUTH", "MOVIE1", "NIGHT1",
    "OFFICE", "PAPER", "PARTY1", "RESTAURANT", "ROAD", "ROOM", "SCHOOL", "SISTER", "STREET",
    "STUDENT", "TABLE", "TEACHER", "TICKET", "TIME", "WATER", "WEEK", "WINDOW", "WORLD", "YEAR",
}  # fmt: skip
IRREGULAR: dict[str, list[str]] = {
    "become": ["became"], "buy": ["bought"], "come": ["came"], "drink": ["drank", "drunk"],
    "drive": ["drove", "driven"], "eat": ["ate", "eaten"], "feel": ["felt"],
    "find": ["found"], "get": ["got", "gotten"], "give": ["gave", "given"],
    "go": ["went", "gone"], "have": ["has", "had"], "hear": ["heard"], "keep": ["kept"],
    "know": ["knew", "known"], "leave": ["left"], "make": ["made"], "mean": ["meant"],
    "meet": ["met"], "pay": ["paid"], "run": ["ran"], "see": ["saw", "seen"],
    "sell": ["sold"], "send": ["sent"], "show": ["shown"], "sit": ["sat"],
    "sleep": ["slept"], "stand": ["stood"], "take": ["took", "taken"],
    "teach": ["taught"], "tell": ["told"], "think": ["thought"], "write": ["wrote", "written"],
}  # fmt: skip
DOUBLE_FINAL = {"grab", "shop", "run", "sit", "cut", "put", "get"}
NO_REGULAR_PAST = {"cut", "put", "read", "hit"}


def base_word(gloss: str) -> str:
    return re.sub(r"\d+$", "", gloss).lower()


def third_person(word: str) -> str:
    if word.endswith(("s", "x", "z", "ch", "sh", "o")):
        return word + "es"
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def noun_forms(word: str) -> list[str]:
    return [word, third_person(word)]


def verb_forms(word: str) -> list[str]:
    forms = [word, third_person(word)]
    if word in DOUBLE_FINAL:
        stem = word + word[-1]
        forms.append(stem + "ing")
        if word not in NO_REGULAR_PAST and word not in IRREGULAR:
            forms.append(stem + "ed")
    else:
        if word.endswith("ie"):
            forms.append(word[:-2] + "ying")
        elif word.endswith("e") and not word.endswith(("ee", "ye", "oe")):
            forms.append(word[:-1] + "ing")
        else:
            forms.append(word + "ing")
        if word not in NO_REGULAR_PAST and word not in IRREGULAR:
            if word.endswith("e"):
                forms.append(word + "d")
            elif len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
                forms.append(word[:-1] + "ied")
            else:
                forms.append(word + "ed")
    forms.extend(IRREGULAR.get(word, []))
    return forms


def forms_for(gloss: str) -> list[str]:
    if gloss in EXPLICIT:
        return EXPLICIT[gloss]
    word = base_word(gloss)
    if gloss in ADJECTIVES:
        return [word]
    if gloss in NOUNS:
        return noun_forms(word)
    # Remaining glosses are verbs or verb/noun pairs (WORK, CALL1, DRINK2): verb forms cover
    # the plural noun spelling too.
    return verb_forms(word)


def build(vocabulary_path: Path) -> dict[str, object]:
    raw = vocabulary_path.read_bytes()
    glosses: list[str] = json.loads(raw)["class_index_to_gloss"]
    unknown = sorted((set(EXPLICIT) | ADJECTIVES | NOUNS) - set(glosses))
    if unknown:
        raise ValueError(f"Lexicon tables name glosses outside the vocabulary: {unknown}")
    return {
        "schemaVersion": 1,
        "lexiconVersion": "v1",
        "vocabularyAsset": VOCABULARY_ASSET,
        "vocabularySha256": hashlib.sha256(raw).hexdigest(),
        "grammarWords": GRAMMAR_WORDS,
        "inferablePronouns": INFERABLE_PRONOUNS,
        "glosses": {gloss: sorted(set(forms_for(gloss))) for gloss in glosses},
    }


def main() -> int:
    lexicon = build(ASSETS / VOCABULARY_ASSET)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(lexicon, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(lexicon['glosses'])} glosses)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
