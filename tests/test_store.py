# SPDX-License-Identifier: MIT
import tempfile
import unittest
from pathlib import Path

from graphrag_audit.extract import extract_repository
from graphrag_audit.store import SQLiteCorpusStore

ROOT = Path(__file__).resolve().parent.parent / "data" / "sample_repo"


class StoreTests(unittest.TestCase):
    def test_sqlite_roundtrip(self):
        corpus = extract_repository(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteCorpusStore(Path(directory) / "graph.db")
            store.save(corpus)
            loaded = store.load()
            store.close()
        self.assertEqual(len(loaded.text_units), len(corpus.text_units))
        self.assertEqual(len(loaded.entities), len(corpus.entities))
        self.assertEqual(len(loaded.claims), len(corpus.claims))


if __name__ == "__main__":
    unittest.main()
