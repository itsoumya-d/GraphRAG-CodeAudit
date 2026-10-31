# SPDX-License-Identifier: MIT
"""Core GraphRAG data types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TextUnit:
    id: str
    path: str
    start_line: int
    end_line: int
    text: str


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    type: str
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Relationship:
    source: str
    target: str
    type: str
    weight: float = 1.0
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    kind: str
    entity_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()


@dataclass
class Corpus:
    text_units: list[TextUnit] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)


@dataclass(frozen=True)
class Community:
    id: str
    level: int
    members: tuple[str, ...]
    parent: str | None = None
    children: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommunityReport:
    community_id: str
    level: int
    title: str
    summary: str
    entities: tuple[str, ...]
    risks: tuple[str, ...]
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass
class QueryResult:
    answer: str
    citations: list[str]
    entities: list[str] = field(default_factory=list)
    communities: list[str] = field(default_factory=list)
