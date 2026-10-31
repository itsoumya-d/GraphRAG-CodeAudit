# SPDX-License-Identifier: MIT
"""Local entity search and global community-report search."""

from __future__ import annotations

from collections import defaultdict
import re

from .graph import KnowledgeGraph
from .index import tokenize
from .types import CommunityReport, Corpus, QueryResult


class LocalSearch:
    def __init__(self, corpus: Corpus, graph: KnowledgeGraph):
        self.corpus = corpus
        self.graph = graph
        self.entities = {entity.id: entity for entity in corpus.entities}
        self.text = {unit.id: unit.text for unit in corpus.text_units}
        self.entity_text: dict[str, str] = {}
        for entity in corpus.entities:
            body = [entity.name, entity.type]
            body.extend(self.text.get(source, "") for source in entity.source_ids)
            self.entity_text[entity.id] = " ".join(body).lower()
        self.claims_by_entity: dict[str, list] = defaultdict(list)
        for claim in corpus.claims:
            for entity_id in claim.entity_ids:
                self.claims_by_entity[entity_id].append(claim)

    def query(self, question: str, top_k: int = 5) -> QueryResult:
        tokens = set(tokenize(question))
        scored = []
        for entity in self.corpus.entities:
            text = self.entity_text[entity.id]
            score = sum(3 if token in entity.name.lower() else 1 for token in tokens if token in text)
            if score:
                scored.append((score, entity.id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        seeds = [entity_id for _, entity_id in scored[:top_k]]
        expanded = set(seeds)
        for seed in seeds:
            for neighbor in sorted(self.graph.neighbors(seed), key=lambda n: (-self.graph.neighbors(seed)[n], n))[:4]:
                expanded.add(neighbor)

        risks = []
        citations = set()
        names = []
        for entity_id in sorted(expanded):
            entity = self.entities.get(entity_id)
            if not entity:
                continue
            names.append(entity.name)
            citations.update(entity.source_ids)
            for claim in self.claims_by_entity.get(entity_id, []):
                risks.append(claim.text)
                citations.update(claim.source_ids)
        unique_risks = sorted(set(risks))[:8]
        answer = (
            f"Local GraphRAG around {', '.join(names[:8]) or 'the query'}: "
            f"{len(unique_risks)} risk signal(s). "
            + ("Risks: " + "; ".join(unique_risks) + ". " if unique_risks else "")
            + f"Sources: {', '.join(sorted(citations)[:12])}"
        )
        return QueryResult(
            answer=answer,
            citations=sorted(citations),
            entities=sorted(expanded),
        )


class GlobalSearch:
    def __init__(self, reports: dict[str, CommunityReport]):
        self.reports = reports

    def query(self, question: str, top_k: int = 3) -> QueryResult:
        tokens = set(tokenize(question))
        scored = []
        for report in self.reports.values():
            text = " ".join([report.title, report.summary, *report.risks]).lower()
            score = sum(1 for token in tokens if token in text)
            scored.append((score, report))
        scored.sort(key=lambda item: (-item[0], item[1].community_id))
        selected = [report for _, report in scored[:top_k]]
        if not selected:
            return QueryResult(answer="No community reports available.", citations=[])

        evidence = []
        for report in selected:
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.])\s+", report.summary)
                if sentence.strip()
            ]
            relevant = [
                sentence
                for sentence in sentences
                if tokens.intersection(tokenize(sentence))
            ]
            evidence.extend((relevant or sentences)[:2])

        risks = sorted({risk for report in selected for risk in report.risks})[:6]
        citations = sorted({source for report in selected for source in report.source_ids})
        answer = (
            f"Global GraphRAG synthesized {len(selected)} community report(s). "
            + " ".join(evidence[:6])
            + (" Key risks: " + "; ".join(risks) + "." if risks else "")
            + f" Sources: {', '.join(citations[:12])}"
        )
        return QueryResult(
            answer=answer,
            citations=citations,
            communities=[report.community_id for report in selected],
        )


class GraphRAG:
    def __init__(self, corpus: Corpus, graph: KnowledgeGraph, reports: dict[str, CommunityReport]):
        self.local = LocalSearch(corpus, graph)
        self.global_search = GlobalSearch(reports)

    def query(self, question: str, mode: str = "global") -> QueryResult:
        if mode == "local":
            return self.local.query(question)
        if mode == "global":
            return self.global_search.query(question)
        raise ValueError("mode must be local or global")
