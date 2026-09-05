"""Calcule des metriques a partir de predictions deja produites.

CSV requis: actual,predicted,confidence,latency_ms. Aucun modele ou dataset
n'est telecharge par cette commande.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def evaluate(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("Le jeu d'evaluation est vide")
    labels = sorted({r["actual"] for r in rows} | {r["predicted"] for r in rows})
    matrix = {actual: {pred: 0 for pred in labels} for actual in labels}
    review = 0
    latencies = []
    for row in rows:
        matrix[row["actual"]][row["predicted"]] += 1
        review += float(row["confidence"]) < 0.80
        latencies.append(float(row["latency_ms"]))
    per_class = {}
    weighted_f1 = 0.0
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[a][label] for a in labels if a != label)
        fn = sum(matrix[label][p] for p in labels if p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        support = sum(matrix[label].values())
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
        weighted_f1 += f1 * support
    correct = sum(matrix[label][label] for label in labels)
    return {
        "samples": len(rows),
        "class_distribution": dict(Counter(row["actual"] for row in rows)),
        "accuracy": correct / len(rows),
        "macro_f1": sum(v["f1"] for v in per_class.values()) / len(labels),
        "weighted_f1": weighted_f1 / len(rows),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "human_review_rate_at_0_80": review / len(rows),
        "mean_inference_ms": sum(latencies) / len(latencies),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    with args.predictions.open(encoding="utf-8", newline="") as stream:
        result = evaluate(list(csv.DictReader(stream)))
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
