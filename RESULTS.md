# GraphRAG-CodeAudit Results

## Environment

| Item | Value |
|---|---|
| Date | 2026-10-31 |
| OS | macOS (Apple Silicon) |
| Python | 3.14.0 |
| Leiden backend | Not installed; deterministic Louvain fallback |
| LLM judge | Not configured; deterministic rubric used |
| Corpus | `data/sample_repo` (synthetic) |

## Tests

```
python -m unittest discover -s tests -v
```

**15/15 tests pass.**

## Corpus

| Metric | Value |
|---|---:|
| Files | 5 |
| Text units | 5 |
| Entities | 27 |
| Relationships | 23 |
| Risk claims | 9 |
| Communities | 5 |
| Questions | 100 |

Extracted claim families include hardcoded secrets, weak password hashing, SQL
string construction, pickle deserialization, `shell=True`, `os.system`, and PII
logging.

## GraphRAG vs flat vector RAG

Command: `python scripts/evaluate.py`

Judge metrics are 1–10, averaged over 100 generated sensemaking questions.
Both systems use the same text units; GraphRAG answers from hierarchical
community reports, while the baseline retrieves the top-5 flat chunks.

| Metric | GraphRAG | Flat vector RAG |
|---|---:|---:|
| Comprehensiveness | 8.58 | 8.58 |
| Diversity | 10.00 | 10.00 |
| Empowerment | 4.01 | 2.28 |
| Directness | 7.72 | 7.40 |
| Average | 7.58 | 7.07 |

Head-to-head: **GraphRAG wins 64/100 (64.0%)**.

Interpretation:

- GraphRAG's community reports add recommended actions (parameterize SQL, avoid
  pickle, rotate secrets, redact PII), which raises empowerment.
- The map-reduce evidence selection keeps the global answer concise, raising
  directness.
- Comprehensiveness and diversity tie because the synthetic corpus has only five
  source files and both systems can cite all of them.
- This is a deterministic proxy, not an LLM judge. The paper's four-metric LLM
  head-to-head on a real enterprise corpus is **not** reproduced here and must
  not be claimed.

## Not executed

- **LLM-as-a-judge** on 100 global questions: needs Anthropic/Gemini/OpenAI
  credentials; the `HeuristicJudge` is the reproducible fallback.
- **Oracle Autonomous AI Database** persistence: schema provided, no database
  credentials.
- **3D WebGL community explorer / Hugging Face Space**: no HF authentication and
  no Mobbin MCP for the UI requirement.
- **Real Leiden partition**: install `.[leiden]` to run it; the committed method
  is `louvain-fallback`.

## Reproduce

```bash
cd repos/GraphRAG-CodeAudit
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/evaluate.py
python scripts/query.py "What security risks exist in files.py?" --mode global
```
