# SPDX-License-Identifier: MIT
"""Bottom-up community report generation."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .communities import CommunityHierarchy
from .types import CommunityReport, Corpus

Summarizer = Callable[[str], str]


def summarize_communities(
    hierarchy: CommunityHierarchy, corpus: Corpus, llm: Summarizer | None = None
) -> dict[str, CommunityReport]:
    entities = {entity.id: entity for entity in corpus.entities}
    claims_by_entity: dict[str, list] = defaultdict(list)
    source_by_entity = {entity.id: set(entity.source_ids) for entity in corpus.entities}
    for claim in corpus.claims:
        for entity_id in claim.entity_ids:
            claims_by_entity[entity_id].append(claim)

    reports: dict[str, CommunityReport] = {}
    communities = sorted(
        hierarchy.communities.values(), key=lambda c: (-c.level, c.id)
    )
    for community in communities:
        entity_ids = [member for member in community.members if member in entities]
        names = [entities[member].name for member in entity_ids]
        types = sorted({entities[member].type for member in entity_ids})
        claims = [
            claim
            for member in entity_ids
            for claim in claims_by_entity.get(member, [])
        ]
        risks = sorted({claim.text for claim in claims})[:8]
        dependencies = sorted(
            {
                entities[member].name
                for member in entity_ids
                if entities[member].type in {"dependency", "module"}
            }
        )
        child_reports = [reports[child] for child in community.children if child in reports]
        child_text = " ".join(report.summary for report in child_reports[:3])
        risk_text = "; ".join(risks) if risks else "no high-signal risks extracted"
        recommendation = _recommendation(risk_text)
        summary = (
            f"Community {community.id} at level {community.level} contains "
            f"{len(entity_ids)} entities ({', '.join(types) or 'unknown'}). "
            f"Key risks: {risk_text}. "
            f"Recommended action: {recommendation} "
            f"Related components: {', '.join(names[:8]) or 'none'}. "
            f"{child_text}"
        ).strip()
        if llm is not None:
            try:
                summary = llm(summary).strip() or summary
            except Exception:
                pass
        source_ids = sorted(
            {
                source
                for member in entity_ids
                for source in source_by_entity.get(member, set())
            }
            | {source for claim in claims for source in claim.source_ids}
        )
        reports[community.id] = CommunityReport(
            community_id=community.id,
            level=community.level,
            title=f"{community.id}: {', '.join(names[:3]) or 'community'}",
            summary=summary,
            entities=tuple(names),
            risks=tuple(risks),
            dependencies=tuple(dependencies),
            source_ids=tuple(source_ids),
        )
    return reports


def _recommendation(risk_text: str) -> str:
    text = risk_text.lower()
    actions = []
    if "sql" in text:
        actions.append("parameterize SQL queries")
    if "pickle" in text or "deserialization" in text:
        actions.append("avoid pickle for untrusted data")
    if "shell" in text or "os.system" in text:
        actions.append("pass argument arrays without a shell")
    if "secret" in text or "password" in text:
        actions.append("move secrets to a secret manager and rotate them")
    if "md5" in text or "sha1" in text or "weak hash" in text:
        actions.append("replace weak hashes with a password KDF")
    if "pii" in text or "logging" in text:
        actions.append("redact PII before logging")
    if "tls" in text:
        actions.append("restore certificate verification")
    if not actions:
        actions.append("review the flagged paths and add regression tests")
    return "; ".join(dict.fromkeys(actions)).capitalize() + "."
