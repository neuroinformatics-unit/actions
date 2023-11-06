# Build Sphinx documentation action
This is a GitHub action that builds Sphinx documentation for your project.

The various steps include:

* setting up Python
  * the version can be specified via the `python-version` input, and defaults to `3.x`
* installing pip and setting up pip cache
* pip installing build dependencies (themes, build tools, etc.) from `docs/requirements.txt`
* Checking that external links in the documentation are not broken 
  * can be disabled via setting the `check-links` input to `false`
* building the html pages from `docs/source` (should contain Sphinx source files) to `docs/build`
* uploading the built html pages as an artifact named `docs-build`, for use in other actions

It can be run upon all pull requests, to ensure that documentation still builds.

It does not publish or deploy the documentation in any way (for that, check the [Deploy Sphinx Docs action](../deploy_sphinx_docs/README.md)).