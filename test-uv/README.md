# Python test (uv) action
This is a GitHub action that runs Python tests with `pytest`, using [uv](https://docs.astral.sh/uv/) to manage the environment, and reports coverage to [codecov.io](https://about.codecov.io/).
Unlike the [Python test action](../test/README.md), it does not use `tox`.

The various steps include:

* checking out the repository
* installing uv and setting up Python
  * the version must be specified via the required `python-version` input
  * the uv cache is enabled and keyed on `pyproject.toml` files
* installing dependencies from the `main` branch of other GitHub repositories (optional)
  * pass a comma-separated list of `<owner>/<repo>` names via the `install-main-branch` input, e.g. `neuroinformatics-unit/movement,napari/napari`
* installing your package in editable mode with its optional dependencies (extras)
  * the extras are specified as a comma-separated list via the `install-extras` input, and default to `dev`
  * additional packages can be installed on top via the `extra-dependencies` input (space-separated, e.g. `"numpy<2 pandas"`)
* setting up a headless display, for tests that need one (e.g. GUI or 3D rendering tests)
  * optional, enabled with `use-headless: true` (defaults to `false`). This step uses [pyvista/setup-headless-display-action](https://github.com/pyvista/setup-headless-display-action) with Qt support.
  * Mesa3D offscreen rendering is installed by default; set `install-mesa3d-offscreen: false` to skip it
* running `pytest`
  * arguments can be passed via the `pytest-args` input (e.g. `"-v --cov=my_package"`)
* reporting coverage to codecov.io using [codecov/codecov-action](https://github.com/codecov/codecov-action)
  * the upload token is passed via the `secret-codecov-token` input, see the [warning](#warning) below
  * flags can be passed via the `codecov-flags` input

## Example usage

```yaml
jobs:
  test:
    name: ${{ matrix.os }} py${{ matrix.python-version }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.12", "3.13"]
    steps:
    - uses: neuroinformatics-unit/actions/test-uv@v3
      with:
        python-version: ${{ matrix.python-version }}
        # Replace CODECOV_TOKEN with the name of the repository secret containing the upload token from codecov.io
        secret-codecov-token: ${{ secrets.CODECOV_TOKEN }}
        pytest-args: "--cov=my_package"  # Optional
        install-extras: "dev"  # Optional, defaults to "dev"
        use-headless: true  # Optional, defaults to false
        codecov-flags: "my-flag"  # Optional
```

## Warning

Tokenless uploads to codecov.io are being phased out. If `secret-codecov-token` is not set, the action emits a deprecation warning, and this input will become required in the future.
You should [provide an upload token](https://docs.codecov.com/docs/quick-start#step-2-get-the-repository-upload-token) from codecov.io, stored as a repository secret and passed to the action as shown above.

Note that `pytest` must be installed as part of the extras you install (e.g. in the `dev` extra of your `pyproject.toml`), since the action does not install it separately.
For coverage reports to be produced, `pytest-cov` must also be installed and `--cov` passed via `pytest-args` (or configured in your `pyproject.toml`).
