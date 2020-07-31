from distutils.core import setup

from setuptools import find_packages

setup(
    name="anonymizer",
    version="0.1.0a",
    packages=find_packages(exclude=["tests"]),
    license="MIT",
    description="A Python module that provides multiple anonymization techniques for text.",
    long_description=open("README.md").read(),
    install_requires=["pydantic==1.5.1", "numpy==1.18.5", "python-dateutil==2.8.1"],
)
