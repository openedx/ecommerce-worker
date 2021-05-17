from __future__ import absolute_import
from setuptools import setup, find_packages


with open('README.rst') as readme:
    long_description = readme.read()


def load_requirements(*requirements_paths):
    """
    Load all requirements from the specified requirements files.
    Returns a list of requirement strings.
    """
    requirements = set()
    for path in requirements_paths:
        requirements.update(
            line.split('#')[0].strip() for line in open(path).readlines()
            if is_requirement(line.strip())
        )
    return list(requirements)


def is_requirement(line):
    """
    Return True if the requirement line is a package requirement;
    that is, it is not blank, a comment, a URL, or an included file.
    """
    return not (
        line == '' or
        line.startswith('-c') or
        line.startswith('-r') or
        line.startswith('#') or
        line.startswith('-e') or
        line.startswith('git+')
    )


setup(
    name='edx-ecommerce-worker',
    version='2.0.1',
    description='Celery tasks supporting the operations of edX\'s ecommerce service',
    long_description=long_description,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
    ],
    keywords='edx ecommerce worker',
    url='https://github.com/edx/ecommerce-worker',
    author='edX',
    author_email='oscm@edx.org',
    license='AGPL',
    packages=find_packages(exclude=['*.tests']),
    install_requires=load_requirements('requirements/base.in'),
)
