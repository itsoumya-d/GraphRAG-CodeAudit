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
| `extract.py` | Python AST entities/edges, risk claims, text units |
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
relationships, and 9 risk claims. The harness generates 100 sensemaking
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

## Tests

```bash
python -m unittest discover -s tests -v
```

15 tests cover graph weights and modularity, hierarchical communities,
deterministic Louvain, extraction of security/privacy claims, local/global
queries, the flat baseline, judge behaviour, the 100-question harness, and
SQLite persistence.

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
