# Build wheels

This action builds Python wheels on multiple operating systems. The built distribution is uploaded as an
artefact in the ``dist`` directory.

The wheels are built using [cibuildwheel](https://cibuildwheel.readthedocs.io/en/stable/).
The operating system is specified in the GitHub actions configuration file that
uses this re-usable action, and all other configuration (e.g. Python versions)
is specified in the `pyproject.toml` file. See the cibuildwheel documentation
for more information on configuration options:
https://cibuildwheel.readthedocs.io/en/stable/options/#configuration-file
