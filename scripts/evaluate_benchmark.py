from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict


def load_predictions(path: str):
    items = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            items[row["claim_id"]] = row
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--md-output", required=True)
    args = parser.parse_args()

    preds = load_predictions(args.predictions)
    strict_correct = 0
    relaxed_correct = 0
    total = 0
    confusion = defaultdict(Counter)
    per_claim = []

    claim_names = sorted([n for n in os.listdir(args.dataset) if n.startswith("claim ")], key=lambda x: int(x.split()[1]))
    for claim_name in claim_names:
        answer_path = os.path.join(args.dataset, claim_name, "answer.json")
        with open(answer_path, "r", encoding="utf-8") as f:
            answer = json.load(f)
        pred = preds[claim_name.replace(" ", "_")]
        predicted = pred["decision"]
        expected = answer["decision"]
        acceptable = answer.get("acceptable_decision")
        strict = predicted == expected
        relaxed = strict or (acceptable is not None and predicted == acceptable)
        strict_correct += int(strict)
        relaxed_correct += int(relaxed)
        total += 1
        confusion[expected][predicted] += 1
        per_claim.append(
            {
                "claim": claim_name,
                "predicted": predicted,
                "expected": expected,
                "acceptable_decision": acceptable,
                "strict_match": strict,
                "relaxed_match": relaxed,
                "prediction_explanation": pred["explanation"],
                "expected_explanation": answer.get("explanation"),
            }
        )

    strict_accuracy = strict_correct / total if total else 0.0
    relaxed_accuracy = relaxed_correct / total if total else 0.0
    payload = {
        "total": total,
        "strict_accuracy": strict_accuracy,
        "relaxed_accuracy": relaxed_accuracy,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "per_claim": per_claim,
    }

    os.makedirs(os.path.dirname(args.json_output), exist_ok=True)
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    with open(args.md_output, "w", encoding="utf-8") as f:
        f.write(f"# Benchmark Evaluation\n\n")
        f.write(f"- Total claims: {total}\n")
        f.write(f"- Strict accuracy: {strict_accuracy:.2%}\n")
        f.write(f"- Relaxed accuracy: {relaxed_accuracy:.2%}\n\n")
        f.write("## Confusion Matrix\n\n")
        for expected, row in sorted(confusion.items()):
            f.write(f"- {expected}: {dict(row)}\n")
        f.write("\n## Per-Claim Comparison\n\n")
        for row in per_claim:
            status = "✅" if row["relaxed_match"] else "❌"
            f.write(f"- {status} {row['claim']}: predicted={row['predicted']} expected={row['expected']} acceptable={row['acceptable_decision']}\n")
            f.write(f"  - predicted explanation: {row['prediction_explanation']}\n")
            f.write(f"  - expected explanation: {row['expected_explanation']}\n")

    print(json.dumps({"strict_accuracy": strict_accuracy, "relaxed_accuracy": relaxed_accuracy}, indent=2))


if __name__ == "__main__":
    main()
