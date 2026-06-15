#!/usr/bin/env python3
"""
Download NWB session files from the DANDI archive for the HMBA NHP collection
and convert them to a BIDS sub-dataset using nwb2bids.

Usage:
    python scripts/download_and_convert_collection_hmba_nhp.py

Prerequisites:
    pip install nwb2bids
"""

import csv
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
COLLECTION_SOURCEDATA_DIR = REPO_ROOT / "sourcedata" / "collection-hmba+nhp"
MAPPING_TSV = COLLECTION_SOURCEDATA_DIR / "mapping.tsv"
NWB_STAGING_DIR = COLLECTION_SOURCEDATA_DIR / "nwb_files"
BIDS_OUTPUT_DIR = REPO_ROOT / "collection-hmba+nhp"


def _check_tool(name: str) -> None:
    result = subprocess.run(["which", name], capture_output=True)
    if result.returncode != 0:
        print(f"ERROR: '{name}' not found on PATH. Install it with: pip install {name}")
        sys.exit(1)


def _read_mapping() -> list[dict]:
    with open(MAPPING_TSV, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def download_nwb_files(rows: list[dict]) -> list[Path]:
    """Download each NWB file from its DANDI API URI into NWB_STAGING_DIR."""
    NWB_STAGING_DIR.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for row in rows:
        dandi_uri = row.get("DANDI File URI", "").strip()
        sub_id = row.get("DANDI Subject ID (for BIDS)", "").strip()
        ses_id = row.get("DANDI Session ID (for BIDS)", "").strip()

        if not dandi_uri or not sub_id or not ses_id:
            continue

        dest = NWB_STAGING_DIR / f"{sub_id}_{ses_id}.nwb"

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


def convert_to_bids(nwb_staging_dir: Path, bids_output_dir: Path) -> None:
    """Convert staged NWB files to a BIDS sub-dataset with nwb2bids."""
    bids_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nRunning: nwb2bids convert {nwb_staging_dir} --bids-directory {bids_output_dir}")
    subprocess.run(
        [
            "nwb2bids",
            "convert",
            str(nwb_staging_dir),
            "--bids-directory",
            str(bids_output_dir),
        ],
        check=True,
    )


def main() -> None:
    _check_tool("nwb2bids")

    print(f"Reading mapping from {MAPPING_TSV}")
    rows = _read_mapping()
    print(f"  {len(rows)} session entries found\n")

    print("=== Step 1: Download NWB files from DANDI ===")
    nwb_files = download_nwb_files(rows)
    print(f"\n  {len(nwb_files)} file(s) ready in {NWB_STAGING_DIR}\n")

    if not nwb_files:
        print("No NWB files downloaded — nothing to convert.")
        sys.exit(1)

    print("=== Step 2: Convert to BIDS ===")
    convert_to_bids(NWB_STAGING_DIR, BIDS_OUTPUT_DIR)
    print(f"\nDone. BIDS sub-dataset written to {BIDS_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
