# Upload packages to PyPI

This action uploads pre-built Python packages to the Python Packaging Index
(PyPI). Packages must have been uploaded as an artefact in the `dist/`
directory in a previous step or job in the same GitHub actions workflow.

For this action to work, you must have a PyPI API token stored as a repository secret and you need to pass the name of that secret to the `pypi-api-key`, under the `secrets` context. For example, if your secret's name is `MY_PYPI_KEY`:

```yaml
- uses: neuroinformatics-unit/actions/upload_pypi@main
    secrets:
        pypi-api-key: ${{ secrets.MY_PYPI_KEY }}
```

This way your secret will be passed from the caller workflow to the reusable action, without exposing it in the action's code.