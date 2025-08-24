# Deploy Sphinx documentation multi-version action
This composite GitHub Action deploys pre-built Sphinx documentation to the gh-pages branch, organized into per-version folders. It is intended to be used together with a build action (such as build_sphinx_docs) that prepares the HTML output as an artifact.
The docs are then published (by default at `https://<username>.github.io/<repo>/<version>`, unless specified otherwise in `docs/source/conf.py`).

## Features
* Removes any previous builds, if present in `docs/build`
* Downloads the built html pages (artifact named `docs-build`) into the `docs/build` folder (see the [Build Sphinx Docs action](../build_sphinx_docs/README.md))
* Pushes the built HTML pages to the gh-pages branch under the correct version
* Updates switcher.json to mark the new version as latest
* Maintains a latest symlink for convenience

## Inputs

| Name           | Required | Type    | Default | Description |
|----------------|----------|---------|---------|-------------|
| `secret_input` | ✅ Yes   | string  | —       | The GitHub token used for authentication. |
| `switcher_url` | ✅ Yes   | string  | —       | URL of the `switcher.json` file, which will be updated with the new version info. |
| `use-make`     | ❌ No    | boolean | `false` | Whether the docs were built with `make`. If `true`, deploys from `./docs/build/html`; otherwise from `./docs/build`. |

> ⚠️ Make sure the value of `use-make` matches what was used in the [Build Sphinx Docs action](../build_sphinx_docs/README.md), otherwise deployment may fail.

## Usage Example

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
        uses: ./.github/actions/build_sphinx_docs
        with:
          use-make: true

      - name: Deploy documentation
        uses: ./.github/actions/deploy_sphinx_docs_multi_version
        with:
          secret_input: ${{ secrets.GITHUB_TOKEN }}
          use-make: true
          switcher_url: https://<username>.github.io/<repo>/latest/_static/switcher.json
```