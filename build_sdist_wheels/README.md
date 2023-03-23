# Build a source distribution and wheel

This action builds a Python package source and wheel distribution. The built distributions
are uploaded as artefacts in the ``dist`` directory.

This action is designed to build pure Python wheels, that can be used across multiple
operating systems and architectures. If your package needs building individually
on different operating systems, the [build_wheels](../build_wheels) action should be
used instead.

