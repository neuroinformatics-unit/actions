# Publish Sphinx documentation action
This is a composite action that builds Sphinx documentation and deploys the built `html` pages to a separate `gh-pages` branch. The website is then published at `https://<username>.github.io/<repo>/` by default.

The various steps include:
* setting up Python
* installing pip and setting up pip cache
* pip installing build dependencies (themes, build tools, etc.) from `docs/requirements.txt`
* building the `html` pages from `docs/source` (should contain Sphinx source files) to `docs/build`
* deploying the built `html` pages to the `gh-pages` branch. This step uses [peaceiris/actions-gh-pages](https://github.com/peaceiris/actions-gh-pages).