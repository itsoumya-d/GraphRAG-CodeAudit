# SPDX-License-Identifier: MIT
"""SQLite persistence for the extracted corpus.

The Oracle Autonomous AI Database schema in sql/oracle_schema.sql mirrors these
tables; the adapter is intentionally left to the deployment environment.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .types import Claim, Corpus, Entity, Relationship, TextUnit


class SQLiteCorpusStore:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path))
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS text_units (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS relationships (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """
        )

    def save(self, corpus: Corpus) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM text_units")
            self.connection.execute("DELETE FROM entities")
            self.connection.execute("DELETE FROM relationships")
            self.connection.execute("DELETE FROM claims")
            self.connection.executemany(
                "INSERT INTO text_units (id, payload) VALUES (?, ?)",
                [(unit.id, json.dumps(asdict(unit))) for unit in corpus.text_units],
            )
            self.connection.executemany(
                "INSERT INTO entities (id, payload) VALUES (?, ?)",
                [(entity.id, json.dumps(asdict(entity))) for entity in corpus.entities],
            )
            self.connection.executemany(
                "INSERT INTO relationships (payload) VALUES (?)",
                [(json.dumps(asdict(rel)),) for rel in corpus.relationships],
            )
            self.connection.executemany(
                "INSERT INTO claims (id, payload) VALUES (?, ?)",
                [(claim.id, json.dumps(asdict(claim))) for claim in corpus.claims],
            )

    def load(self) -> Corpus:
        def rows(table: str):
            return [json.loads(row[0]) for row in self.connection.execute(f"SELECT payload FROM {table}")]

        return Corpus(
            text_units=[TextUnit(**row) for row in rows("text_units")],
            entities=[Entity(**row) for row in rows("entities")],
            relationships=[Relationship(**row) for row in rows("relationships")],
            claims=[Claim(**row) for row in rows("claims")],
        )

    def close(self) -> None:
        self.connection.close()
