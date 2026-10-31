"""Database access layer with a deliberate SQL construction issue."""
import sqlite3

CONNECTION = sqlite3.connect(":memory:")


def find_user(email: str):
    cursor = CONNECTION.cursor()
    # SQL built from a string: flagged by the extractor.
    cursor.execute(f"SELECT id, email FROM users WHERE email = '{email}'")
    return cursor.fetchall()


def save_user(email: str):
    cursor = CONNECTION.cursor()
    cursor.execute("INSERT INTO users (email) VALUES (?)", (email,))
    CONNECTION.commit()
