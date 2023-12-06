import os
import re

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

def get_version(file_path):
    """
    Extract the version string from the file at the given relative path fragments.
    """
    filename = os.path.join(os.path.dirname(__file__), file_path)
    with open(filename, encoding='utf-8') as opened_file:
        version_file = opened_file.read()
        version_match = re.search(r"""(^__version__\s?=\s?['"](?P<version_number>[^'"]*)['"])""",
                                  version_file, re.M)
    if version_match:
        return version_match.group('version_number')
    raise RuntimeError('Unable to find version string.')


VERSION = get_version("ecommerce_worker/__init__.py")


setup(
    name='edx-ecommerce-worker',
    version=VERSION,
    description='Celery tasks supporting the operations of edX\'s ecommerce service',
    long_description=long_description,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Topic :: Internet',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
    ],
    keywords='edx ecommerce worker',
    url='https://github.com/openedx/ecommerce-worker',
    author='edX',
    author_email='oscm@edx.org',
    license='AGPL',
    packages=find_packages(exclude=['*.tests']),
    install_requires=load_requirements('requirements/base.in'),
)
