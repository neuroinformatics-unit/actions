# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains reusable GitHub Actions composite actions for the neuroinformatics-unit organization. These actions standardize CI/CD workflows across multiple Python repositories.

## Repository Structure

Each action lives in its own directory with an `action.yml` (or `action.yaml`) file:

- **test/**: Run Python tests using tox and upload coverage to codecov
- **lint/**: Run pre-commit linting (requires `.pre-commit-config.yaml` in consuming repo)
- **check_manifest/**: Verify package manifest using check-manifest
- **build_sdist_wheels/**: Build source distribution and wheels using `pipx run build`
- **build_sphinx_docs/**: Build Sphinx documentation with optional link checking
- **deploy_sphinx_docs/**: Deploy pre-built docs to GitHub Pages
- **deploy_sphinx_docs_multiversion/**: Deploy versioned docs with switcher.json support
- **check_tag_on_main/**: Check if triggering tag points to a commit on main branch

## Development Workflow

There is no build or test process for this repository itself. Changes are tested by consuming repositories.

### Making Changes

1. Edit the `action.yml` file in the relevant action directory
2. Test by referencing your branch from a consuming repository: `uses: neuroinformatics-unit/actions/<action>@<branch>`
3. Create a release through GitHub's releases UI

### Releasing

1. Create a new release through GitHub releases with an appropriate tag
2. If not incrementing a major version, move the major tag to the new release:
   ```bash
   git push origin :refs/tags/<tagname>
   git tag -fa <tagname>
   git push upstream main --tags
   ```
   This allows actions specifying `@v2` to automatically use the latest minor version.

## Key Implementation Details

- **test action**: Uses `tox` and `tox-gh-actions` for test execution; optional XVFB support for GUI testing on Linux
- **build_sphinx_docs action**: Supports both `sphinx-build` directly and `make html`; can use either `docs/requirements.txt` or `pyproject.toml [docs]` extras
- **deploy_sphinx_docs_multiversion action**: Maintains a `switcher.json` for version switching; creates symbolic link from `latest` to current release version
- Dependabot is configured to update action versions in each action directory
