from setuptools import setup, find_packages


with open('README.rst') as readme:
    long_description = readme.read()

setup(
    name='edx-ecommerce-worker',
    version='0.2.0',
    description='Celery tasks supporting the operations of edX\'s ecommerce service',
    long_description=long_description,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
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
    install_requires=['celery', 'edx-ecommerce-api-client'],
)
