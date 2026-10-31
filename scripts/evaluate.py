#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Evaluate global GraphRAG against flat vector RAG."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graphrag_audit.eval import generate_questions, run_evaluation  # noqa: E402
from graphrag_audit.extract import extract_repository  # noqa: E402
from graphrag_audit.graph import KnowledgeGraph  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(ROOT / "data" / "sample_repo"))
    parser.add_argument("--questions", type=int, default=100)
    parser.add_argument(
        "--out", default=str(ROOT / "experiments" / "eval_results.json")
    )
    args = parser.parse_args()

    result = run_evaluation(args.repo, n=args.questions)
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    corpus = extract_repository(args.repo)
    graph = KnowledgeGraph().from_corpus(corpus)
    questions = generate_questions(corpus, graph, args.questions)
    questions_path = ROOT / "data" / "questions_100.jsonl"
    questions_path.write_text(
        "\n".join(json.dumps({"id": f"q-{i+1:03d}", "question": q}) for i, q in enumerate(questions))
        + "\n",
        encoding="utf-8",
    )

    metrics = ["comprehensiveness", "diversity", "empowerment", "directness"]
    print("| Metric | GraphRAG | Flat vector RAG |")
    print("|---|---:|---:|")
    for metric in metrics:
        print(f"| {metric} | {result['graph'][metric]:.2f} | {result['flat'][metric]:.2f} |")
    print(f"| average | {result['graph_average']:.2f} | {result['flat_average']:.2f} |")
    print(f"\nGraphRAG wins: {result['graph_wins']}/{result['questions']} ({result['win_rate']:.1%})")
    print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
