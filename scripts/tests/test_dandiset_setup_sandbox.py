"""
Expected-output integration test for ``dandiset_setup.py``, run against the
DANDI *sandbox* archive (https://sandbox.dandiarchive.org) — never
production.

Same idea as the fixture pattern at
https://github.com/brain-bbqs/data-ingest-task-force/tree/main/labs/kemere/tests
(sometimes called "golden file" testing): fixed input fixtures, a real run
of the code under test, and the result compared against a committed
expected-output file. Adapted here for a live API instead of an offline
conversion: fields the sandbox itself assigns (Dandiset id, identifier,
schemaVersion, timestamps, assetsSummary, ...) can't be predicted ahead of
time, so the comparison in ``_helpers.assert_subset`` is a subset check —
every field we asked the script to set must come back exactly as sent —
rather than full-document equality.

Requires a real sandbox account:

    export DANDI_SANDBOX_API_KEY=...   # sandbox.dandiarchive.org -> account -> API keys
    pytest scripts/tests/test_dandiset_setup_sandbox.py -v

Skipped automatically when ``DANDI_SANDBOX_API_KEY`` is unset (e.g. in CI
with no sandbox credentials configured). Every Dandiset this test creates is
deleted again in a ``finally`` block, whether the test passes or fails.

Owner-adding is exercised only when ``DANDI_SANDBOX_TEST_USERNAME`` is also
set, to a *second* real sandbox account distinct from the one running the
test. "Add a user" is not tested against a fixed expected-output file the
way metadata is: who the test's creator is, and who is available to add as
an owner, both depend on whose credentials the test runs with, so there is
no fixed expected output to commit — the test asserts the invariant instead
(the new user is added, nobody already there is removed).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # for `import dandiset_setup`
import dandiset_setup  # noqa: E402
from dandi.dandiapi import DandiAPIClient  # noqa: E402

from _helpers import EXPECTED_OUTPUT, FIXTURES, assert_subset, load_json  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("DANDI_SANDBOX_API_KEY"),
    reason="set DANDI_SANDBOX_API_KEY to run this test against the DANDI sandbox",
)


@pytest.fixture
def sandbox_client():
    with DandiAPIClient.for_dandi_instance("dandi-sandbox", authenticate=True) as client:
        yield client


def _unique_metadata() -> dict:
    """The metadata fixture, with a unique suffix so repeated runs don't pile
    up Dandisets with identical names while still exercising the same
    fields the expected-output file checks."""
    metadata = load_json(FIXTURES / "metadata.json")
    metadata["name"] = f"{metadata['name']} [{uuid.uuid4().hex[:8]}]"
    return metadata


def test_create_and_update_matches_expected_metadata(sandbox_client):
    metadata = _unique_metadata()

    dandiset = dandiset_setup.create_dandiset(
        sandbox_client, metadata["name"], metadata["description"], embargo=False, dry_run=False
    )
    try:
        dandiset_setup.update_metadata(dandiset, metadata, dry_run=False)

        actual = dandiset.get_raw_metadata()
        expected = load_json(EXPECTED_OUTPUT / "metadata.json")
        expected["name"] = metadata["name"]  # expected-output file uses the un-suffixed name
        assert_subset(expected, actual, context="Dandiset metadata")
    finally:
        dandiset.delete()


@pytest.mark.skipif(
    not os.environ.get("DANDI_SANDBOX_TEST_USERNAME"),
    reason="set DANDI_SANDBOX_TEST_USERNAME to a second sandbox account to test adding owners",
)
def test_add_owners_only_adds(sandbox_client):
    test_username = os.environ["DANDI_SANDBOX_TEST_USERNAME"]
    metadata = _unique_metadata()

    dandiset = dandiset_setup.create_dandiset(
        sandbox_client, metadata["name"], metadata["description"], embargo=False, dry_run=False
    )
    try:
        before = dandiset_setup.get_owners(sandbox_client, dandiset.identifier)
        dandiset_setup.add_owners(
            sandbox_client, dandiset.identifier, [test_username], dry_run=False
        )
        after = dandiset_setup.get_owners(sandbox_client, dandiset.identifier)

        assert set(before) <= set(after), "existing owners must never be removed"
        assert test_username in after
        assert len(after) == len(before) + 1
    finally:
        dandiset.delete()
