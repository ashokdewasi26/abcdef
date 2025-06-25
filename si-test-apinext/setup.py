#!/usr/bin/env python3
import os
import subprocess

from setuptools import find_packages, setup
import si_test_apinext

CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "License :: BMW Proprietary",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Topic :: Software Development :: Testing",
]


try:
    version_git = (
        os.getenv("GITPKGVTAG", None)
        or subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().rstrip()
    )
except (subprocess.CalledProcessError, OSError):
    version_git = "unknown"
pkg_version = "{}+{}".format(si_test_apinext.__version__, version_git)

# Requirements that are strictly needed for all executions
requirements = open("requirements.txt").read().splitlines()

# Requirements that are exclusive for a feature. Only installed if needed
requirements_traas = open("requirements-traas.txt").read().splitlines()

setup(
    name="si_test_apinext",
    version=pkg_version,
    description="Tests and helpers for IDC Android and RSE System Integration tests",
    author="BMW CTW",
    license="BMW proprietary",
    keywords="testing test automation MTEE framework apinext",
    platforms="any",
    classifiers=CLASSIFIERS,
    packages=find_packages(),
    scripts=[],
    install_requires=[requirements],
    extras_require={"traas": requirements_traas},
    include_package_data=True,
    package_data={
        # If any package contains *.png or *.wav files, include them:
        "": ["*.png", "*.wav"]
    },
)
