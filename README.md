# Re-usable GitHub Action Workflows

This repository contains a number of GitHub Actions composite actions that
can be used for running continuous integration across BrainGlobe repositories.
If you are using Github Actions you are probably already

## test
Runs Python tests using `tox`, and uploads a coverage report to `codecov`.
A `tox.ini` file must be present in the root of the repository.

Example usage for running tests across a matrix of operating systems and
Python versions:

```yaml
jobs:
  test:
    name: ${{ matrix.platform }} py${{ matrix.python-version }}
    runs-on: ${{ matrix.platform }}
    strategy:
      matrix:
        platform: [ubuntu-latest, windows-latest, macos-latest]
        python-version: [3.9, 3.10]

    steps:
      - uses: brainglobe/actions/test@main
        with:
          python-version: ${{ matrix.python-version }}
```

## lint
Lints code using `pre-commit`. A `.pre-commit-config.yaml` file must be present
in the root of the repository.

Example usage:

```yaml
jobs:
  linting:
    name: Run linting
    runs-on: ubuntu-latest
    steps:
      - uses: brainglobe/actions/lint@main
```

## manifest
Checks that no files are missing from the source distribution using
`pip-manifest`.

Example usage:
```yaml
jobs:
  manifest:
    name: Check manifest
    runs-on: ubuntu-latest
    steps:
      - uses: brainglobe/actions/check_manifest@main
```
