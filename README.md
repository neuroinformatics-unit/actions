# Re-usable GitHub Action Workflows

This repository contains a number of GitHub Actions composite actions that
can be used for running continuous integration across BrainGlobe repositories.
If you are using Github Actions you are probably already

## test
Runs Python tests using and uploads a coverage report to `codecov`.

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
    - uses: neuroinformatics-unit/actions/test@main
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
    - uses: neuroinformatics-unit/actions/lint@main
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
    - uses: neuroinformatics-unit/actions/check_manifest@main
```

# Releasing a new version

1. Create a new release through the GitHub releases UI. Make sure you add the appropriate tag to the release.
2. If not incrementing a major version (ie. going from 2.1 > 2.2), move the major tag (e.g. <tagname>=v2) to the most recent tag:

```bash
git push origin :refs/tags/<tagname>
git tag -fa <tagname>
git push upstream main --tags
```

  This means any actions specifying (e.g.) `v2` will automatically use the new minor version of the actions.

