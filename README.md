# Re-usable GitHub Action Workflows

This repository contains a number of GitHub Actions composite actions that
can be used for running continuous integration across multiple repositories.

## Test
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
    - uses: neuroinformatics-unit/actions/test@v3
        with:
          python-version: ${{ matrix.python-version }}
          # Replace CODECOV_TOKEN with the name of the repository secret containing the upload token from codecov.io
          secret-codecov-token: ${{ secrets.CODECOV_TOKEN }}
          use-xvfb: true  # Optional, defaults to false if not specified
          codecov-flags: "my-flag"  # Optional
```

## Test (uv)
An alternative to the [Test](#test) action above that doesn't rely on `tox`.
Runs Python tests with `pytest`, using `uv` to install the package and its dependencies, and uploads a coverage report to `codecov`.
See the [Test (uv) README](./test-uv/README.md) for all inputs.

Example usage:

```yaml
jobs:
  test:
    name: ${{ matrix.platform }} py${{ matrix.python-version }}
    runs-on: ${{ matrix.platform }}
    strategy:
      matrix:
        platform: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.12", "3.13"]

    steps:
    - uses: neuroinformatics-unit/actions/test-uv@v3
      with:
        python-version: ${{ matrix.python-version }}
        secret-codecov-token: ${{ secrets.CODECOV_TOKEN }}
```

## Lint
Lints code using `pre-commit`. A `.pre-commit-config.yaml` file must be present
in the root of the repository.

Example usage:

```yaml
jobs:
  linting:
    name: Run linting
    runs-on: ubuntu-latest
    steps:
    - uses: neuroinformatics-unit/actions/lint@v3
```

## Manifest
Checks that no files are missing from the source distribution using
`pip-manifest`.

Example usage:
```yaml
jobs:
  manifest:
    name: Check manifest
    runs-on: ubuntu-latest
    steps:
    - uses: neuroinformatics-unit/actions/check_manifest@v3
```

## Build distributions
Build source and wheel distributions for upload to PyPI.

Example usage:
```yaml
build_sdist_wheels:
name: Build source distribution
needs: [test]
if: github.event_name == 'push' && github.ref_type == 'tag'
runs-on: ubuntu-latest
steps:
- uses: neuroinformatics-unit/actions/build_sdist_wheels@v3
```

## Build Sphinx documentation
Ensures that Sphinx docs can be built upon pushes and pull requests to any branch.

Example usage:
```yaml
build_sphinx_docs:
  name: Build Sphinx Docs
  runs-on: ubuntu-latest
  steps:
  - uses: neuroinformatics-unit/actions/build_sphinx_docs@v3
    with:
      python-version: 3.10
      check-links: false
      use-make: false
```
The `python-version` input is optional and defaults to `3.x` (where `x` is the latest stable version of Python 3 available on the GitHub Actions platform)

The `check-links` input is also optional and defaults to `true`. If set to `true`, the action will use the Sphinx linkcheck builder to check the integrity of all **external** links.

The `use-make` input is optional and defaults to `false`. If set to `true`, the action will use the `make` utility with a custom `docs/Makefile` to build the pages from `SOURCEDIR` to `BUILDDIR` as defined in the Makefile. If set to `false`, the action will use `sphinx-build` to build the pages from `docs/source` to `docs/build`.

## Publish Sphinx documentation
Deploys pre-built documentation to GitHub Pages.

Example usage:
```yaml
deploy_sphinx_docs:
  name: Deploy Sphinx Docs
  needs: build_sphinx_docs
  permissions:
      contents: write
  if: (github.event_name == 'push' && github.ref_type == 'tag') || github.event_name == 'workflow_dispatch'
  runs-on: ubuntu-latest
  steps:
  - uses: neuroinformatics-unit/actions/deploy_sphinx_docs@v3
    with:
      secret_input: ${{ secrets.GITHUB_TOKEN }}
      use-make: false
```

To deploy versioned docs you can instead use the `deploy_sphinx_docs_multiversion` action.

```yaml
name: Deploy Docs

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy-docs:
    runs-on: ubuntu-latest
    steps:
      - name: Build documentation
        uses: neuroinformatics-unit/actions/build_sphinx_docs@v3
        with:
          use-make: true

      - name: Deploy documentation
        uses: neuroinformatics-unit/actions/deploy_sphinx_docs_multiversion@v3
        with:
          secret_input: ${{ secrets.GITHUB_TOKEN }}
          use-make: true
          switcher-url: https://<username>.github.io/<repo>/latest/_static/switcher.json

```
The `use-make` input is optional as well and defaults to `false`. If set to `true`, the action will assume that the Sphinx documentation is built using `make` and will use the `./docs/build/html` directory as the publish directory. If set to `false`, it will use the `./docs/build/` directory instead. 


## Green DiSC toolkit
Actions for the [Green DiSC toolkit](https://github.com/neuroinformatics-unit/greendisc-toolkit), which helps research groups gather and review evidence for Green DiSC certification: see [`greendisc_toolkit/`](greendisc_toolkit/README.md).

## Full Workflows
* An example workflow, including linting, testing and release can be found at [example_test_and_deploy.yml](./example_test_and_deploy.yml).
* An example workflow, for building and deploying documentation can be found at [example_build_and_deploy_docs.yml](./example_docs_build_and_deploy.yml).
# Releasing a new version

1. If incrementing a major version (e.g. going from v3 > v4), first open a PR that updates the references to these actions in the READMEs and example workflows to the new major tag.
The following snippet bumps all references to the next major version (run from the repo root in a Unix shell, or Git Bash/WSL on Windows):

```bash
PATTERN='neuroinformatics-unit/actions/[A-Za-z_-]+@v[0-9]+'
FILES=$(grep -rlE "$PATTERN" --include='*.md' --include='*.yml' --include='*.yaml' .)
CURRENT=$(grep -hoE "$PATTERN" $FILES | sed -E 's/.*@v//' | sort -n | tail -1)
NEXT=$((CURRENT + 1))
echo "Bumping v$CURRENT -> v$NEXT"
NEXT=$NEXT perl -pi -e 's#(neuroinformatics-unit/actions/[A-Za-z_-]+)\@v\d+\b#$1\@v$ENV{NEXT}#g' $FILES
```

2. Create a new release through the GitHub releases UI. Make sure you add the appropriate tag to the release.
3. If not incrementing a major version (ie. going from 2.1 > 2.2), move the major tag (e.g. <tagname>=v2) to the most recent tag:

```bash
git push origin :refs/tags/<tagname>
git tag -fa <tagname>
git push upstream main --tags
```

This means any actions specifying (e.g.) `v2` will automatically use the new minor version of the actions.
