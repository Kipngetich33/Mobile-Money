# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in mobile_money/__init__.py
from mobile_money import __version__ as version

setup(
	name='mobile_money',
	version=version,
	description='this is an app that allows mobile money to be intergrated PNext',
	author='Upande LTD',
	author_email='dev@upande.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
