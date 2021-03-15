#!/usr/bin/env python3
import os

import kolibri_app_desktop_xdg_plugin
from setuptools import find_packages
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), "README.md")) as readme:
    README_MD = readme.read()

setup(
    name="kolibri-app-desktop-xdg-plugin",
    description="Kolibri plugin for Linux desktop app integration",
    long_description=README_MD,
    long_description_content_type="text/markdown",
    version=kolibri_app_desktop_xdg_plugin.__version__,
    author="Dylan McCall",
    author_email="dylan@endlessos.org",
    url="https://github.com/endlessm/kolibri-app-desktop-xdg-plugin",
    packages=find_packages(),
    entry_points={
        "kolibri.plugins": "kolibri_app_desktop_xdg_plugin = kolibri_app_desktop_xdg_plugin",
    },
    package_dir={"kolibri_app_desktop_xdg_plugin": "kolibri_app_desktop_xdg_plugin"},
    include_package_data=True,
    license="MIT",
    keywords="kolibri",
    install_requires=["kolibri>=0.14.6", "Pillow>=8.1.2"],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
