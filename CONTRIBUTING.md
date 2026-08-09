# Contributing

FastDataGov welcomes issues and pull requests under the MIT license.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
pytest -q
python main.py
```

The default environment uses deterministic demo data and requires no platform
credentials. Keep the offline suite deterministic and network-free.

## Pull requests

- Keep routes and UI grouped by governance capability.
- Qualify every PostgreSQL table with `fastdatagov.`.
- Add append-only migrations; do not edit an already released migration.
- Preserve the adapter contract and add contract tests for new platforms.
- Label lineage evidence and avoid overstating platform coverage.
- Keep secrets, real customer metadata, and absolute developer paths out of
  source, fixtures, screenshots, and logs.
- Ensure forms work without JavaScript and remain keyboard accessible.
- Run `pytest -q`, `python -m compileall -q fastdatagov main.py`, and
  `git diff --check` before opening a pull request.

## Commit scope

Prefer small commits that keep schema, repository, routes, UI, and tests for one
capability understandable together. Security-sensitive changes should include
their threat assumptions in the pull request description.
