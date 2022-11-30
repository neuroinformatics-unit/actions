# Check Sphinx documentation action
This is a GitHub action that looks for Sphinx documentation folders in your project. It builds the documentation using Sphinx and any errors in the build process are bubbled up as GitHub status checks.

It is best run upon pull requests.

The main purposes of this action are:

* Run a CI test to ensure your documentation still builds.
* Allow contributors to get build errors on simple doc changes inline on Github without having to install Sphinx and build locally.

If you have any Python dependencies that your project needs (themes, build tools, etc) then place them in a requirements.txt file inside your docs folder.

For a full description see [ammaraskar/sphinx-action](https://github.com/ammaraskar/sphinx-action)
