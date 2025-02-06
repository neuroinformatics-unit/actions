# Upload packages to PyPI

> [!Warning]
> This workflow is currently incompatible with PyPI publish GitHub Action > v1.9.
> See [here](https://github.com/pypa/gh-action-pypi-publish/blob/release/v1.9/README.md#trusted-publishing) for more details.

This action uploads pre-built Python packages to the Python Packaging Index
(PyPI). Packages must have been uploaded as an artefact in the `dist/`
directory in a previous step or job in the same GitHub actions workflow.

For this action to work, you must have a PyPI API token stored as a repository
secret and that must be passed as an input to the action.

```yaml
- uses: neuroinformatics-unit/actions/upload_pypi@main
      with:
        secret-pypi-key: ${{ secrets.MY_PYPI_KEY }}
```
