# SPDX-License-Identifier: MIT
"""Deterministic repository extraction: entities, typed edges, and claims."""

from __future__ import annotations

import ast
import posixpath
import re
from functools import lru_cache
from pathlib import Path

from .types import Claim, Corpus, Entity, Relationship, TextUnit

PATTERNS = [
    (re.compile(r"\beval\s*\("), "dynamic-code-evaluation", "security", "dynamic eval() call"),
    (re.compile(r"shell\s*=\s*True"), "shell-injection", "security", "subprocess with shell=True"),
    (re.compile(r"pickle\.loads?\s*\("), "insecure-deserialization", "security", "pickle deserialization"),
    (re.compile(r"SECRET_KEY\s*=\s*['\"]"), "hardcoded-secret", "security", "hardcoded SECRET_KEY"),
    (re.compile(r"PASSWORD\s*=\s*['\"]", re.IGNORECASE), "hardcoded-password", "security", "hardcoded password"),
    (re.compile(r"execute\s*\(\s*f['\"].*(SELECT|INSERT|UPDATE|DELETE)", re.IGNORECASE), "sql-construction", "security", "SQL built from an f-string"),
    (re.compile(r"os\.system\s*\("), "command-execution", "security", "os.system call"),
    (re.compile(r"hashlib\.(md5|sha1)\s*\("), "weak-hash", "security", "weak hash algorithm"),
    (re.compile(r"verify\s*=\s*False"), "tls-verification-disabled", "security", "TLS verification disabled"),
    (re.compile(r"(?:logging|logger)\.(info|debug|warning)\s*\([^)]*(password|email|token)", re.IGNORECASE), "pii-logging", "privacy", "potential PII in logs"),
]

JS_PATTERNS = [
    (re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*="), "xss-sink", "security", "raw HTML sink"),
    (re.compile(r"(?:exec|execSync|spawn|spawnSync)\s*\(\s*[`\"'][^`\"']*\$\{"), "command-injection", "security", "shell command built from interpolation"),
    (re.compile(r"(?:rejectUnauthorized|verify)\s*:\s*false"), "tls-verification-disabled", "security", "TLS verification disabled"),
    (re.compile(r"createHash\s*\(\s*['\"](?:md5|sha1)['\"]", re.IGNORECASE), "weak-hash", "security", "weak hash algorithm"),
    (re.compile(r"localStorage\.setItem\s*\([^,)]*token", re.IGNORECASE), "token-in-localstorage", "security", "token stored in localStorage"),
]

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

SKIP_DIRECTORIES = {
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "vendor",
    ".venv",
    "venv",
}

CLASS_NODE_TYPES = {"class_declaration", "abstract_class_declaration"}
FUNCTION_NODE_TYPES = {"function_declaration", "generator_function_declaration"}
FUNCTION_VALUE_TYPES = {"arrow_function", "function_expression", "function"}


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


def _iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in LANGUAGE_BY_SUFFIX:
            continue
        relative_parts = path.relative_to(root).parts
        if any(part.startswith(".") or part in SKIP_DIRECTORIES for part in relative_parts):
            continue
        yield path


def _extract_python(
    corpus: Corpus,
    relative: str,
    source: str,
    lines: list[str],
    line_to_unit: dict[int, str],
    module_id: str,
    module_unit: str,
    ranges: list[tuple[int, int, str]],
) -> None:
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
        return

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


@lru_cache(maxsize=None)
def _load_parser(language: str):
    try:
        from tree_sitter import Language, Parser

        if language in {"typescript", "tsx"}:
            import tree_sitter_typescript as grammar

            selected = grammar.language_tsx() if language == "tsx" else grammar.language_typescript()
        else:
            import tree_sitter_javascript as grammar

            selected = grammar.language()
    except ImportError as exc:
        raise RuntimeError(
            "TypeScript/JavaScript extraction requires tree-sitter, "
            "tree-sitter-typescript, and tree-sitter-javascript"
        ) from exc
    return Parser(Language(selected))


def _dependency_name(specifier: str, relative: str) -> str:
    specifier = specifier.strip().strip("'\"")
    if specifier.startswith("node:"):
        specifier = specifier[5:]
    if specifier.startswith((".", "/")):
        if specifier.startswith("."):
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(relative), specifier))
        else:
            resolved = posixpath.normpath(specifier.lstrip("/"))
        return resolved[2:] if resolved.startswith("./") else resolved.lstrip("/")
    parts = specifier.split("/")
    if specifier.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _extract_javascript(
    corpus: Corpus,
    relative: str,
    language: str,
    source: str,
    line_to_unit: dict[int, str],
    module_id: str,
    module_unit: str,
    ranges: list[tuple[int, int, str]],
) -> set[int]:
    encoded = source.encode("utf-8")
    tree = _load_parser(language)
    root = tree.parse(encoded).root_node
    comment_lines: set[int] = set()
    seen_dependencies: set[str] = set()

    def text(node) -> str:
        return encoded[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def line_of(node) -> int:
        return node.start_point[0] + 1

    def add_dependency(node, line: int) -> None:
        dependency = _dependency_name(text(node), relative)
        if not dependency or dependency in seen_dependencies:
            return
        seen_dependencies.add(dependency)
        unit = line_to_unit.get(line, module_unit)
        dependency_id = f"import:{dependency}"
        corpus.entities.append(Entity(dependency_id, dependency, "dependency", (unit,)))
        corpus.relationships.append(
            Relationship(module_id, dependency_id, "imports", 1.0, (unit,))
        )

    def enclosing_class(node):
        parent = node.parent
        return parent.parent if parent is not None else None

    def add_symbol(
        node,
        name: str,
        kind: str,
        prefix: str | None = None,
        container_id: str | None = None,
    ) -> str:
        unit = line_to_unit.get(line_of(node), module_unit)
        qualified = f"{prefix}.{name}" if prefix else name
        entity_id = f"{kind}:{relative}:{qualified}"
        ranges.append((line_of(node), node.end_point[0] + 1, entity_id))
        corpus.entities.append(Entity(entity_id, name, kind, (unit,)))
        corpus.relationships.append(
            Relationship(container_id or module_id, entity_id, "defines", 1.0, (unit,))
        )
        return entity_id

    def visit(node) -> None:
        kind = node.type
        if kind == "comment":
            comment_lines.update(range(node.start_point[0] + 1, node.end_point[0] + 2))
            return
        if kind == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node is not None:
                add_dependency(source_node, line_of(node))
        elif kind == "export_statement":
            source_node = node.child_by_field_name("source")
            if source_node is not None:
                add_dependency(source_node, line_of(node))
        elif kind == "call_expression":
            function_node = node.child_by_field_name("function")
            arguments = node.child_by_field_name("arguments")
            if function_node is not None and text(function_node) == "require" and arguments is not None:
                string_node = next(
                    (child for child in arguments.children if child.type == "string"), None
                )
                if string_node is not None:
                    add_dependency(string_node, line_of(node))
        elif kind in CLASS_NODE_TYPES:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node is not None else f"anonymous@{line_of(node)}"
            unit = line_to_unit.get(line_of(node), module_unit)
            entity_id = add_symbol(node, name, "class")
            heritage = next((child for child in node.children if child.type == "class_heritage"), None)
            clause = next(
                (child for child in heritage.children if child.type == "extends_clause"), None
            ) if heritage is not None else None
            base_node = clause.child_by_field_name("value") if clause is not None else None
            if base_node is not None:
                base = text(base_node)
                base_id = f"external:{base}"
                corpus.entities.append(Entity(base_id, base, "class", (unit,)))
                corpus.relationships.append(
                    Relationship(entity_id, base_id, "inherits", 1.0, (unit,))
                )
        elif kind == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                add_symbol(node, text(name_node), "interface")
        elif kind in FUNCTION_NODE_TYPES:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                add_symbol(node, text(name_node), "function")
        elif kind == "method_definition":
            name_node = node.child_by_field_name("name")
            class_node = enclosing_class(node)
            if name_node is None:
                pass
            elif class_node is not None and class_node.type in CLASS_NODE_TYPES:
                class_name_node = class_node.child_by_field_name("name")
                class_name = (
                    text(class_name_node)
                    if class_name_node is not None
                    else f"anonymous@{line_of(class_node)}"
                )
                add_symbol(
                    node,
                    text(name_node),
                    "method",
                    prefix=class_name,
                    container_id=f"class:{relative}:{class_name}",
                )
            else:
                add_symbol(node, text(name_node), "function")
        elif kind == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if (
                name_node is not None
                and name_node.type == "identifier"
                and value_node is not None
                and value_node.type in FUNCTION_VALUE_TYPES
            ):
                add_symbol(node, text(name_node), "function")
        for child in node.children:
            visit(child)

    visit(root)
    if root.has_error:
        corpus.claims.append(
            Claim(
                id=f"claim:{relative}:syntax",
                text=f"{relative} contains a parse error",
                kind="reliability",
                entity_ids=(module_id,),
                source_ids=(line_to_unit.get(1, module_unit),),
            )
        )
    return comment_lines


def _scan_claims(
    corpus: Corpus,
    relative: str,
    lines: list[str],
    ranges: list[tuple[int, int, str]],
    module_id: str,
    line_to_unit: dict[int, str],
    module_unit: str,
    patterns,
    skip_lines: set[int],
    python_mode: bool,
) -> None:
    for line_number, line in enumerate(lines, 1):
        if line_number in skip_lines:
            continue
        stripped = line.lstrip()
        if python_mode and (stripped.startswith("#") or "re.compile(" in line):
            continue
        for pattern, kind, category, description in patterns:
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


def extract_repository(root: str | Path) -> Corpus:
    root = Path(root)
    corpus = Corpus()
    if not root.exists():
        raise FileNotFoundError(root)

    for path in _iter_source_files(root):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        units, line_to_unit = _text_units(relative, lines)
        corpus.text_units.extend(units)
        module_id = f"module:{relative}"
        module_unit = units[0].id if units else f"{relative}:1-1"
        corpus.entities.append(Entity(module_id, relative, "module", (module_unit,)))

        ranges: list[tuple[int, int, str]] = []
        language = LANGUAGE_BY_SUFFIX[path.suffix.lower()]
        if language == "python":
            _extract_python(
                corpus, relative, source, lines, line_to_unit, module_id, module_unit, ranges
            )
            _scan_claims(
                corpus,
                relative,
                lines,
                ranges,
                module_id,
                line_to_unit,
                module_unit,
                PATTERNS,
                set(),
                python_mode=True,
            )
        else:
            comment_lines = _extract_javascript(
                corpus, relative, language, source, line_to_unit, module_id, module_unit, ranges
            )
            _scan_claims(
                corpus,
                relative,
                lines,
                ranges,
                module_id,
                line_to_unit,
                module_unit,
                PATTERNS + JS_PATTERNS,
                comment_lines,
                python_mode=False,
            )

    unique: dict[str, Entity] = {}
    for entity in corpus.entities:
        unique.setdefault(entity.id, entity)
    corpus.entities = list(unique.values())
    return corpus
