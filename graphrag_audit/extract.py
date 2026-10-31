# SPDX-License-Identifier: MIT
"""Deterministic repository extraction: entities, typed edges, and claims."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .types import Claim, Corpus, Entity, Relationship, TextUnit

PATTERNS = [
    (re.compile(r"\beval\s*\("), "dynamic-code-evaluation", "security", "dynamic eval() call"),
    (re.compile(r"shell\s*=\s*True"), "shell-injection", "security", "subprocess with shell=True"),
    (re.compile(r"pickle\.loads?\s*\("), "insecure-deserialization", "security", "pickle deserialization"),
    (re.compile(r"SECRET_KEY\s*=\s*['\"]"), "hardcoded-secret", "security", "hardcoded SECRET_KEY"),
    (re.compile(r"PASSWORD\s*=\s*['\"]", re.IGNORECASE), "hardcoded-password", "security", "hardcoded password"),
    (re.compile(r"execute\s*\(\s*f?['\"].*(SELECT|INSERT|UPDATE|DELETE)", re.IGNORECASE), "sql-construction", "security", "SQL built from a string"),
    (re.compile(r"os\.system\s*\("), "command-execution", "security", "os.system call"),
    (re.compile(r"hashlib\.(md5|sha1)\s*\("), "weak-hash", "security", "weak hash algorithm"),
    (re.compile(r"verify\s*=\s*False"), "tls-verification-disabled", "security", "TLS verification disabled"),
    (re.compile(r"(?:logging|logger)\.(info|debug|warning)\s*\([^)]*(password|email|token)", re.IGNORECASE), "pii-logging", "privacy", "potential PII in logs"),
]


def _text_units(path: str, lines: list[str]) -> tuple[list[TextUnit], dict[int, str]]:
    units: list[TextUnit] = []
    line_to_unit: dict[int, str] = {}
    window = 40
    step = 30
    if not lines:
        units.append(TextUnit(f"{path}:1-1", path, 1, 1, ""))
        return units, {1: f"{path}:1-1"}
    for start in range(0, len(lines), step):
        end = min(len(lines), start + window)
        unit_id = f"{path}:{start + 1}-{end}"
        units.append(TextUnit(unit_id, path, start + 1, end, "\n".join(lines[start:end])))
        for line in range(start + 1, end + 1):
            line_to_unit[line] = unit_id
        if end == len(lines):
            break
    return units, line_to_unit


def _nearest_definition(ranges: list[tuple[int, int, str]], line: int, module_id: str) -> str:
    candidates = [entity_id for start, end, entity_id in ranges if start <= line <= end]
    return candidates[-1] if candidates else module_id


def extract_repository(root: str | Path) -> Corpus:
    root = Path(root)
    corpus = Corpus()
    if not root.exists():
        raise FileNotFoundError(root)

    for path in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        units, line_to_unit = _text_units(relative, lines)
        corpus.text_units.extend(units)
        module_id = f"module:{relative}"
        module_unit = units[0].id if units else f"{relative}:1-1"
        corpus.entities.append(Entity(module_id, relative, "module", (module_unit,)))

        try:
            tree = ast.parse(source)
        except SyntaxError:
            corpus.claims.append(
                Claim(
                    id=f"claim:{relative}:syntax",
                    text=f"{relative} could not be parsed",
                    kind="reliability",
                    entity_ids=(module_id,),
                    source_ids=(module_unit,),
                )
            )
            continue

        ranges: list[tuple[int, int, str]] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                entity_id = f"class:{relative}:{node.name}"
                start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
                ranges.append((start, getattr(node, "end_lineno", node.lineno), entity_id))
                unit = line_to_unit.get(node.lineno, module_unit)
                corpus.entities.append(Entity(entity_id, node.name, "class", (unit,)))
                corpus.relationships.append(
                    Relationship(module_id, entity_id, "defines", 1.0, (unit,))
                )
                for base in node.bases:
                    name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
                    if name:
                        base_id = f"external:{name}"
                        corpus.entities.append(Entity(base_id, name, "class", (unit,)))
                        corpus.relationships.append(
                            Relationship(entity_id, base_id, "inherits", 1.0, (unit,))
                        )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                entity_id = f"function:{relative}:{node.name}"
                start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
                ranges.append((start, getattr(node, "end_lineno", node.lineno), entity_id))
                unit = line_to_unit.get(node.lineno, module_unit)
                corpus.entities.append(Entity(entity_id, node.name, "function", (unit,)))
                corpus.relationships.append(
                    Relationship(module_id, entity_id, "defines", 1.0, (unit,))
                )
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    dependency_id = f"import:{name.split('.')[0]}"
                    unit = line_to_unit.get(getattr(node, "lineno", 1), module_unit)
                    corpus.entities.append(Entity(dependency_id, name, "dependency", (unit,)))
                    corpus.relationships.append(
                        Relationship(module_id, dependency_id, "imports", 1.0, (unit,))
                    )

        for line_number, line in enumerate(lines, 1):
            for pattern, kind, category, description in PATTERNS:
                if pattern.search(line):
                    entity_id = _nearest_definition(ranges, line_number, module_id)
                    unit = line_to_unit.get(line_number, module_unit)
                    snippet = line.strip()[:180]
                    corpus.claims.append(
                        Claim(
                            id=f"claim:{relative}:{line_number}:{kind}",
                            text=f"{description}: {snippet}",
                            kind=category,
                            entity_ids=(entity_id,),
                            source_ids=(unit,),
                        )
                    )

    # Deduplicate entities by id while keeping the first source unit list.
    unique: dict[str, Entity] = {}
    for entity in corpus.entities:
        unique.setdefault(entity.id, entity)
    corpus.entities = list(unique.values())
    return corpus
