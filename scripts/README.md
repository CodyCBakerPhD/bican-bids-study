# `dandiset_setup.py`

One script that does three things against a DANDI instance:

1. Create a Dandiset (or target an existing one with `--dandiset-id`).
2. Update its draft metadata from a JSON file.
3. Add owners from a TSV table. Users are **only ever added**; nobody is removed.

## Setup

```bash
pip install -r scripts/requirements.txt
export DANDI_API_KEY=...            # production; use DANDI_SANDBOX_API_KEY for --instance dandi-sandbox
```

Your API key is on your DANDI account page. If the environment variable is not set, the
`dandi` client looks in the system keyring and otherwise prompts for the key.

## Usage

```bash
# Create a new Dandiset, set its metadata, and add owners (try the sandbox first!)
python scripts/dandiset_setup.py --instance dandi-sandbox \
    --metadata scripts/examples/metadata.json --users scripts/examples/users.tsv

# Only add owners to an existing Dandiset
python scripts/dandiset_setup.py --dandiset-id 000123 --users users.tsv

# Only update metadata on an existing Dandiset
python scripts/dandiset_setup.py --dandiset-id 000123 --metadata metadata.json

# Preview without writing anything
python scripts/dandiset_setup.py --metadata metadata.json --users users.tsv --dry-run
```

Other flags: `--name` / `--description` override the values in the metadata JSON,
`--embargo` creates the new Dandiset as embargoed.

## Input files

### `users.tsv`

Tab-separated with a header row. Only the `username` column is read; any other columns
are ignored, so you can keep names or notes alongside. DANDI usernames are GitHub logins.
Blank rows and rows whose username starts with `#` are skipped.

```
username	name
CodyCBakerPhD	Cody Baker
pamela-baker	Pamela Baker
```

The person running the script must already be an owner of the Dandiset (the creator is
one automatically). Every username must belong to an existing, approved DANDI account or
the server rejects the whole request and no owners change.

### `metadata.json`

A JSON object holding any subset of the
[Dandiset metadata schema](https://github.com/dandi/dandi-schema). Top-level keys in the
file replace the same keys in the current draft metadata; keys you do not mention (and
server-managed fields like `id`, `identifier`, `version`, `assetsSummary`) are left as is.
When creating a new Dandiset, `name` and `description` are required, either here or via
`--name` / `--description`.

See `scripts/examples/metadata.json` for a starting point with `name`, `description`,
`license`, `keywords`, and `contributor` (people and a funder).

## Tests

`tests/` has an expected-output integration test that runs this script against the real
DANDI sandbox and checks the result against a committed expected-output file. See
`tests/README.md`.

# `assemble_bids_study.py`

Builds a publication Dandiset out of NWB files that are already on DANDI, laid out as a
BIDS `study` dataset the same way as [001893](https://github.com/dandisets/001893), then
validates and uploads it:

```
<dandiset>/
├── .bidsignore
├── dataset_description.json     DatasetType "study"
├── README.txt
├── participants.tsv / .json     one row per subject
├── mapping.tsv / .json          one row per recorded cell (NWB file)
├── datasets.tsv / .json         one row per source Dandiset
└── sourcedata/raw/sub-<id>/sub-<id>_ses-<id>_icephys.nwb
```

1. Downloads every asset in an inventory table (CSV or TSV) into `sourcedata/raw/`, keeping
   its original path and checking its size and DANDI checksum. Files already downloaded
   are skipped, so an interrupted run can simply be started again.
2. Copies the static files (`dataset_description.json`, `README.txt`, `.bidsignore` and
   the `*.json` column descriptions) from a template directory, e.g.
   [`templates/002029/`](templates/002029).
3. Writes `participants.tsv`, `mapping.tsv` and `datasets.tsv` from the inventory.
   `datasets.tsv` counts each source Dandiset's NWB files (one per cell) on DANDI.
4. Runs the BIDS validator (the one `dandi upload` uses) on every BIDS dataset level, i.e.
   every directory with a `dataset_description.json`, and stops on any error.
5. Uploads with `dandi upload`, then fills `mapping.tsv`'s `dandi_file_url` column with the
   new assets' URLs and uploads `mapping.tsv` again.

## Usage

```bash
pip install -r scripts/requirements.txt
export DANDI_API_KEY=...

# Assemble and validate only (about 11.5 GB for the 002029 inventory)
python scripts/assemble_bids_study.py \
    --inventory sourcedata/HMBA_NHP_BG_NWB_files.tsv \
    --template scripts/templates/002029 \
    --dandiset-id 002029 \
    --bican-subprogram "BICAN HMBA" --grant-number "NIMH UM1MH130981" \
    --output-dir /data/bids-study --no-upload

# Same command without --no-upload to also upload to DANDI:002029
```

The Dandiset is assembled in `<output-dir>/<dandiset-id>/`. Other flags: `--jobs`
(parallel downloads and uploads, default 4), `--validation` (passed to `dandi upload`,
default `require`), `--instance` / `--source-instance` (DANDI instances to upload to and
download from, both default `dandi`).

## Inventory columns

One row per NWB file. The script reads `asset_id`, `path`, `size` and `dandiset_id` to find
and check the file; `subject_id`, `species`, `gender` and `age` (e.g. `8 yrs`) for
`participants.tsv`; and `session_id`, `cell_id`, `cell_name`, `roi_dhba`,
`patched_cell_container_x`, `exp_component_name` and `library_prep` for `mapping.tsv`.
Other columns are ignored.

## Notes on BIDS validity

- `sourcedata/` is opaque to BIDS, which is where the NWB files have to live: no BIDS
  release covers intracellular electrophysiology yet.
- The top-level `.bidsignore` lists `mapping.*` and `datasets.*`, which are not BIDS files,
  and `participants.*`: a `study` dataset has no `sub-*` directories at its root, so the
  validator's `participant_id` cross-check cannot pass there.

## Tests

`tests/test_assemble_bids_study.py` runs the script offline, with fake DANDI clients and
the real BIDS validator: `pytest scripts/tests -k assemble`.
