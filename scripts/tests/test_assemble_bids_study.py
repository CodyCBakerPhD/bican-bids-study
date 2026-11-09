"""
Offline tests for ``assemble_bids_study.py``.

The DANDI API is replaced by small in-memory fakes, so nothing touches the network; the
BIDS validator (``bids-validator-deno``, installed with ``dandi``) runs for real.
"""

from __future__ import annotations

import csv
import json
import sys
import types
from pathlib import Path

import pytest
from dandischema.digests.dandietag import DandiETag

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assemble_bids_study as abs_

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "002029"
API = "https://api.example.org/api"


def json_keys(path: Path) -> list[str]:
    return list(json.loads(path.read_text()))


def make_row(subject: str, session: str, **overrides: str) -> dict[str, str]:
    row = {
        "asset_id": f"asset-{session}",
        "path": f"sub-{subject}/sub-{subject}_ses-{session}_icephys.nwb",
        "size": "0",
        "dandiset_id": "000569",
        "subject_id": subject,
        "session_id": session,
        "species": "Macaca nemestrina",
        "gender": "F",
        "age": "8 yrs",
        "cell_id": f"cell-{session}",
        "cell_name": f"QN.{session}",
        "roi_dhba": "Pu",
        "patched_cell_container_x": f"PNS4_{session}",
        "exp_component_name": f"AB-{session}",
        "library_prep": f"L8S4_{session}",
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def test_participants_one_row_per_subject():
    rows = [
        make_row("2", "20", gender="M", age="10 yrs"),
        make_row("1", "10"),
        make_row("1", "11"),
    ]
    assert abs_.build_participants(rows) == [
        {
            "participant_id": "sub-1",
            "species_name": "Macaca nemestrina",
            "species_ncbi_taxon": "NCBITaxon:9545",
            "sex_at_birth": "Female",
            "age": "8",
        },
        {
            "participant_id": "sub-2",
            "species_name": "Macaca nemestrina",
            "species_ncbi_taxon": "NCBITaxon:9545",
            "sex_at_birth": "Male",
            "age": "10",
        },
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"species": "Macaca unknownus"},
        {"gender": "X"},
        {"age": "about 8"},
        {"age": "9 yrs"},
    ],
)
def test_participants_rejects_bad_or_conflicting_rows(bad):
    with pytest.raises(SystemExit):
        abs_.build_participants([make_row("1", "10"), make_row("1", "11", **bad)])


def test_mapping_links_new_and_source_assets():
    rows = [make_row("1", "11"), make_row("1", "10")]
    new_url = f"{API}/assets/new-10/download/"
    target = {"sourcedata/raw/sub-1/sub-1_ses-10_icephys.nwb": new_url}
    mapping = abs_.build_mapping(rows, API, target)
    assert [m["session_id"] for m in mapping] == ["ses-10", "ses-11"]
    assert mapping[0]["dandi_file_url"] == new_url
    assert mapping[1]["dandi_file_url"] == ""  # not uploaded yet
    assert mapping[0]["source_dandi_file_url"] == f"{API}/assets/asset-10/download/"
    assert set(mapping[0]) == set(json_keys(TEMPLATE / "mapping.json"))


def test_write_tsv_leaves_unchanged_file_alone(tmp_path):
    path = tmp_path / "t.tsv"
    assert abs_.write_tsv(path, [{"a": "1", "b": "2"}]) is True
    assert path.read_text() == "a\tb\n1\t2\n"
    assert abs_.write_tsv(path, [{"a": "1", "b": "2"}]) is False
    assert abs_.write_tsv(path, [{"a": "1", "b": "3"}]) is True


def test_template_sidecars_describe_every_column():
    rows = [make_row("1", "10")]
    datasets = [dict.fromkeys(json_keys(TEMPLATE / "datasets.json"), "")]
    for table, sidecar in [
        (abs_.build_participants(rows), "participants.json"),
        (abs_.build_mapping(rows, API, {}), "mapping.json"),
        (datasets, "datasets.json"),
    ]:
        assert list(table[0]) == json_keys(TEMPLATE / sidecar), sidecar


# --------------------------------------------------------------------------- #
# Whole run against fake DANDI clients
# --------------------------------------------------------------------------- #
class FakeAsset:
    def __init__(self, path: str, content: bytes, identifier: str = "", etag: str = ""):
        self.path, self.content, self.identifier = path, content, identifier
        self.size = len(content)
        self.etag = etag

    @property
    def base_download_url(self) -> str:
        return f"{API}/assets/{self.identifier}/download/"

    def download(self, filepath) -> None:
        Path(filepath).write_bytes(self.content)

    def get_raw_digest(self, digest_type: str) -> str:
        assert digest_type == "dandi:dandi-etag"
        return self.etag


class FakeDandiset:
    def __init__(self, identifier: str, assets: list):
        self.identifier, self.assets = identifier, assets
        self.api_url = f"{API}/dandisets/{identifier}/"
        self.version = types.SimpleNamespace(name=f"Dandiset {identifier}")

    def get_raw_metadata(self) -> dict:
        return {"identifier": f"DANDI:{self.identifier}", "name": self.version.name}

    def get_assets(self) -> list:
        return list(self.assets)


class FakeClient:
    def __init__(
        self, source_assets: dict[str, FakeAsset], dandisets: dict[str, FakeDandiset]
    ):
        self.source_assets, self.dandisets = source_assets, dandisets
        self.api_url = API
        self.dandi_instance = types.SimpleNamespace(gui="https://dandi.example.org")

    def get_asset(self, asset_id: str) -> FakeAsset:
        return self.source_assets[asset_id]

    def get_dandiset(
        self, dandiset_id: str, version_id=None, lazy=True
    ) -> FakeDandiset:
        return self.dandisets[dandiset_id]


@pytest.fixture
def fake_run(tmp_path, monkeypatch):
    """Fake source and target Dandisets; returns (inventory, rows, target, upload_calls)."""
    rows = [
        make_row("1", "10"),
        make_row("1", "11"),
        make_row("2", "20", dandiset_id="001626"),
    ]
    source_assets = {}
    for row in rows:
        content = f"fake NWB for {row['session_id']}".encode()
        row["size"] = str(len(content))
        etag_file = tmp_path / "etag"
        etag_file.write_bytes(content)
        etag = DandiETag.from_file(etag_file).as_str()
        source_assets[row["asset_id"]] = FakeAsset(row["path"], content, etag=etag)
    inventory = tmp_path / "inventory.tsv"
    with inventory.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    target = FakeDandiset("002029", [])
    sources = {
        "000569": FakeDandiset(
            "000569", [FakeAsset(f"sub-x/{i}.nwb", b"") for i in range(5)]
        ),
        "001626": FakeDandiset("001626", [FakeAsset("sub-y/0.nwb", b"")]),
    }
    client = FakeClient(source_assets, {"002029": target, **sources})
    monkeypatch.setattr(
        abs_,
        "DandiAPIClient",
        types.SimpleNamespace(for_dandi_instance=lambda *a, **k: client),
    )

    upload_calls = []

    def fake_upload(paths, **kwargs):
        root = tmp_path / "out" / "002029"
        upload_calls.append([Path(p).relative_to(root).as_posix() for p in paths])
        files = sorted(
            p for p in root.rglob("*") if p.is_file() and p.name != "dandiset.yaml"
        )
        target.assets = [
            FakeAsset(p.relative_to(root).as_posix(), b"", identifier=f"new-{i}")
            for i, p in enumerate(files)
        ]

    monkeypatch.setattr(abs_, "upload", fake_upload)
    return inventory, rows, target, upload_calls


def run(tmp_path, inventory, *extra):
    return abs_.main(
        [
            "--inventory", str(inventory),
            "--template", str(TEMPLATE),
            "--dandiset-id", "002029",
            "--output-dir", str(tmp_path / "out"),
            "--bican-subprogram", "BICAN HMBA",
            "--grant-number", "NIMH UM1MH130981",
            *extra,
        ]
    )  # fmt: skip


def test_assembles_validates_and_uploads(tmp_path, fake_run):
    inventory, rows, _, upload_calls = fake_run
    assert run(tmp_path, inventory) == 0
    root = tmp_path / "out" / "002029"

    files = sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )
    assert files == sorted(
        [
            ".bidsignore",
            "README.txt",
            "dandiset.yaml",
            "dataset_description.json",
            "datasets.json",
            "datasets.tsv",
            "mapping.json",
            "mapping.tsv",
            "participants.json",
            "participants.tsv",
            *(f"sourcedata/raw/{row['path']}" for row in rows),
        ]
    )
    for row in rows:
        assert (root / "sourcedata/raw" / row["path"]).read_bytes() == (
            f"fake NWB for {row['session_id']}".encode()
        )

    datasets = (root / "datasets.tsv").read_text().splitlines()
    assert datasets[1:] == [
        "000569\thttps://dandi.example.org/dandiset/000569\tBICAN HMBA\tNIMH UM1MH130981\t5",
        "001626\thttps://dandi.example.org/dandiset/001626\tBICAN HMBA\tNIMH UM1MH130981\t1",
    ]

    # Whole Dandiset first, then mapping.tsv again once the new asset URLs are known.
    assert upload_calls == [["."], ["mapping.tsv"]]
    with (root / "mapping.tsv").open() as handle:
        mapping = list(csv.DictReader(handle, delimiter="\t"))
    assert all(m["dandi_file_url"].startswith(f"{API}/assets/new-") for m in mapping)

    # A second run finds everything in place and only refreshes the upload.
    upload_calls.clear()
    assert run(tmp_path, inventory) == 0
    assert upload_calls == [["."]]


def test_no_upload_stops_after_validation(tmp_path, fake_run):
    inventory, _, _, upload_calls = fake_run
    assert run(tmp_path, inventory, "--no-upload") == 0
    assert upload_calls == []


def test_bids_errors_block_upload(tmp_path, fake_run, capsys):
    inventory, _, _, upload_calls = fake_run
    template = tmp_path / "template"
    template.mkdir()
    (template / "dataset_description.json").write_text(
        '{"Name": "missing BIDSVersion"}'
    )
    assert abs_.main(
        ["--inventory", str(inventory), "--template", str(template),
         "--dandiset-id", "002029", "--output-dir", str(tmp_path / "out")]
    ) == 1  # fmt: skip
    assert upload_calls == []
    assert "ERROR" in capsys.readouterr().out


def test_bad_checksum_is_rejected(tmp_path, fake_run):
    inventory, rows, _, _ = fake_run
    abs_.DandiAPIClient.for_dandi_instance().source_assets[
        rows[0]["asset_id"]
    ].etag = "bad-1"
    with pytest.raises(RuntimeError, match="checksum"):
        run(tmp_path, inventory, "--no-upload")
    raw = tmp_path / "out" / "002029" / "sourcedata" / "raw"
    assert not (raw / rows[0]["path"]).exists()
    assert not list(raw.rglob("*.part"))


def test_files_outside_inventory_block_upload(tmp_path, fake_run):
    inventory, _, _, upload_calls = fake_run
    stray = tmp_path / "out" / "002029" / "sourcedata" / "raw" / "sub-9" / "stray.nwb"
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"")
    with pytest.raises(SystemExit, match="not in the inventory"):
        run(tmp_path, inventory)
    assert upload_calls == []
