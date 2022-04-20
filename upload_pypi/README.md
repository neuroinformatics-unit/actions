# Upload packages to PyPi

This action uploads pre-built Python packages to the Python Packaging Index
(PyPi). Packages must have been uploaded as an artefact in the `dist/`
directory in a previous step or job in the same GitHub actions workflow.

Your PyPi API key must be specified as the `twine-api-key` secret to the
composite action.
