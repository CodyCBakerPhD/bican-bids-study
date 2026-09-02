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

`tests/` has a golden-output integration test that runs this script against the real
DANDI sandbox and checks the result against a committed expected-output file. See
`tests/README.md`.
