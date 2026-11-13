#!/usr/bin/env python3
"""
Assemble a BIDS "study" Dandiset from NWB files already on DANDI, validate it, and upload it.

The result is laid out like https://github.com/dandisets/001893:

    <dandiset>/
    ├── .bidsignore
    ├── dataset_description.json     (DatasetType "study")
    ├── README.txt
    ├── participants.tsv / .json     one row per subject
    ├── mapping.tsv / .json          one row per recorded cell (NWB file)
    ├── datasets.tsv / .json         one row per source Dandiset
    └── sourcedata/raw/sub-<id>/sub-<id>_ses-<id>_icephys.nwb

Steps:

  1. Download every asset listed in the inventory (CSV or TSV) into sourcedata/raw/,
     keeping its original path, and check its size and DANDI etag. Files already present
     with the right size are skipped, so an interrupted run can just be started again.
  2. Copy the static files (dataset_description.json, README.txt, .bidsignore and the
     *.json column descriptions) from --template, which mirrors the Dandiset's tree.
  3. Write participants.tsv, mapping.tsv and datasets.tsv from the inventory.
  4. Validate every BIDS dataset level (every directory holding a dataset_description.json)
     with the BIDS validator that `dandi upload` uses, and stop if any level has errors.
  5. Upload to the target Dandiset, then fill mapping.tsv's dandi_file_url column with the
     URLs of the new assets and upload mapping.tsv again.

Authentication: uploading needs ``DANDI_API_KEY`` (``DANDI_SANDBOX_API_KEY`` for
--instance dandi-sandbox). Downloading from published Dandisets needs no key.

Example::

    python scripts/assemble_bids_study.py \\
        --inventory sourcedata/HMBA_NHP_BG_NWB_files.tsv \\
        --template scripts/templates/002029 \\
        --dandiset-id 002029 \\
        --bican-subprogram "BICAN HMBA" --grant-number "NIMH UM1MH130981" \\
        --output-dir /data/bids-study
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from dandi.bids_validator_deno import bids_validate
    from dandi.dandiapi import DandiAPIClient, RemoteDandiset
    from dandi.dandiset import Dandiset
    from dandi.support.digests import get_digest
    from dandi.upload import UploadExisting, UploadValidation, upload
    from dandi.validate import Severity
except ImportError:  # pragma: no cover - friendly message instead of a traceback
    sys.exit("The 'dandi' package is required: pip install -r scripts/requirements.txt")

RAW_DIR = Path("sourcedata", "raw")

REQUIRED_COLUMNS = (
    "asset_id",
    "path",
    "size",
    "dandiset_id",
    "subject_id",
    "session_id",
    "species",
    "gender",
    "age",
    "cell_id",
    "cell_name",
    "roi_dhba",
    "patched_cell_container_x",
    "exp_component_name",
    "library_prep",
)

SPECIES_NCBI_TAXON = {
    "Homo sapiens": "NCBITaxon:9606",
    "Macaca fascicularis": "NCBITaxon:9541",
    "Macaca mulatta": "NCBITaxon:9544",
    "Macaca nemestrina": "NCBITaxon:9545",
    "Mus musculus": "NCBITaxon:10090",
}
SEX = {"F": "Female", "M": "Male"}
AGE_IN_YEARS = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:yrs?|years?)\s*$", re.IGNORECASE)

Row = dict[str, str]


# --------------------------------------------------------------------------- #
# Inventory and tables
# --------------------------------------------------------------------------- #
def read_inventory(path: Path) -> list[Row]:
    """Read the asset inventory; ``.tsv`` files are tab-separated, anything else CSV."""
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(
                f"{path}: missing required column(s): {', '.join(missing)}"
            )
        rows = [row for row in reader if any(value.strip() for value in row.values())]
    paths = [row["path"] for row in rows]
    duplicates = sorted({p for p in paths if paths.count(p) > 1})
    if duplicates:
        raise SystemExit(f"{path}: duplicate asset paths: {', '.join(duplicates)}")
    return rows


def build_participants(rows: Iterable[Row]) -> list[Row]:
    """One row per subject; every row of a subject must agree on species, sex and age."""
    participants: dict[str, Row] = {}
    for row in rows:
        species = row["species"].strip()
        if species not in SPECIES_NCBI_TAXON:
            raise SystemExit(
                f"Unknown species {species!r}: add it to SPECIES_NCBI_TAXON"
            )
        if row["gender"].strip() not in SEX:
            raise SystemExit(
                f"Unknown sex {row['gender']!r} for subject {row['subject_id']}"
            )
        age = AGE_IN_YEARS.match(row["age"])
        if age is None:
            raise SystemExit(f"Cannot parse age {row['age']!r} (expected e.g. '8 yrs')")
        participant = {
            "participant_id": f"sub-{row['subject_id']}",
            "species_name": species,
            "species_ncbi_taxon": SPECIES_NCBI_TAXON[species],
            "sex_at_birth": SEX[row["gender"].strip()],
            "age": age.group(1),
        }
        previous = participants.setdefault(participant["participant_id"], participant)
        if previous != participant:
            raise SystemExit(f"Conflicting subject info: {previous} vs {participant}")
    return sorted(participants.values(), key=lambda p: p["participant_id"])


def build_mapping(
    rows: Iterable[Row], source_api_url: str, target_urls: dict[str, str]
) -> list[Row]:
    """One row per cell; ``target_urls`` maps Dandiset paths to their download URLs."""
    mapping = [
        {
            "session_id": f"ses-{row['session_id']}",
            "participant_id": f"sub-{row['subject_id']}",
            "cell_specimen_id": row["cell_id"],
            "dissociated_cell_sample_local_name": row["cell_name"],
            "brain_structure_acronym_dhba": row["roi_dhba"],
            "patched_cell_container": row["patched_cell_container_x"],
            "exp_component_name": row["exp_component_name"],
            "library_prep": row["library_prep"],
            "dandi_file_url": target_urls.get((RAW_DIR / row["path"]).as_posix(), ""),
            "source_dandiset_id": row["dandiset_id"],
            "source_dandi_file_url": f"{source_api_url}/assets/{row['asset_id']}/download/",
        }
        for row in rows
    ]
    return sorted(mapping, key=lambda m: (m["participant_id"], m["session_id"]))


def build_datasets(
    client: DandiAPIClient,
    rows: Iterable[Row],
    *,
    gui_url: str,
    bican_subprogram: str,
    grant_number: str,
) -> list[Row]:
    """One row per source Dandiset, counting its NWB files (one per cell) on DANDI."""
    datasets = []
    for dandiset_id in sorted({row["dandiset_id"] for row in rows}):
        # No version given: the latest published version, else the draft
        dandiset = client.get_dandiset(dandiset_id)
        n_cells = sum(asset.path.endswith(".nwb") for asset in dandiset.get_assets())
        datasets.append(
            {
                "dandiset_id": dandiset_id,
                "url": f"{gui_url}/dandiset/{dandiset_id}",
                "bican_subprogram": bican_subprogram,
                "grant_number": grant_number,
                "number_of_cells": str(n_cells),
            }
        )
    return datasets


def write_tsv(path: Path, records: list[Row]) -> bool:
    """Write ``records`` as a TSV; leave the file (and its mtime) alone if unchanged."""
    if not records:
        raise SystemExit(f"Refusing to write empty table {path}")
    columns = list(records[0])
    lines = ["\t".join(columns)]
    lines += ["\t".join(record[column] for column in columns) for record in records]
    content = "\n".join(lines) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def asset_urls(dandiset: RemoteDandiset) -> dict[str, str]:
    return {asset.path: asset.base_download_url for asset in dandiset.get_assets()}


# --------------------------------------------------------------------------- #
# Download, validate, upload
# --------------------------------------------------------------------------- #
def download_asset(client: DandiAPIClient, row: Row, dest: Path) -> str:
    size = int(row["size"])
    if dest.exists() and dest.stat().st_size == size:
        return "already present"
    asset = client.get_asset(row["asset_id"])
    if asset.size != size:
        raise RuntimeError(
            f"{row['asset_id']}: inventory size {size} != DANDI {asset.size}"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    asset.download(partial)
    expected = asset.get_raw_digest("dandi:dandi-etag")
    actual = get_digest(partial, "dandi-etag")
    if partial.stat().st_size != size or actual != expected:
        partial.unlink()
        raise RuntimeError(f"{dest.name}: checksum {actual} != expected {expected}")
    partial.replace(dest)
    return "downloaded"


def download_assets(
    client: DandiAPIClient, rows: list[Row], raw_dir: Path, jobs: int
) -> None:
    total_gb = sum(int(row["size"]) for row in rows) / 1e9
    print(f"Fetching {len(rows)} assets ({total_gb:.1f} GB) into {raw_dir}")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(download_asset, client, row, raw_dir / row["path"]): row["path"]
            for row in rows
        }
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                print(f"  [{done}/{len(rows)}] {futures[future]}: {future.result()}")
        except BaseException:
            pool.shutdown(cancel_futures=True)
            raise

    expected = {raw_dir / row["path"] for row in rows}
    extra = sorted(p for p in raw_dir.rglob("*") if p.is_file() and p not in expected)
    if extra:
        listing = "\n  ".join(str(p) for p in extra)
        raise SystemExit(
            f"Files not in the inventory (remove them first):\n  {listing}"
        )


def validate_bids_levels(root: Path) -> bool:
    """Run the BIDS validator on each directory under ``root`` with a dataset_description.json."""
    ok = True
    levels = sorted(p.parent for p in root.rglob("dataset_description.json"))
    if not levels:
        print(f"No dataset_description.json found under {root}")
        return False
    for level in levels:
        results = bids_validate(level)
        errors = [
            r
            for r in results
            if r.severity is not None and r.severity >= Severity.ERROR
        ]
        warnings = [
            r for r in results if r.severity is not None and r.severity < Severity.ERROR
        ]
        name = level.relative_to(root).as_posix()
        print(
            f"BIDS validation of '{name}': {len(errors)} error(s), {len(warnings)} warning(s)"
        )
        for result in errors:
            where = result.path.relative_to(level).as_posix() if result.path else ""
            print(f"  ERROR {result.id} {where}: {(result.message or '').strip()}")
        ok = ok and not errors
    return ok


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--inventory", type=Path, required=True, help="CSV/TSV of DANDI assets"
    )
    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Directory of static files to copy into the Dandiset (same tree layout)",
    )
    parser.add_argument(
        "--dandiset-id", required=True, help="Target Dandiset, e.g. 002029"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Where to assemble the Dandiset; it goes in <output-dir>/<dandiset-id>",
    )
    parser.add_argument("--bican-subprogram", default="", help="For datasets.tsv")
    parser.add_argument("--grant-number", default="", help="For datasets.tsv")
    parser.add_argument(
        "--instance",
        default="dandi",
        help="DANDI instance to upload to (default: dandi)",
    )
    parser.add_argument(
        "--source-instance",
        default="dandi",
        help="DANDI instance the inventory's assets live on (default: dandi)",
    )
    parser.add_argument(
        "--jobs", type=int, default=4, help="Parallel downloads/uploads"
    )
    parser.add_argument(
        "--validation",
        choices=("require", "skip", "ignore"),
        default="require",
        help="`dandi upload` validation mode (default: require)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Download, assemble and validate only; do not upload",
    )
    args = parser.parse_args(argv)
    if not args.template.is_dir():
        parser.error(f"--template {args.template} is not a directory")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = read_inventory(args.inventory)

    source = DandiAPIClient.for_dandi_instance(args.source_instance)
    # Authenticate up front when uploading, so a missing key fails before the download.
    target = DandiAPIClient.for_dandi_instance(
        args.instance, authenticate=not args.no_upload
    )
    remote = target.get_dandiset(args.dandiset_id, "draft", lazy=False)
    print(f"Target: {remote.identifier} ({remote.version.name})")

    root = args.output_dir / args.dandiset_id
    root.mkdir(parents=True, exist_ok=True)
    Dandiset(root, allow_empty=True).update_metadata(remote.get_raw_metadata())
    shutil.copytree(args.template, root, dirs_exist_ok=True)

    download_assets(source, rows, root / RAW_DIR, args.jobs)

    write_tsv(root / "participants.tsv", build_participants(rows))
    write_tsv(
        root / "datasets.tsv",
        build_datasets(
            source,
            rows,
            gui_url=source.dandi_instance.gui or source.api_url,
            bican_subprogram=args.bican_subprogram,
            grant_number=args.grant_number,
        ),
    )
    write_tsv(
        root / "mapping.tsv", build_mapping(rows, source.api_url, asset_urls(remote))
    )

    if not validate_bids_levels(root):
        print("BIDS validation failed; fix the errors above before uploading.")
        return 1
    if args.no_upload:
        print(f"Assembled and validated {root}; not uploading (--no-upload).")
        return 0

    upload_kwargs = {
        "dandi_instance": args.instance,
        "existing": UploadExisting.REFRESH,
        "validation": UploadValidation(args.validation),
        "jobs": args.jobs,
    }
    upload([root], **upload_kwargs)

    # The new assets' URLs only exist after the upload; record them and upload mapping.tsv again.
    remote = target.get_dandiset(args.dandiset_id, "draft", lazy=False)
    mapping = build_mapping(rows, source.api_url, asset_urls(remote))
    missing = [m["session_id"] for m in mapping if not m["dandi_file_url"]]
    if missing:
        print(
            f"WARNING: {len(missing)} session(s) not found on DANDI after upload: {missing}"
        )
    if write_tsv(root / "mapping.tsv", mapping):
        if not validate_bids_levels(root):
            return 1
        upload([root / "mapping.tsv"], **upload_kwargs)

    print(f"Done: {remote.api_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
