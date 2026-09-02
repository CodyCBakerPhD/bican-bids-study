"""Shared helpers for the DANDI-sandbox expected-output test.

Kept in one place so the test and the fixtures it reads are guaranteed to
be interpreted the same way.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
EXPECTED_OUTPUT = HERE / "expected_output"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def assert_subset(expected: dict[str, Any], actual: dict[str, Any], *, context: str) -> None:
    """Assert every key/value in ``expected`` is present and equal in ``actual``.

    This is a subset check, not full-document equality: the live sandbox
    response also carries server-assigned fields (id, identifier,
    schemaVersion, timestamps, assetsSummary, ...) that this basic example
    does not attempt to predict or pin down in the expected-output file.
    """
    missing = [key for key in expected if key not in actual]
    assert not missing, f"{context}: missing keys {missing} (actual keys: {sorted(actual)})"
    mismatched = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in expected
        if actual[key] != expected[key]
    }
    assert not mismatched, f"{context}: mismatched keys {json.dumps(mismatched, indent=2)}"
