# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path

from graphrag_audit.eval import run_evaluation
from graphrag_audit.extract import extract_repository
from graphrag_audit.index import tokenize
from graphrag_audit.judge import HeuristicJudge
from graphrag_audit.types import QueryResult

ROOT = Path(__file__).resolve().parent.parent / "data" / "sample_repo"


class EvalTests(unittest.TestCase):
    def test_judge_prefers_richer_answer(self):
        judge = HeuristicJudge(extract_repository(ROOT))
        query = "security risks in auth.py"
        weak = judge.evaluate(query, QueryResult(answer="unknown", citations=[]))
        strong = judge.evaluate(
            query,
            QueryResult(
                answer=(
                    "Security risks in auth.py: hardcoded secret and MD5 password hashing. "
                    "Fix by moving the secret to a secret manager, replacing MD5 with a "
                    "password KDF, and validating the login path. Sources: auth.py:1-18"
                ),
                citations=["auth.py:1-18"],
            ),
        )
        self.assertGreater(judge.average(strong), judge.average(weak))

    def test_full_evaluation_runs(self):
        result = run_evaluation(str(ROOT), n=20)
        self.assertEqual(result["questions"], 20)
        self.assertIn("comprehensiveness", result["graph"])
        self.assertIn("directness", result["flat"])
        self.assertGreaterEqual(result["win_rate"], 0.0)
        self.assertLessEqual(result["win_rate"], 1.0)
        self.assertEqual(len(result["details"]), 20)


if __name__ == "__main__":
    unittest.main()
