#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Query the sample GraphRAG index from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graphrag_audit.communities import LeidenDetector  # noqa: E402
from graphrag_audit.extract import extract_repository  # noqa: E402
from graphrag_audit.graph import KnowledgeGraph  # noqa: E402
from graphrag_audit.query import GraphRAG  # noqa: E402
from graphrag_audit.summarize import summarize_communities  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--repo", default=str(ROOT / "data" / "sample_repo"))
    parser.add_argument("--mode", choices=["local", "global"], default="global")
    args = parser.parse_args()

    corpus = extract_repository(args.repo)
    graph = KnowledgeGraph().from_corpus(corpus)
    hierarchy = LeidenDetector().detect(graph)
    reports = summarize_communities(hierarchy, corpus)
    result = GraphRAG(corpus, graph, reports).query(args.question, mode=args.mode)
    print(result.answer)
    print(f"\nCitations: {', '.join(result.citations)}")
    if result.communities:
        print(f"Communities: {', '.join(result.communities)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
