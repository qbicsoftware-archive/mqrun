from setuptools import setup
import os
import sys
import re
import codecs

here = os.path.abspath(os.path.dirname(__file__))

pyversion = sys.version_info
if pyversion.major < 3:
    if pyversion.minor < 7:
        raise ValueError("Requires python2.7 or later")
    requires_pathlib = True
else:
    assert pyversion.major >= 3
    requires_pathlib = pyversion.minor < 4

requirements = []

if requires_pathlib:
    requirements.append('pathlib>=1.0')


def find_version(*file_paths):
    with codecs.open(os.path.join(here, *file_paths), 'r', 'utf-8') as f:
        version_file = f.read()

    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)

    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


with codecs.open('DESCRIPTION.rst', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="mqrun",
    version=find_version('mqrun', '__init__.py'),
    description="Automate MaxQuant",
    long_description=long_description,
    url="https://github.com/aseyboldt/mqrun",
    author="Adrian Seyboldt",
    author_email="adrian.seyboldt@gmail.com",
    license="MIT",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Bioinformatics :: Proteomics',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
    ],
    keywords="MaxQuant proteomics",
    packages=['mqrun'],
    install_requires=requirements,
    package_data={
        "mqrun": ['data/*'],
    },
    entry_points={
        'console_scripts': [
            'mqdaemon=mqrun.mqdaemon:main',
        ],
    },
)
