# SPDX-License-Identifier: MIT
import tempfile
import unittest
from pathlib import Path

from graphrag_audit.extract import extract_repository

ROOT = Path(__file__).resolve().parent.parent / "data" / "sample_repo_ts"


class TypeScriptExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = extract_repository(ROOT)
        cls.entities = {entity.id: entity for entity in cls.corpus.entities}

    def test_module_class_and_interface_entities(self):
        for expected in {
            "module:auth.ts",
            "class:auth.ts:AuthService",
            "interface:auth.ts:UserRecord",
            "method:auth.ts:AuthService.login",
            "method:auth.ts:AuthService.hashToken",
            "function:auth.ts:normalizeEmail",
            "function:auth.ts:auditLogin",
            "module:App.tsx",
            "function:App.tsx:App",
        }:
            self.assertIn(expected, self.entities)

    def test_inheritance_and_relative_import_edges(self):
        edges = {
            (relation.source, relation.target, relation.type)
            for relation in self.corpus.relationships
        }
        self.assertIn(
            ("class:auth.ts:AuthService", "external:BaseService", "inherits"), edges
        )
        self.assertIn(("module:auth.ts", "import:base", "imports"), edges)
        self.assertIn(("module:auth.ts", "import:crypto", "imports"), edges)
        self.assertIn(("module:legacy.js", "import:fs", "imports"), edges)
        self.assertIn(
            ("module:legacy.js", "import:child_process", "imports"), edges
        )
        self.assertIn(("module:re-export.ts", "import:base", "imports"), edges)

    def test_javascript_function_and_require_extraction(self):
        self.assertIn("function:legacy.js:render", self.entities)
        self.assertIn("function:legacy.js:run", self.entities)

    def test_claims_carry_entity_and_source_provenance(self):
        kinds = {claim.id.split(":")[-1] for claim in self.corpus.claims}
        for expected in {
            "dynamic-code-evaluation",
            "hardcoded-password",
            "weak-hash",
            "xss-sink",
            "command-injection",
        }:
            self.assertIn(expected, kinds)
        for claim in self.corpus.claims:
            self.assertTrue(claim.source_ids)
            for entity_id in claim.entity_ids:
                self.assertIn(entity_id, self.entities)

    def test_comments_are_not_scanned_for_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "safe.ts").write_text(
                "// eval('commented')\n"
                "/* document.body.innerHTML = value; */\n"
                "export function run(value: string) {\n"
                "  return eval('live');\n"
                "}\n",
                encoding="utf-8",
            )
            corpus = extract_repository(tmp)
        kinds = [claim.id.split(":")[-1] for claim in corpus.claims]
        self.assertEqual(kinds.count("dynamic-code-evaluation"), 1)
        self.assertNotIn("xss-sink", kinds)

    def test_text_units_cover_every_source_line(self):
        paths = {unit.path for unit in self.corpus.text_units}
        self.assertEqual(
            paths, {"auth.ts", "base.ts", "legacy.js", "App.tsx", "re-export.ts"}
        )


if __name__ == "__main__":
    unittest.main()
