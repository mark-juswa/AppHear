"""Character-level sequence diagnostics; no language correction or inferred boundaries."""

from __future__ import annotations

from typing import Any


def greedy_decode(ids: list[int], blank: int = 27) -> str:
    result = []
    previous = None
    for token in ids:
        if token != blank and token != previous:
            if not 0 <= token <= 26:
                raise ValueError("[fingerspelling/decode] Invalid character index")
            result.append(" " if token == 26 else chr(ord("A") + token))
        previous = token
    return "".join(result)


def alignment(reference: str, prediction: str) -> dict[str, Any]:
    """Levenshtein with deterministic MATCHâ†’SUBâ†’DELâ†’INS tie order."""
    n, m = len(reference), len(prediction)
    costs = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        costs[i][0] = i
    for j in range(m + 1):
        costs[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            costs[i][j] = min(
                costs[i - 1][j - 1] + (reference[i - 1] != prediction[j - 1]),
                costs[i - 1][j] + 1,
                costs[i][j - 1] + 1,
            )
    i, j = n, m
    operations = []
    while i or j:
        if i and j and costs[i][j] == costs[i - 1][j - 1] + (reference[i - 1] != prediction[j - 1]):
            operations.append(
                (
                    "M" if reference[i - 1] == prediction[j - 1] else "S",
                    reference[i - 1],
                    prediction[j - 1],
                )
            )
            i -= 1
            j -= 1
        elif i and costs[i][j] == costs[i - 1][j] + 1:
            operations.append(("D", reference[i - 1], ""))
            i -= 1
        else:
            operations.append(("I", "", prediction[j - 1]))
            j -= 1
    operations.reverse()
    return {
        "substitutions": sum(o[0] == "S" for o in operations),
        "deletions": sum(o[0] == "D" for o in operations),
        "insertions": sum(o[0] == "I" for o in operations),
        "operations": operations,
    }


def summarize(rows: list[dict[str, str]], minimum_subgroup: int) -> dict[str, Any]:
    def score(group: list[dict[str, str]]) -> dict[str, Any]:
        aligned = [alignment(r["reference"], r["prediction"]) for r in group]
        chars = sum(len(r["reference"]) for r in group)
        counts = {
            k: sum(a[k] for a in aligned) for k in ["substitutions", "deletions", "insertions"]
        }
        return {
            "sequences": len(group),
            "reference_characters": chars,
            **counts,
            "cer": sum(counts.values()) / chars if chars else None,
            "exact_sequence_accuracy": (
                sum(r["reference"] == r["prediction"] for r in group) / len(group)
                if group
                else None
            ),
        }

    result = score(rows)
    result["signers"] = {
        signer: score([r for r in rows if r["signer_id"] == signer])
        for signer in sorted({r["signer_id"] for r in rows})
    }
    result["subgroups"] = {}
    for name in ["J", "Z", "REPEATED_LETTERS"]:
        group = [
            r
            for r in rows
            if (
                name in r["reference"]
                if name in {"J", "Z"}
                else any(
                    a == b and a != " "
                    for a, b in zip(r["reference"], r["reference"][1:], strict=False)
                )
            )
        ]
        value = score(group)
        value["interpretation_sample_count_sufficient"] = len(group) >= minimum_subgroup
        if name in {"J", "Z"}:
            ops = [
                op for r in group for op in alignment(r["reference"], r["prediction"])["operations"]
            ]
            expected = sum(op[1] == name for op in ops)
            value["reference_character_occurrences"] = expected
            value["aligned_character_recall"] = (
                sum(op[0] == "M" and op[1] == name for op in ops) / expected if expected else None
            )
        result["subgroups"][name] = value
    return result
