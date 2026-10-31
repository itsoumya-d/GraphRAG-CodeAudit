# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path

from graphrag_audit.communities import LeidenDetector
from graphrag_audit.extract import extract_repository
from graphrag_audit.graph import KnowledgeGraph
from graphrag_audit.index import FlatVectorRAG
from graphrag_audit.query import GlobalSearch, LocalSearch
from graphrag_audit.summarize import summarize_communities

ROOT = Path(__file__).resolve().parent.parent / "data" / "sample_repo"


class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = extract_repository(ROOT)
        cls.graph = KnowledgeGraph().from_corpus(cls.corpus)
        cls.hierarchy = LeidenDetector().detect(cls.graph)
        cls.reports = summarize_communities(cls.hierarchy, cls.corpus)

    def test_local_search_finds_auth_risk(self):
        result = LocalSearch(self.corpus, self.graph).query("password hashing and secret risks")
        self.assertTrue(result.citations)
        self.assertTrue(any("auth.py" in citation for citation in result.citations))
        self.assertIn("risk", result.answer.lower())

    def test_global_search_uses_community_reports(self):
        result = GlobalSearch(self.reports).query("security risks across the repository", top_k=5)
        self.assertTrue(result.citations)
        self.assertTrue(result.communities)
        self.assertIn("community", result.answer.lower())

    def test_flat_rag_baseline(self):
        result = FlatVectorRAG(self.corpus.text_units).answer("sql query risk")
        self.assertIn("Sources:", result["answer"])
        self.assertTrue(result["citations"])


if __name__ == "__main__":
    unittest.main()
