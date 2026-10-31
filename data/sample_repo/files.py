"""File import helpers with unsafe deserialization and command execution."""
import os
import pickle
import subprocess


def load_snapshot(path: str):
    with open(path, "rb") as handle:
        # Insecure deserialization: flagged by the extractor.
        return pickle.loads(handle.read())


def convert_image(path: str) -> str:
    # shell=True: flagged by the extractor.
    return subprocess.check_output(f"convert {path} /tmp/out.png", shell=True, text=True)


def list_dir(path: str):
    # os.system: flagged by the extractor.
    os.system(f"ls {path}")
