#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit one or more real Python repositories with the deterministic GraphRAG stack."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graphrag_audit.communities import LeidenDetector  # noqa: E402
from graphrag_audit.extract import extract_repository  # noqa: E402
from graphrag_audit.graph import KnowledgeGraph  # noqa: E402
from graphrag_audit.summarize import summarize_communities  # noqa: E402


def audit(repo: str) -> dict:
    path = Path(repo).resolve()
    corpus = extract_repository(path)
    graph = KnowledgeGraph().from_corpus(corpus)
    hierarchy = LeidenDetector().detect(graph)
    reports = summarize_communities(hierarchy, corpus)

    degree = sorted(
        ((node, graph.degree(node)) for node in graph.nodes),
        key=lambda item: (-item[1], item[0]),
    )
    claims_by_kind = Counter(claim.kind for claim in corpus.claims)
    files = sorted({unit.path for unit in corpus.text_units})
    risk_reports = [report for report in reports.values() if report.risks]
    return {
        "repo": str(path),
        "files": len(files),
        "text_units": len(corpus.text_units),
        "entities": len(corpus.entities),
        "relationships": len(corpus.relationships),
        "claims": len(corpus.claims),
        "claims_by_kind": dict(sorted(claims_by_kind.items())),
        "graph_edges": graph.edge_count,
        "communities": len(hierarchy.communities),
        "levels": len(hierarchy.levels),
        "modularity": round(hierarchy.modularity, 6),
        "community_method": hierarchy.method,
        "community_reports": len(reports),
        "reports_with_risks": len(risk_reports),
        "top_entities_by_degree": [
            {"id": node, "degree": round(value, 3)} for node, value in degree[:10]
        ],
        "top_risks": [
            {
                "text": claim.text,
                "kind": claim.kind,
                "sources": list(claim.source_ids[:3]),
            }
            for claim in corpus.claims[:20]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", nargs="+", required=True)
    parser.add_argument("--out", default=str(ROOT / "experiments" / "real_repo_audit.json"))
    args = parser.parse_args()

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": (
            "Deterministic Python-AST extraction and Louvain/Leiden communities. "
            "Risk claims come from regex patterns, not an LLM judge. No model was called."
        ),
        "repos": [audit(repo) for repo in args.repo],
    }
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("| Repo | Files | Entities | Edges | Claims | Communities | Modularity | Method |")
    print("|---|---:|---:|---:|---:|---:|---:|---|")
    for item in result["repos"]:
        name = Path(item["repo"]).name
        print(
            f"| {name} | {item['files']} | {item['entities']} | {item['graph_edges']} | "
            f"{item['claims']} | {item['communities']} | {item['modularity']:.4f} | "
            f"{item['community_method']} |"
        )
    print(f"\nwrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
