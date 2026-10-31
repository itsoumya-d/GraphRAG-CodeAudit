# SPDX-License-Identifier: MIT
"""Deterministic rubric judge used for reproducible local evaluation.

This is not the paper's LLM-as-a-judge protocol. It is a transparent proxy that
scores comprehensiveness, diversity, empowerment, and directness from the answer
and its citations so the harness can be tested without API credentials.
"""

from __future__ import annotations

import re

from .index import tokenize
from .types import Corpus, QueryResult

ACTION_RE = re.compile(
    r"\b(fix|validate|sanitize|parameterize|encrypt|review|avoid|use|replace|"
    r"restrict|verify|audit|rotate|remove)\b",
    re.IGNORECASE,
)


class HeuristicJudge:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self.source_paths = {unit.id: unit.path for unit in corpus.text_units}

    def evaluate(self, question: str, result: QueryResult) -> dict[str, float]:
        answer = result.answer or ""
        query_tokens = set(tokenize(question))
        answer_tokens = set(tokenize(answer))
        coverage = (
            len(query_tokens & answer_tokens) / len(query_tokens) if query_tokens else 0.0
        )
        distinct_files = {self.source_paths.get(c, c) for c in result.citations}
        comprehensiveness = min(10.0, 1.0 + 6.0 * coverage + 1.0 * len(distinct_files))
        diversity = min(
            10.0,
            1.0 + 1.5 * len(set(result.citations)) + 1.0 * len(distinct_files),
        )
        actions = len(ACTION_RE.findall(answer))
        specificity = len(re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", answer))
        empowerment = min(10.0, 1.0 + 1.5 * actions + 0.05 * min(specificity, 60))
        words = len(re.findall(r"\S+", answer))
        length_score = 10.0 if 15 <= words <= 180 else max(1.0, 10.0 - abs(words - 90) / 30)
        directness = min(10.0, 0.6 * length_score + 4.0 * coverage)
        return {
            "comprehensiveness": round(comprehensiveness, 2),
            "diversity": round(diversity, 2),
            "empowerment": round(empowerment, 2),
            "directness": round(directness, 2),
        }

    @staticmethod
    def average(scores: dict[str, float]) -> float:
        return sum(scores.values()) / len(scores) if scores else 0.0
