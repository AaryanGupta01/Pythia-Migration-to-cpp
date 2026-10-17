"""JSON report persistence."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2


def save_report(path: str, payload: Dict[str, Any]) -> None:
    """Write a report with a schema version header; keys are sorted so files diff cleanly."""
    document = {"schema": SCHEMA_VERSION, "results": payload}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_report(path: str) -> Dict[str, Any]:
    """Load a report written by `save_report`, rejecting files from an unknown schema."""
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    if document.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported report schema {document.get('schema')!r}")
    return document["results"]


def diff_reports(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Keys whose values differ between two reports (nested dicts are compared recursively)."""
    changes: Dict[str, Any] = {}
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if isinstance(a, dict) and isinstance(b, dict):
            inner = diff_reports(a, b)
            if inner:
                changes[key] = inner
        elif a != b:
            changes[key] = {"old": a, "new": b}
    return changes
