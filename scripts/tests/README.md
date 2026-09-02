# Golden-output test for `dandiset_setup.py`

A basic example of testing against a live API with a committed "golden"
expected-output file, in the style of
[`labs/kemere/tests`](https://github.com/brain-bbqs/data-ingest-task-force/tree/main/labs/kemere/tests)
in the `brain-bbqs/data-ingest-task-force` repo: fixed input fixtures, a real
run of the code under test, and the result compared against a committed
expected-output file. The difference here is the code under test calls a
live API (the DANDI **sandbox**, never production) rather than converting
files on disk, so the golden comparison is a subset check on the fields we
control instead of full-document equality — see the docstrings in
`_golden.py` and `test_dandiset_setup_sandbox.py` for why.

## Layout

```
tests/
├── fixtures/
│   └── metadata.json          # input handed to dandiset_setup.py
├── expected_output/
│   └── metadata.json          # golden: what should come back afterwards
├── _golden.py                 # shared load/compare helpers
├── test_dandiset_setup_sandbox.py
└── README.md
```

## Running

```bash
pip install -r scripts/requirements.txt -r scripts/requirements-dev.txt
export DANDI_SANDBOX_API_KEY=...    # sandbox.dandiarchive.org -> account -> API keys
pytest scripts/tests -v
```

Without `DANDI_SANDBOX_API_KEY` set, the whole module is skipped rather than
failing — useful for CI that doesn't have sandbox credentials configured.

Every Dandiset the test creates is deleted again at the end (in a `finally`
block, so it runs even if an assertion fails); nothing is left behind on the
sandbox.

### Testing owner-adding

Adding owners is only exercised when `DANDI_SANDBOX_TEST_USERNAME` is also
set, to a **second** sandbox account distinct from the one running the test:

```bash
export DANDI_SANDBOX_TEST_USERNAME=some-other-sandbox-username
pytest scripts/tests -v
```

That sub-test does not use a golden file — see the docstring in
`test_dandiset_setup_sandbox.py` for why "who gets added" can't be pinned to
a fixed fixture — it asserts the invariant instead: the new user ends up an
owner, and nobody who was already an owner is removed.

## Updating the golden file

`expected_output/metadata.json` should equal `fixtures/metadata.json`
(the fields the script is asked to set, echoed back unchanged) plus
`"schemaKey": "Dandiset"`, which the server always adds. If you add a field
to the input fixture, add the same key/value to the golden file.

## A note on this example

This test was written and reviewed but has not been run against the live
DANDI sandbox from this environment — outbound network access to
`sandbox.dandiarchive.org` is blocked in the sandbox this was authored in.
Before relying on it, run it once locally with a real `DANDI_SANDBOX_API_KEY`
and confirm it passes.
