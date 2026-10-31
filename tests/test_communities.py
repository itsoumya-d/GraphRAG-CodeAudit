# SPDX-License-Identifier: MIT
import unittest

from graphrag_audit.communities import LeidenDetector, LouvainDetector
from graphrag_audit.graph import KnowledgeGraph


def two_cliques():
    graph = KnowledgeGraph()
    for a, b in [("a", "b"), ("b", "c"), ("a", "c"), ("d", "e"), ("e", "f"), ("d", "f")]:
        graph.add_edge(a, b, "co_occurs", 1.0, ("u",))
    graph.add_edge("c", "d", "co_occurs", 0.05, ("u",))
    return graph


class CommunityTests(unittest.TestCase):
    def test_louvain_finds_two_cliques(self):
        hierarchy = LouvainDetector().detect(two_cliques())
        self.assertGreaterEqual(len(hierarchy.levels), 1)
        final = hierarchy.levels[-1]
        self.assertEqual(len(set(final.values())), 2)
        self.assertGreater(hierarchy.modularity, 0.3)
        self.assertEqual(hierarchy.method, "louvain")

    def test_hierarchy_covers_every_node(self):
        hierarchy = LouvainDetector().detect(two_cliques())
        covered = {node for level in hierarchy.levels for node in level}
        self.assertEqual(covered, {"a", "b", "c", "d", "e", "f"})
        self.assertTrue(all(community.members for community in hierarchy.communities.values()))

    def test_leiden_falls_back_cleanly(self):
        hierarchy = LeidenDetector().detect(two_cliques())
        self.assertIn(hierarchy.method, {"leiden", "louvain-fallback"})
        self.assertGreaterEqual(len(hierarchy.levels), 1)

    def test_deterministic(self):
        first = LouvainDetector().detect(two_cliques())
        second = LouvainDetector().detect(two_cliques())
        self.assertEqual(first.levels, second.levels)


if __name__ == "__main__":
    unittest.main()
