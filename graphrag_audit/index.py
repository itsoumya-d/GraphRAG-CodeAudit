# SPDX-License-Identifier: MIT
"""Flat vector RAG baseline with deterministic hashed embeddings."""

from __future__ import annotations

import hashlib
import math
import re

from .types import TextUnit

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "what",
    "which", "how", "are", "was", "were", "does", "did", "can", "should",
    "main", "summary", "summarize", "explain",
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOPWORDS]


class FlatVectorRAG:
    def __init__(self, text_units: list[TextUnit], dimensions: int = 256):
        self.dimensions = dimensions
        self.units = list(text_units)
        self.vectors = [self.embed(unit.text) for unit in self.units]

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def search(self, question: str, top_k: int = 5):
        query = self.embed(question)
        scored = []
        for unit, vector in zip(self.units, self.vectors):
            score = sum(a * b for a, b in zip(query, vector))
            scored.append((score, unit))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return scored[:top_k]

    def answer(self, question: str, top_k: int = 5):
        results = self.search(question, top_k)
        query_tokens = set(tokenize(question))
        sentences = []
        citations = []
        for _, unit in results:
            citations.append(unit.id)
            for sentence in re.split(r"(?<=[.!?])\s+|\n", unit.text):
                sentence = sentence.strip()
                if sentence and query_tokens.intersection(tokenize(sentence)):
                    sentences.append(sentence)
        text = " ".join(sentences[:6]) or "No relevant flat chunks found."
        return {
            "answer": f"Flat vector RAG: {text} Sources: {', '.join(sorted(set(citations)))}",
            "citations": sorted(set(citations)),
        }
