from setuptools import find_packages
from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='gitlab-lint',
    version='0.2.2',
    py_modules=['gitlab-lint'],
    author="Christian Steinmeyer",
    author_email="christian.steinmeyer@item.fraunhofer.de",
    description="This is a CLI application to quickly lint .gitlab-ci.yml files using the gitlab api. It's a fork "
                "from https://github.com/mick352/gitlab-lint (https://github.com/elijah-roberts/gitlab-lint)",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    download_url="https://github.com/christian-steinmeyer/gitlab-lint/archive/0.2.2.tar.gz",
    keywords=['GITLAB', 'LINT', 'GIT'],
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'Click',
        'Requests'
    ],
    entry_points='''
        [console_scripts]
        gll=gitlab_lint.gll:gll
    ''',
)
