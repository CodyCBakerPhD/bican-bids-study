#!/usr/bin/env python3
"""
Create a Dandiset, update its metadata, and add owners to it.

Three inputs, all optional except where noted:

  --metadata metadata.json   Partial Dandiset metadata (see scripts/examples/metadata.json).
                             Top-level keys are merged onto the current draft metadata.
                             On creation, ``name`` and ``description`` are taken from here
                             unless overridden with --name / --description.
  --users users.tsv          TSV with a ``username`` column (DANDI usernames == GitHub logins).
                             Users are only ever ADDED as owners; existing owners are kept.
  --dandiset-id 000123       Operate on an existing Dandiset instead of creating a new one.

Authentication: set the ``DANDI_API_KEY`` environment variable (or
``DANDI_SANDBOX_API_KEY`` for --instance dandi-sandbox). If unset, the dandi
client falls back to the system keyring and then prompts for the key.

Examples::

    # Create a new Dandiset on the sandbox, set its metadata, and add owners
    python scripts/dandiset_setup.py --instance dandi-sandbox \\
        --metadata scripts/examples/metadata.json --users scripts/examples/users.tsv

    # Only add owners to an existing Dandiset on production
    python scripts/dandiset_setup.py --dandiset-id 000123 --users users.tsv

    # Only update the metadata on an existing Dandiset
    python scripts/dandiset_setup.py --dandiset-id 000123 --metadata metadata.json

    # See what would happen without changing anything
    python scripts/dandiset_setup.py --metadata metadata.json --users users.tsv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

try:
    from dandi.dandiapi import DandiAPIClient, RemoteDandiset
except ImportError:  # pragma: no cover - friendly message instead of a traceback
    sys.exit(
        "The 'dandi' package is required: pip install dandi "
        "(or: pip install -r scripts/requirements.txt)"
    )

USERNAME_COLUMN = "username"


# --------------------------------------------------------------------------- #
# Input readers
# --------------------------------------------------------------------------- #
def read_users_tsv(path: Path) -> list[str]:
    """Return the de-duplicated, ordered list of usernames from a TSV file."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None or USERNAME_COLUMN not in reader.fieldnames:
            raise SystemExit(
                f"{path}: expected a header row containing a '{USERNAME_COLUMN}' column; "
                f"found columns: {reader.fieldnames}"
            )
        usernames: list[str] = []
        for row in reader:
            username = (row.get(USERNAME_COLUMN) or "").strip()
            if not username or username.startswith("#"):
                continue
            if username not in usernames:
                usernames.append(username)
    return usernames


def read_metadata_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    if not isinstance(metadata, dict):
        raise SystemExit(f"{path}: top-level value must be a JSON object")
    return metadata


# --------------------------------------------------------------------------- #
# DANDI operations
# --------------------------------------------------------------------------- #
def create_dandiset(
    client: DandiAPIClient, name: str, description: str, *, embargo: bool, dry_run: bool
) -> RemoteDandiset | None:
    print(f"Creating Dandiset {'(embargoed) ' if embargo else ''}named: {name!r}")
    if dry_run:
        print("  [dry-run] not created")
        return None
    dandiset = client.create_dandiset(
        name,
        {"schemaKey": "Dandiset", "name": name, "description": description},
        embargo=embargo,
    )
    print(f"  Created {dandiset.identifier}: {dandiset.api_url}")
    return dandiset


def update_metadata(
    dandiset: RemoteDandiset, updates: dict[str, Any], *, dry_run: bool
) -> None:
    """Merge ``updates`` onto the draft metadata (top-level keys replace)."""
    current = dandiset.get_raw_metadata()
    merged = {**current, **updates}
    merged.setdefault("schemaKey", "Dandiset")
    changed = sorted(key for key in updates if current.get(key) != updates[key])
    if not changed:
        print(f"Metadata for {dandiset.identifier}: already up to date")
        return
    print(f"Updating metadata for {dandiset.identifier}; changed keys: {', '.join(changed)}")
    if dry_run:
        print("  [dry-run] not written")
        return
    dandiset.set_raw_metadata(merged)
    print("  Metadata updated")


def get_owners(client: DandiAPIClient, dandiset_id: str) -> list[str]:
    users = client.get(f"/dandisets/{dandiset_id}/users/")
    return [user["username"] for user in users]


def add_owners(
    client: DandiAPIClient, dandiset_id: str, usernames: list[str], *, dry_run: bool
) -> None:
    """Add ``usernames`` as owners; never removes anyone."""
    current = get_owners(client, dandiset_id)
    new = [username for username in usernames if username not in current]
    print(f"Owners of {dandiset_id}: currently {current}")
    if not new:
        print("  All requested users are already owners; nothing to add")
        return
    print(f"  Adding: {new}")
    if dry_run:
        print("  [dry-run] not written")
        return
    # The API replaces the full owner list, so send current + new.
    client.put(
        f"/dandisets/{dandiset_id}/users/",
        json=[{"username": username} for username in current + new],
    )
    print(f"  Owners are now: {get_owners(client, dandiset_id)}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--instance",
        default="dandi",
        help="DANDI instance name, e.g. 'dandi' (production, default) or 'dandi-sandbox'",
    )
    parser.add_argument(
        "--dandiset-id",
        help="Existing Dandiset ID (e.g. 000123). If omitted, a new Dandiset is created.",
    )
    parser.add_argument("--metadata", type=Path, help="Path to a metadata JSON file")
    parser.add_argument("--users", type=Path, help="Path to a users TSV file")
    parser.add_argument("--name", help="Dandiset name (overrides 'name' in --metadata)")
    parser.add_argument(
        "--description", help="Dandiset description (overrides 'description' in --metadata)"
    )
    parser.add_argument(
        "--embargo", action="store_true", help="Create the new Dandiset as embargoed"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without writing"
    )
    args = parser.parse_args(argv)

    if args.dandiset_id is None and args.metadata is None and args.name is None:
        parser.error("creating a Dandiset needs --metadata (with 'name') or --name")
    if args.dandiset_id is not None and args.embargo:
        parser.error("--embargo only applies when creating a new Dandiset")
    if args.dandiset_id is not None and args.metadata is None and args.users is None:
        parser.error("nothing to do: pass --metadata and/or --users")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    metadata = read_metadata_json(args.metadata) if args.metadata else {}
    usernames = read_users_tsv(args.users) if args.users else []

    if args.name:
        metadata["name"] = args.name
    if args.description:
        metadata["description"] = args.description

    client = DandiAPIClient.for_dandi_instance(args.instance, authenticate=True)

    if args.dandiset_id:
        dandiset_id = args.dandiset_id
        dandiset = client.get_dandiset(dandiset_id, "draft", lazy=False)
        print(f"Using existing Dandiset {dandiset_id}: {dandiset.api_url}")
    else:
        name = metadata.get("name")
        description = metadata.get("description")
        if not name or not description:
            raise SystemExit(
                "A new Dandiset needs both a name and a description "
                "(via --metadata or --name/--description)"
            )
        created = create_dandiset(
            client, name, description, embargo=args.embargo, dry_run=args.dry_run
        )
        if created is None:  # dry run: nothing else can be applied to a nonexistent Dandiset
            if metadata:
                print(f"[dry-run] would apply metadata keys: {', '.join(sorted(metadata))}")
            if usernames:
                print(f"[dry-run] would add owners: {usernames}")
            return 0
        dandiset_id = created.identifier
        dandiset = client.get_dandiset(dandiset_id, "draft", lazy=False)

    if metadata:
        update_metadata(dandiset, metadata, dry_run=args.dry_run)
    if usernames:
        add_owners(client, dandiset_id, usernames, dry_run=args.dry_run)

    print(f"Done: {dandiset_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
