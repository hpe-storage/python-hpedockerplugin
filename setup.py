from setuptools import setup, find_packages

with open("requirements-py3.txt") as requirements:
        install_requires = requirements.readlines()

setup(name='python-hpedockerplugin',
    version='1.0.0',
    description='HPE Native Docker Volume Plugin',
    url='http://csim-gitlab.rose.rdlabs.hpecorp.net/csim/python-hpedockerplugin',
    author='Garth Booth, Anthony Lee',
    author_email='garth.booth@hpe.com, anthony.mic.lee@hpe.com',
    license='Apache License, Version 2.0',
    packages = find_packages(),
    install_requires=install_requires,
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Environment :: Web Environment',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.0',
        'Topic :: Internet :: WWW/HTTP',

        ]
   )

