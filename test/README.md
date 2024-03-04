# Python test action

This action:

- Takes the python version as input
- Installs tox
- Uses tox to run tests from a tox.ini file
- Reports coverage to [codecov.io](https://about.codecov.io/)

With `v4` of the Codecov GitHub Action, tokenless uploads are not supported. You must [provide an upload token](https://docs.codecov.com/docs/frequently-asked-questions#section-where-is-the-repository-upload-token-found-) from [codecov.io](https://about.codecov.io/) stored as a repository secret and that must be passed as an input to the action.

```yaml
- uses: neuroinformatics-unit/actions/test@main
      with:
        secret-codecov-token: ${{ secrets.CODECOV_TOKEN }}
```