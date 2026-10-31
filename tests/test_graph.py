# SPDX-License-Identifier: MIT
import unittest

from graphrag_audit.graph import KnowledgeGraph


class GraphTests(unittest.TestCase):
    def test_two_cliques_modularity(self):
        graph = KnowledgeGraph()
        for a, b in [("a", "b"), ("b", "c"), ("a", "c"), ("d", "e"), ("e", "f"), ("d", "f")]:
            graph.add_edge(a, b, "co_occurs", 1.0, ("u",))
        graph.add_edge("c", "d", "co_occurs", 0.1, ("u",))
        partition = {"a": "x", "b": "x", "c": "x", "d": "y", "e": "y", "f": "y"}
        self.assertGreater(graph.modularity(partition), 0.3)
        self.assertEqual(graph.edge_count, 7)
        self.assertEqual(set(graph.neighbors("a")), {"b", "c"})

    def test_edge_metadata(self):
        graph = KnowledgeGraph()
        graph.add_edge("a", "b", "imports", 1.0, ("u1",))
        graph.add_edge("b", "a", "calls", 2.0, ("u2",))
        self.assertEqual(graph.edge_types("a", "b"), ("calls", "imports"))
        self.assertEqual(set(graph.edge_source_ids("a", "b")), {"u1", "u2"})
        self.assertAlmostEqual(graph.degree("a"), 3.0)


if __name__ == "__main__":
    unittest.main()
