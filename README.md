# GraphRAG-CodeAudit

Local-to-global GraphRAG for codebases and compliance audits.

The pipeline extracts typed entities, relationships, and risk claims from a
repository, builds an undirected weighted knowledge graph, partitions it into
hierarchical communities, and answers questions through two engines:

- **Local search** — entity neighbourhood fan-out with claim and source
  drill-through.
- **Global search** — map-reduce over community reports for repository-wide
  sensemaking.

A flat hashed-embedding RAG baseline is included so the global engine can be
compared under the same text units and citations.

Research basis: *From Local to Global: A Graph RAG Approach to Query-Focused
Summarization* (Microsoft Research, arXiv:2404.16130).

## Pipeline

```
repository
   │  AST + regex extraction
   ▼
entities / typed edges / claims / text units
   │
   ▼
weighted undirected graph
   │  Louvain (default) or Leiden (optional)
   ▼
hierarchical communities  ──▶  bottom-up community reports
   │                                   │
   ▼                                   ▼
local entity search          global map-reduce search
```

| Module | Responsibility |
|---|---|
| `extract.py` | Python AST and tree-sitter TS/JS/TSX entities/edges, risk claims, text units |
| `graph.py` | Undirected weighted graph + modularity |
| `communities.py` | Deterministic Louvain hierarchy; optional reference Leiden |
| `summarize.py` | Bottom-up reports with risks, dependencies, recommended actions |
| `query.py` | Local neighbourhood search and global report synthesis |
| `index.py` | Flat hashed-embedding vector RAG baseline |
| `judge.py` | Deterministic rubric judge (comprehensiveness/diversity/empowerment/directness) |
| `store.py` | SQLite persistence; Oracle schema in `sql/oracle_schema.sql` |

## Quick start

```bash
python -m pip install -e .
python scripts/evaluate.py
python scripts/query.py "What security risks exist in auth.py?" --mode global
python scripts/query.py "password hashing risks" --mode local
```

Example:

```python
from graphrag_audit import (
    KnowledgeGraph, LeidenDetector, extract_repository, summarize_communities
)
from graphrag_audit.query import GraphRAG

corpus = extract_repository("data/sample_repo")
graph = KnowledgeGraph().from_corpus(corpus)
hierarchy = LeidenDetector().detect(graph)
reports = summarize_communities(hierarchy, corpus)
result = GraphRAG(corpus, graph, reports).query(
    "What security risks exist in auth.py?", mode="global"
)
print(result.answer)
print(result.citations)
```

If `igraph` and `leidenalg` are installed (`pip install -e ".[leiden]"`), the
detector uses the reference Leiden implementation for the first level. Otherwise
it falls back to the deterministic Louvain hierarchy and reports
`method="louvain-fallback"`.

## Measured evaluation

The synthetic sample repository has 5 files, 5 text units, 27 entities, 23
relationships, and 7 risk claims. The harness generates 100 sensemaking
questions and scores global GraphRAG against flat vector RAG with a deterministic
rubric judge:

| Metric | GraphRAG | Flat vector RAG |
|---|---:|---:|
| Comprehensiveness | 8.58 | 8.58 |
| Diversity | 10.00 | 10.00 |
| Empowerment | 4.01 | 2.28 |
| Directness | 7.72 | 7.40 |
| **Average** | **7.58** | **7.07** |

GraphRAG wins **64/100** questions. It gains on actionable empowerment and
directness; comprehensiveness and diversity tie because both systems can draw
from the same five source files in this tiny corpus.

This is a reproducible harness result on a synthetic repository, **not** a
replication of the paper's LLM-as-a-judge study on real enterprise corpora. See
[RESULTS.md](RESULTS.md) for the full methodology and limitations.

### Real repository audit

```bash
python scripts/audit_repo.py --repo ../HEROS-RL ../Reflexion-SWE .
```

The deterministic extractor was run on three real Python repositories on
2026-11-01. No model was called.

| Repository | Files | Entities | Edges | Claims | Communities | Modularity | Method |
|---|---:|---:|---:|---:|---:|---:|---|
| HEROS-RL | 22 | 129 | 304 | 1 | 30 | 0.6759 | louvain-fallback |
| Reflexion-SWE | 21 | 114 | 278 | 0 | 26 | 0.6545 | louvain-fallback |
| GraphRAG-CodeAudit (self) | 25 | 112 | 281 | 10 | 32 | 0.7001 | louvain-fallback |

The self-audit exposed a real false-positive class: the first run flagged the
extractor's own regex definitions and a comment containing `shell=True`. The
extractor now skips comment-only lines and `re.compile(...)` definitions, and
only flags SQL built from an f-string rather than every `execute(...)` call.
Parameterized SQL is no longer reported. Raw output:
`experiments/real_repo_audit.json`.

Boundary: Python AST plus tree-sitter TypeScript/JavaScript/TSX AST; risk
claims are regex patterns, not an LLM judge; the sample fixture repository is
intentionally vulnerable and its claims are expected.

## Language support

- **Python:** `ast`-based modules, classes, functions, imports, and inheritance.
- **TypeScript / TSX / JavaScript:** tree-sitter modules, classes, methods,
  functions, arrow-function constants, interfaces, ES imports, CommonJS
  `require`, and `extends` inheritance.
- Claims are scanned on non-comment lines with language-specific regexes; the
  TS/JS fixture in `data/sample_repo_ts` covers XSS sinks, interpolated shell
  commands, weak hashes, hardcoded passwords, and dynamic `eval`.
- No type resolution, call graph, or cross-file symbol binding is performed.

## Tests

```bash
python -m unittest discover -s tests -v
```

22 tests cover graph weights and modularity, hierarchical communities,
deterministic Louvain, Python and TypeScript/JavaScript extraction, provenance
for every claim, local/global queries, the flat baseline, judge behaviour, the
100-question harness, and SQLite persistence.

## Infrastructure status

- **Oracle Autonomous AI Database:** DDL is in `sql/oracle_schema.sql`; a live
  Oracle adapter requires database credentials and is not deployed here.
- **3D WebGL community explorer / Hugging Face Space:** not built; Hugging Face
  authentication and the Mobbin MCP were unavailable.
- **LLM-as-a-judge:** the harness accepts a judge implementation, but the
  measured table uses the deterministic rubric so it runs without API keys.
- **Leiden:** real Leiden is optional; the committed result uses the honest
  Louvain fallback.

## License

MIT. Copyright (c) 2024-2026 Soumya Debnath.
