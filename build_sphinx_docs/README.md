# Build Sphinx documentation action
This is a GitHub action that builds Sphinx documentation for your project.

The various steps include:

* setting up Python
* installing pip and setting up pip cache
* pip installing build dependencies (themes, build tools, etc.) from `docs/requirements.txt`
* building the html pages from `docs/source` (should contain Sphinx source files) to `docs/build`
* uploading the built html pages as an artifact named `docs-build`, for use in other actions

It can be run upon all pull requests, to ensure that documentation still builds.

It does not publish or deploy the documentation in any way (for that, check the [Deploy Sphinx Docs action](../deploy_sphinx_docs/README.md)).