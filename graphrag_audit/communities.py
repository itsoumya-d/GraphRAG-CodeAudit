# SPDX-License-Identifier: MIT
"""Hierarchical community detection.

The dependency-free path is a deterministic Louvain modularity optimiser with
resolution control and aggregation levels. `LeidenDetector` uses the reference
Leiden implementation when `igraph` and `leidenalg` are installed, and falls
back to the Louvain path with an explicit `method` marker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable

from .graph import KnowledgeGraph
from .types import Community


@dataclass
class CommunityHierarchy:
    levels: list[dict[str, str]] = field(default_factory=list)
    communities: dict[str, Community] = field(default_factory=dict)
    modularity: float = 0.0
    method: str = "louvain"

    def level_of(self, community_id: str) -> int:
        return self.communities[community_id].level

    def roots(self) -> list[Community]:
        return [c for c in self.communities.values() if c.parent is None]


def _local_moving(
    adjacency: dict[int, dict[int, float]],
    degree: dict[int, float],
    resolution: float,
) -> tuple[dict[int, int], bool]:
    communities = {node: node for node in adjacency}
    totals = dict(degree)
    m2 = sum(degree.values())
    if m2 == 0:
        return communities, False
    changed_any = False
    for _ in range(30):
        changed = False
        for node in sorted(adjacency):
            current = communities[node]
            k_i = degree[node]
            weights: dict[int, float] = {}
            for neighbor, weight in adjacency[node].items():
                if neighbor == node:
                    continue
                weights[communities[neighbor]] = weights.get(communities[neighbor], 0.0) + weight
            totals[current] -= k_i
            best = current
            best_gain = weights.get(current, 0.0) - resolution * totals[current] * k_i / m2
            for community, weight in sorted(weights.items()):
                gain = weight - resolution * totals[community] * k_i / m2
                if gain > best_gain + 1e-12 or (
                    abs(gain - best_gain) <= 1e-12 and community < best
                ):
                    best = community
                    best_gain = gain
            communities[node] = best
            totals[best] += k_i
            if best != current:
                changed = True
        if not changed:
            break
        changed_any = True
    return communities, changed_any


def _aggregate(
    adjacency: dict[int, dict[int, float]], partition: dict[int, int]
) -> tuple[dict[int, dict[int, float]], dict[int, float]]:
    labels = sorted(set(partition.values()), key=lambda label: min(
        node for node, value in partition.items() if value == label
    ))
    mapping = {label: index for index, label in enumerate(labels)}
    output: dict[int, dict[int, float]] = {index: {} for index in range(len(labels))}
    for node, neighbors in adjacency.items():
        source = mapping[partition[node]]
        for neighbor, weight in neighbors.items():
            if neighbor < node:
                continue
            target = mapping[partition[neighbor]]
            if source == target:
                output[source][source] = output[source].get(source, 0.0) + weight
            else:
                output[source][target] = output[source].get(target, 0.0) + weight
                output[target][source] = output[target].get(source, 0.0) + weight
    degree = {
        node: sum(neighbors.values()) + neighbors.get(node, 0.0)
        for node, neighbors in output.items()
    }
    return output, degree


class LouvainDetector:
    def detect(
        self,
        graph: KnowledgeGraph,
        resolution: float = 1.0,
        max_levels: int = 4,
    ) -> CommunityHierarchy:
        if not graph.nodes:
            return CommunityHierarchy([], {}, 0.0, "louvain")
        original = sorted(graph.nodes)
        index = {node: position for position, node in enumerate(original)}
        adjacency = {
            index[node]: {index[neighbor]: weight for neighbor, weight in neighbors.items()}
            for node, neighbors in graph.adjacency().items()
        }
        degree = {
            node: sum(neighbors.values()) + neighbors.get(node, 0.0)
            for node, neighbors in adjacency.items()
        }
        members: dict[int, list[str]] = {node: [original[node]] for node in adjacency}
        level_maps: list[dict[str, str]] = []

        for level in range(max_levels):
            partition, changed = _local_moving(adjacency, degree, resolution)
            if level > 0 and not changed:
                break

            groups: dict[int, list[int]] = {}
            for node in sorted(adjacency):
                groups.setdefault(partition[node], []).append(node)
            ordered = sorted(
                groups.values(),
                key=lambda nodes: min(min(members[node]) for node in nodes),
            )

            mapping: dict[str, str] = {}
            new_members: dict[int, list[str]] = {}
            for position, group in enumerate(ordered):
                community_id = f"L{level}-{position}"
                original_members = sorted(
                    member for node in group for member in members[node]
                )
                new_members[position] = original_members
                for member in original_members:
                    mapping[member] = community_id
            level_maps.append(mapping)
            if len(ordered) == 1:
                break

            label_to_new = {
                partition[node]: position
                for position, group in enumerate(ordered)
                for node in group
            }
            new_adjacency: dict[int, dict[int, float]] = {
                position: {} for position in range(len(ordered))
            }
            for source, neighbors in adjacency.items():
                source_community = label_to_new[partition[source]]
                for target, weight in neighbors.items():
                    if target < source:
                        continue
                    target_community = label_to_new[partition[target]]
                    if source_community == target_community:
                        new_adjacency[source_community][source_community] = (
                            new_adjacency[source_community].get(source_community, 0.0)
                            + weight
                        )
                    else:
                        new_adjacency[source_community][target_community] = (
                            new_adjacency[source_community].get(target_community, 0.0)
                            + weight
                        )
                        new_adjacency[target_community][source_community] = (
                            new_adjacency[target_community].get(source_community, 0.0)
                            + weight
                        )
            new_degree = {
                node: sum(neighbors.values()) + neighbors.get(node, 0.0)
                for node, neighbors in new_adjacency.items()
            }
            if len(new_adjacency) == len(adjacency):
                break
            adjacency = new_adjacency
            degree = new_degree
            members = new_members

        if not level_maps:
            level_maps = [{node: node for node in original}]
        final_partition = {node: level_maps[-1][node] for node in original}
        modularity = graph.modularity(final_partition, resolution)
        return CommunityHierarchy(
            level_maps,
            self._build_communities(level_maps),
            modularity,
            "louvain",
        )

    @staticmethod
    def _build_communities(level_maps: list[dict[str, str]]) -> dict[str, Community]:
        communities: dict[str, Community] = {}
        members_by_id: dict[str, list[str]] = {}
        for level, mapping in enumerate(level_maps):
            for node, community_id in mapping.items():
                members_by_id.setdefault(community_id, []).append(node)

        for level, mapping in enumerate(level_maps):
            for community_id in sorted(
                {value for value in mapping.values()}, key=lambda value: int(value.split("-")[1])
            ):
                members = tuple(sorted(members_by_id[community_id]))
                parent = None
                if level + 1 < len(level_maps):
                    parent = level_maps[level + 1][members[0]]
                children = tuple(
                    sorted(
                        child_id
                        for child_id, child in communities.items()
                        if child.parent == community_id
                    )
                )
                communities[community_id] = Community(
                    id=community_id,
                    level=level,
                    members=members,
                    parent=parent,
                    children=children,
                )
        # Children are assigned while iterating from shallow to deep, so rebuild
        # the tuple once all communities exist.
        children_map: dict[str, list[str]] = {}
        for community in communities.values():
            if community.parent:
                children_map.setdefault(community.parent, []).append(community.id)
        return {
            community.id: Community(
                id=community.id,
                level=community.level,
                members=community.members,
                parent=community.parent,
                children=tuple(sorted(children_map.get(community.id, []))),
            )
            for community in communities.values()
        }


class LeidenDetector:
    def __init__(self):
        self.method = "louvain-fallback"
        try:
            import igraph  # noqa: F401
            import leidenalg  # noqa: F401
        except ImportError:
            return
        self.method = "leiden"

    def detect(
        self,
        graph: KnowledgeGraph,
        resolution: float = 1.0,
        max_levels: int = 4,
    ) -> CommunityHierarchy:
        if self.method != "leiden":
            hierarchy = LouvainDetector().detect(graph, resolution, max_levels)
            hierarchy.method = "louvain-fallback"
            return hierarchy

        import igraph as ig
        import leidenalg as la

        original = sorted(graph.nodes)
        adjacency = graph.adjacency()
        index = {node: i for i, node in enumerate(original)}
        edges = []
        weights = []
        for source, neighbors in adjacency.items():
            for target, weight in neighbors.items():
                if source < target:
                    edges.append((index[source], index[target]))
                    weights.append(weight)
        ig_graph = ig.Graph(n=len(original), edges=edges, directed=False)
        partition = la.find_partition(
            ig_graph,
            la.RBConfigurationVertexPartition,
            weights=weights,
            resolution_parameter=resolution,
            seed=42,
        )
        mapping = {
            original[node]: f"L0-{community}"
            for community, members in enumerate(partition)
            for node in members
        }
        hierarchy = CommunityHierarchy(
            levels=[mapping],
            communities=LouvainDetector._build_communities([mapping]),
            modularity=graph.modularity(mapping, resolution),
            method="leiden",
        )
        return hierarchy
