# Deploy Sphinx documentation action
This is a composite action that deploys pre-built documentation to a separate `gh-pages` branch.
The docs are then published (by default at `https://<username>.github.io/<repo>/`, unless specified otherwise in `docs/source/conf.py`).

The various steps include:
* Removing any previous builds, if present in `docs/build`
* downloading the built html pages (artifact named `docs-build`) into the `docs/build` folder (see the [Build Sphinx Docs action](../build_sphinx_docs/README.md))
* deploying the`html` pages to the `gh-pages` branch. This step uses [peaceiris/actions-gh-pages](https://github.com/peaceiris/actions-gh-pages).

The `use-make` input is optional and defaults to `false`. 
As this input helps to identify the location of the built documentation for deployment, it should match the `use-make` value specified in the [Build Sphinx Docs action](../build_sphinx_docs/README.md).
If set to `true`, it is assumed that the documentation is built using `make` and the `./docs/build/html` directory will be used as the publish directory. 
If set to `false`, the `./docs/build/` directory will be used instead.