#!/usr/bin/env python3
"""
Download NWB session files from the DANDI archive and convert them to a BIDS
sub-dataset using nwb2bids.

The collection name is derived from the parent directory of the mapping file.
NWB files are staged in a nwb_files/ sub-folder next to the mapping file, and
the BIDS output is written to <repo_root>/<collection_name>/.

Usage:
    python code/download_and_convert_collection.py <path/to/mapping.tsv>

Example:
    python code/download_and_convert_collection.py \\
        sourcedata/collection-hmba+nhp/mapping.tsv

Prerequisites:
    pip install nwb2bids
"""

import argparse
import csv
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _check_tool(name: str) -> None:
    result = subprocess.run(["which", name], capture_output=True)
    if result.returncode != 0:
        print(f"ERROR: '{name}' not found on PATH. Install it with: pip install {name}")
        sys.exit(1)


def _read_mapping(mapping_tsv: Path) -> list[dict]:
    with open(mapping_tsv, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def download_nwb_files(rows: list[dict], staging_dir: Path) -> list[Path]:
    """Download each NWB file from its DANDI API URI into staging_dir."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for row in rows:
        dandi_uri = row.get("DANDI File URI", "").strip()
        sub_id = row.get("DANDI Subject ID (for BIDS)", "").strip()
        ses_id = row.get("DANDI Session ID (for BIDS)", "").strip()

        if not dandi_uri or not sub_id or not ses_id:
            continue

        dest = staging_dir / f"{sub_id}_{ses_id}.nwb"

        if dest.exists():
            print(f"  [skip] {dest.name} already exists")
            downloaded.append(dest)
            continue

        print(f"  Downloading {dest.name} ...")
        try:
            urllib.request.urlretrieve(dandi_uri, dest)
            downloaded.append(dest)
        except Exception as exc:
            print(f"    ERROR downloading {dest.name}: {exc}")
            if dest.exists():
                dest.unlink()

    return downloaded


def convert_to_bids(staging_dir: Path, bids_output_dir: Path) -> None:
    """Convert staged NWB files to a BIDS sub-dataset with nwb2bids."""
    bids_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nRunning: nwb2bids convert {staging_dir} --bids-directory {bids_output_dir}")
    subprocess.run(
        [
            "nwb2bids",
            "convert",
            str(staging_dir),
            "--bids-directory",
            str(bids_output_dir),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mapping_tsv", type=Path, help="Path to the mapping.tsv file")
    args = parser.parse_args()

    mapping_tsv: Path = args.mapping_tsv.resolve()
    if not mapping_tsv.is_file():
        print(f"ERROR: mapping file not found: {mapping_tsv}")
        sys.exit(1)

    collection_name = mapping_tsv.parent.name
    staging_dir = mapping_tsv.parent / "nwb_files"
    bids_output_dir = REPO_ROOT / collection_name

    _check_tool("nwb2bids")

    print(f"Collection:  {collection_name}")
    print(f"Mapping:     {mapping_tsv}")
    print(f"NWB staging: {staging_dir}")
    print(f"BIDS output: {bids_output_dir}\n")

    print("=== Step 1: Download NWB files from DANDI ===")
    rows = _read_mapping(mapping_tsv)
    print(f"  {len(rows)} session entries found")
    nwb_files = download_nwb_files(rows, staging_dir)
    print(f"\n  {len(nwb_files)} file(s) ready in {staging_dir}\n")

    if not nwb_files:
        print("No NWB files downloaded — nothing to convert.")
        sys.exit(1)

    print("=== Step 2: Convert to BIDS ===")
    convert_to_bids(staging_dir, bids_output_dir)
    print(f"\nDone. BIDS sub-dataset written to {bids_output_dir}")


if __name__ == "__main__":
    main()
