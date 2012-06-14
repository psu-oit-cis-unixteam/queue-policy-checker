#!/usr/bin/python

import os
from setuptools import setup, find_packages
import queuecheck

def get_desc():
    """Read the long description from the README.md"""
    pwd = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(pwd, 'README.md')) as readme:
        return readme.read()

setup(name='queue-policy-check',
    version=queuecheck.__version__,
    description=queuecheck.__doc__,
    install_requires=[
        'argparse>=1.1',
        'PyYAML>=3.10',
        'requests>=0.11.1',
        'termcolor>=1.1.0',
    ],
    author='Max R.D. Parmer',
    author_email='maxp@pdx.edu',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'check-queue = queuecheck.Main:QueueCheck',
        ]
    },
    long_description=get_desc(),
)
