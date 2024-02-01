# Upload packages to PyPI

This action uploads pre-built Python packages to the Python Packaging Index
(PyPI). Packages must have been uploaded as an artefact in the `dist/`
directory in a previous step or job in the same GitHub actions workflow.

For this action to work, you must have a PyPI API token stored as a secret in your repository and you need to pass the name of the secret to the action using the `secret_name` input. For example, if the secret's name is `TWINE_API_KEY` (the value would be the PyPI API token):

```yaml
- uses: neuroinformatics-unit/actions/upload_pypi@main
    with:
        secret_name: TWINE_API_KEY
```