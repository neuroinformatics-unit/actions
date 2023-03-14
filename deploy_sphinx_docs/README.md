# Deploy Sphinx documentation action
This is a composite action that deploys pre-built documentation to a separate `gh-pages` branch.
The docs are then published (by default at `https://<username>.github.io/<repo>/`, unless specified otherwise in `docs/source/conf.py`).

The various steps include:
* Removing any previous builds, if present in `docs/build`
* downloading the built html pages (artifact named `docs-build`) into the `docs/build` folder (see the [Build Sphinx Docs action](../build_sphinx_docs/README.md))
* deploying the`html` pages to the `gh-pages` branch. This step uses [peaceiris/actions-gh-pages](https://github.com/peaceiris/actions-gh-pages).