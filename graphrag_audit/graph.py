# SPDX-License-Identifier: MIT
"""Undirected weighted knowledge graph."""

from __future__ import annotations

from collections import defaultdict
from typing import Hashable, Iterable

from .types import Corpus


class KnowledgeGraph:
    def __init__(self):
        self.nodes: set[str] = set()
        self._edges: dict[tuple[str, str], dict] = {}

    @staticmethod
    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def add_node(self, node: str) -> None:
        self.nodes.add(node)

    def add_edge(
        self,
        source: str,
        target: str,
        kind: str = "related",
        weight: float = 1.0,
        source_ids: Iterable[str] = (),
    ) -> None:
        if weight <= 0:
            return
        self.nodes.add(source)
        self.nodes.add(target)
        key = self._key(source, target)
        record = self._edges.setdefault(
            key, {"weight": 0.0, "types": set(), "source_ids": set()}
        )
        record["weight"] += float(weight)
        record["types"].add(kind)
        record["source_ids"].update(source_ids)

    def from_corpus(self, corpus: Corpus) -> "KnowledgeGraph":
        for entity in corpus.entities:
            self.add_node(entity.id)
        for relationship in corpus.relationships:
            self.add_edge(
                relationship.source,
                relationship.target,
                relationship.type,
                relationship.weight,
                relationship.source_ids,
            )

        mentions: dict[str, list[str]] = defaultdict(list)
        for entity in corpus.entities:
            for source_id in entity.source_ids:
                mentions[source_id].append(entity.id)
        for source_id, entities in mentions.items():
            entities = sorted(set(entities))
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    self.add_edge(
                        entities[i],
                        entities[j],
                        "co_occurs",
                        0.5,
                        (source_id,),
                    )
        return self

    def neighbors(self, node: str) -> dict[str, float]:
        output: dict[str, float] = {}
        for (a, b), record in self._edges.items():
            if a == node and b == node:
                continue
            if a == node:
                output[b] = output.get(b, 0.0) + record["weight"]
            elif b == node:
                output[a] = output.get(a, 0.0) + record["weight"]
        return output

    def degree(self, node: str) -> float:
        total = 0.0
        for (a, b), record in self._edges.items():
            if a == node and b == node:
                total += 2 * record["weight"]
            elif a == node or b == node:
                total += record["weight"]
        return total

    def adjacency(self) -> dict[str, dict[str, float]]:
        output: dict[str, dict[str, float]] = {node: {} for node in self.nodes}
        for (a, b), record in self._edges.items():
            output[a][b] = output[a].get(b, 0.0) + record["weight"]
            if a != b:
                output[b][a] = output[b].get(a, 0.0) + record["weight"]
        return output

    def edge_types(self, a: str, b: str) -> tuple[str, ...]:
        record = self._edges.get(self._key(a, b))
        return tuple(sorted(record["types"])) if record else ()

    def edge_source_ids(self, a: str, b: str) -> tuple[str, ...]:
        record = self._edges.get(self._key(a, b))
        return tuple(sorted(record["source_ids"])) if record else ()

    def modularity(
        self, partition: dict[Hashable, Hashable], resolution: float = 1.0
    ) -> float:
        if not self.nodes:
            return 0.0
        adjacency = self.adjacency()
        degree = {node: sum(adjacency[node].values()) for node in self.nodes}
        m2 = sum(degree.values())
        if m2 == 0:
            return 0.0
        inside: dict[Hashable, float] = defaultdict(float)
        totals: dict[Hashable, float] = defaultdict(float)
        for (a, b), record in self._edges.items():
            if a == b:
                if partition.get(a) == partition.get(b):
                    inside[partition[a]] += 2 * record["weight"]
                continue
            if partition.get(a) == partition.get(b):
                inside[partition[a]] += 2 * record["weight"]
        for node, value in degree.items():
            totals[partition.get(node)] += value
        return sum(
            inside[c] / m2 - resolution * (totals[c] / m2) ** 2 for c in totals
        )

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def edge_items(self):
        for (a, b), record in self._edges.items():
            yield a, b, record["weight"], tuple(sorted(record["types"]))
