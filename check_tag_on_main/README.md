# Check if trigger tag is on `main`

This action checks if the workflow is triggered by a tag, and if that tag points to a commit on the main branch.

This is useful to only run certain steps in a workflow if the tag points to a commit on the main branch.

## Examples of usage
To use this action:
- add it as a step to your workflow, and
- in any subsequent steps that you want to only run if the trigger is a tag pointing to main, add the action's job ID to `need` and use the output variable of the action in the `if` condition.

For example, to only build and publish the source distribution if the trigger is a tag that points to a commit on the main branch, we would add a step with this action to our workflow and use the output variable in the next steps:

```yaml
  check_tag:
    name: Check if trigger is tag and if it points to commit on main
    runs-on: ubuntu-latest
    outputs:
      tag_on_main: ${{ steps.check.outputs.tag_on_main }}
    steps:
      - uses: neuroinformatics-unit/actions/check_tag_on_main@v1
        id: check

  # Build if trigger is a pushed tag that points to commit on main
  build_sdist_wheels:
    name: Build source distribution
    needs: [test, check_tag]  # add check_tag to `needs`
    if: github.event_name == 'push' && needs.check_tag.outputs.tag_on_main == 'true'
    runs-on: ubuntu-latest
    steps:
    - uses: neuroinformatics-unit/actions/build_sdist_wheels@v2

  # Publish to PyPI if trigger is a pushed tag that points to commit on main
  upload_all:
    name: Publish build distributions
    needs: [build_sdist_wheels, check_tag]  # add check_tag to `needs`
    if: github.event_name == 'push' && needs.check_tag.outputs.tag_on_main == 'true'
    runs-on: ubuntu-latest
    steps:
    - uses: actions/download-artifact@v6
      with:
        name: artifact
        path: dist
    - uses: pypa/gh-action-pypi-publish@release/v1
      with:
        user: __token__
        password: ${{ secrets.TWINE_API_KEY }}

```

Similarly, to only deploy the documentation if the trigger is a tag that points to a commit on the main branch, we would add this step to the jobs in our workflow:
```yaml
  build_sphinx_docs:
    name: Build Sphinx Docs
    runs-on: ubuntu-latest
    steps:
      - uses: neuroinformatics-unit/actions/build_sphinx_docs@main
        with:
          python-version: 3.12
          use-make: true
          fetch-tags: true
          use-artifactci: lazy

  # Check tag
  check_tag:
    name: Check if trigger is tag and if it points to commit on main
    runs-on: ubuntu-latest
    outputs:
      tag_on_main: ${{ steps.check.outputs.tag_on_main }}
    steps:
      - uses: neuroinformatics-unit/actions/check_tag_on_main@v1
        id: check
          
  # Deploy documentation if trigger is a pushed tag that points to commit on main
  deploy_sphinx_docs:
    name: Deploy Sphinx Docs
    needs: [build_sphinx_docs, check_tag]  # add check_tag to `needs`
    permissions:
      contents: write
    if: (github.event_name == 'push' && (github.ref == 'refs/heads/main' || needs.check_tag.outputs.tag_on_main == 'true')) || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    steps:
      - uses: neuroinformatics-unit/actions/deploy_sphinx_docs@v2
        with:
          secret_input: ${{ secrets.GITHUB_TOKEN }}
          use-make: true
```