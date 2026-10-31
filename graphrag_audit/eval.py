# SPDX-License-Identifier: MIT
"""GraphRAG vs flat-vector RAG evaluation harness."""

from __future__ import annotations

from collections import defaultdict

from .communities import LeidenDetector
from .extract import extract_repository
from .graph import KnowledgeGraph
from .index import FlatVectorRAG
from .judge import HeuristicJudge
from .query import GlobalSearch
from .summarize import summarize_communities
from .types import Corpus, QueryResult


def generate_questions(corpus: Corpus, graph: KnowledgeGraph, n: int = 100) -> list[str]:
    modules = sorted({entity.name for entity in corpus.entities if entity.type == "module"})
    functions = sorted(
        {entity.name for entity in corpus.entities if entity.type in {"function", "class"}}
    )
    pairs = sorted(
        {
            (relationship.source.split(":")[-1], relationship.target.split(":")[-1])
            for relationship in corpus.relationships
            if relationship.source != relationship.target
        }
    )
    templates = [
        lambda m: f"What security risks exist in {m}?",
        lambda m: f"Summarize the main risks and dependencies of {m}.",
        lambda m: f"Which components should be reviewed before deploying {m}?",
        lambda f: f"What does {f} do and what risks does it carry?",
        lambda m: f"Which modules depend on {m}?",
    ]
    questions: list[str] = []
    seen = set()

    def add(question: str):
        if question not in seen and len(questions) < n:
            seen.add(question)
            questions.append(question)

    for template in templates[:3]:
        for module in modules:
            add(template(module))
    for template in templates[3:]:
        for name in functions:
            add(template(name))
    for source, target in pairs:
        add(f"How does {source} interact with {target}?")
    index = 0
    while len(questions) < n:
        module = modules[index % len(modules)] if modules else "the repository"
        add(f"Audit question {index + 1}: what should be reviewed in {module}?")
        index += 1
        if index > n * 4:
            break
    return questions


def run_evaluation(repo_path: str, n: int = 100) -> dict:
    corpus = extract_repository(repo_path)
    graph = KnowledgeGraph().from_corpus(corpus)
    hierarchy = LeidenDetector().detect(graph, resolution=1.0, max_levels=4)
    reports = summarize_communities(hierarchy, corpus)
    judge = HeuristicJudge(corpus)
    questions = generate_questions(corpus, graph, n)
    global_search = GlobalSearch(reports)
    flat = FlatVectorRAG(corpus.text_units)

    totals = {
        "graph": defaultdict(float),
        "flat": defaultdict(float),
    }
    wins = 0
    details = []
    for question in questions:
        graph_result = global_search.query(question, top_k=5)
        flat_answer = flat.answer(question)
        flat_result = QueryResult(
            answer=flat_answer["answer"],
            citations=flat_answer["citations"],
        )
        graph_scores = judge.evaluate(question, graph_result)
        flat_scores = judge.evaluate(question, flat_result)
        for metric, value in graph_scores.items():
            totals["graph"][metric] += value
        for metric, value in flat_scores.items():
            totals["flat"][metric] += value
        graph_avg = judge.average(graph_scores)
        flat_avg = judge.average(flat_scores)
        if graph_avg > flat_avg:
            wins += 1
        details.append(
            {
                "question": question,
                "graph": graph_scores,
                "flat": flat_scores,
                "graph_average": round(graph_avg, 2),
                "flat_average": round(flat_avg, 2),
                "graph_citations": len(graph_result.citations),
                "flat_citations": len(flat_result.citations),
            }
        )

    count = len(questions) or 1
    graph_metrics = {k: round(v / count, 2) for k, v in totals["graph"].items()}
    flat_metrics = {k: round(v / count, 2) for k, v in totals["flat"].items()}
    return {
        "repo": repo_path,
        "questions": len(questions),
        "community_method": hierarchy.method,
        "communities": len(hierarchy.communities),
        "graph": graph_metrics,
        "flat": flat_metrics,
        "graph_average": round(sum(graph_metrics.values()) / len(graph_metrics), 2),
        "flat_average": round(sum(flat_metrics.values()) / len(flat_metrics), 2),
        "graph_wins": wins,
        "win_rate": round(wins / count, 3),
        "details": details,
        "note": "Deterministic rubric judge on a synthetic repository; not the paper's LLM judge or dataset.",
    }
