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
    - uses: neuroinformatics-unit/actions/test@main
        with:
          python-version: ${{ matrix.python-version }}
          # Replace CODECOV_TOKEN with the name of the repository secret containing the upload token from codecov.io
          secret-codecov-token: ${{ secrets.CODECOV_TOKEN }}
          use-xvfb: true  # Optional, defaults to false if not specified
          codecov-flags: "my-flag"  # Optional
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
    - uses: neuroinformatics-unit/actions/lint@main
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
    - uses: neuroinformatics-unit/actions/check_manifest@main
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
- uses: neuroinformatics-unit/actions/build_sdist_wheels@main
```

## Upload to PyPI
Upload distributions to PyPI.

Example usage:
```yaml
upload_all:
    name: Publish build distributions
    needs: [build_sdist_wheels]
    runs-on: ubuntu-latest
    steps:
    - uses: neuroinformatics-unit/actions/upload_pypi@main
      with:
        # Replace MY_PYPI_KEY with the name of the repository secret containing the PyPI API key
        secret-pypi-key: ${{ secrets.MY_PYPI_KEY }}
```

## Build Sphinx documentation
Ensures that Sphinx docs can be built upon pushes and pull requests to any branch.

Example usage:
```yaml
build_sphinx_docs:
  name: Build Sphinx Docs
  runs-on: ubuntu-latest
  steps:
  - uses: neuroinformatics-unit/actions/build_sphinx_docs@main
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
  - uses: neuroinformatics-unit/actions/deploy_sphinx_docs@main
    with:
      secret_input: ${{ secrets.GITHUB_TOKEN }}
      use-make: false
```
The `use-make` input is optional and defaults to `false`. If set to `true`, the action will assume that the Sphinx documentation is built using `make` and will use the `./docs/build/html` directory as the publish directory. If set to `false`, it will use the `./docs/build/` directory instead. 

## Full Workflows
* An example workflow, including linting, testing and release can be found at [example_test_and_deploy.yml](./example_test_and_deploy.yml).
* An example workflow, for building and deploying documentation can be found at [example_build_and_deploy_docs.yml](./example_docs_build_and_deploy.yml).
# Releasing a new version

1. Create a new release through the GitHub releases UI. Make sure you add the appropriate tag to the release.
2. If not incrementing a major version (ie. going from 2.1 > 2.2), move the major tag (e.g. <tagname>=v2) to the most recent tag:

```bash
git push origin :refs/tags/<tagname>
git tag -fa <tagname>
git push upstream main --tags
```

This means any actions specifying (e.g.) `v2` will automatically use the new minor version of the actions.
