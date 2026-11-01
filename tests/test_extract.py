# SPDX-License-Identifier: MIT
import tempfile
import unittest
from pathlib import Path

from graphrag_audit.extract import extract_repository
from graphrag_audit.graph import KnowledgeGraph

ROOT = Path(__file__).resolve().parent.parent / "data" / "sample_repo"


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.corpus = extract_repository(ROOT)

    def test_entities_and_text_units(self):
        names = {entity.name for entity in self.corpus.entities}
        self.assertIn("auth.py", names)
        self.assertIn("verify_password", names)
        self.assertIn("login", names)
        self.assertTrue(self.corpus.text_units)

    def test_security_claims_are_extracted(self):
        kinds = {claim.id.split(":")[-1] for claim in self.corpus.claims}
        for expected in {
            "hardcoded-secret",
            "sql-construction",
            "insecure-deserialization",
            "shell-injection",
            "command-execution",
            "weak-hash",
            "pii-logging",
        }:
            self.assertIn(expected, kinds)
        self.assertTrue(all(claim.source_ids for claim in self.corpus.claims))

    def test_comments_patterns_and_parameterized_sql_are_not_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "safe.py").write_text(
                "# shell=True is a comment, not a call\n"
                "PATTERN = re.compile(r\"shell\\s*=\\s*True\")\n"
                "cursor.execute(\"SELECT id FROM users WHERE id = ?\", (user_id,))\n",
                encoding="utf-8",
            )
            corpus = extract_repository(tmp)
        kinds = {claim.id.split(":")[-1] for claim in corpus.claims}
        self.assertNotIn("shell-injection", kinds)
        self.assertNotIn("sql-construction", kinds)

    def test_graph_builds(self):
        graph = KnowledgeGraph().from_corpus(self.corpus)
        self.assertGreater(len(graph.nodes), 10)
        self.assertGreater(graph.edge_count, 5)


if __name__ == "__main__":
    unittest.main()
