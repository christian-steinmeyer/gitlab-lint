#!/usr/bin/env python3
# script to validate .gitlab-ci.yml
#
import sys
from pathlib import Path
from typing import Tuple
from typing import Union

import click

from gitlab_lint.Linter import Linter


@click.command()
@click.option("--domain", "-d", envvar='GITLAB_LINT_DOMAIN', default="gitlab.com",
              help="Gitlab Domain. You can set envvar GITLAB_LINT_DOMAIN")
@click.option("--token", "-t", envvar='GITLAB_LINT_TOKEN',
              help="Gitlab Personal Token. You can set envvar GITLAB_LINT_TOKEN")
@click.option("--path", "-p", default=[Linter.DEFAULT_FILE_NAME],
              help="Path to .yml or directory (see --find-all), defaults to .gitlab-ci.yml in local directory, "
                   "can be repeated",
              type=click.Path(exists=True, readable=True, file_okay=True), multiple=True)
@click.option("--verify", "-v", default=False, is_flag=True,
              help="Enables HTTPS verification, which is disabled by default to support privately hosted instances")
@click.option("--find-all", "-f", default=False, is_flag=True,
              help="Traverse directory given in --path argument recursively and check all .yml files")
@click.option("--skip-includes", "-s", default=False, is_flag=True,
              help="Ignore include blocks in order to not 'import' errors from other files")
def gll(domain: str, token: Union[None, str], path: Tuple[str], verify: bool, find_all: bool, skip_includes: bool):
    validate_arguments(find_all, path)
    linter = Linter(domain, token, path, verify, find_all, skip_includes)
    linter.validate()
    sys.exit(linter.exit_code)


def validate_arguments(find_all, path):
    if not find_all:
        for p in path:
            if Path(p).is_dir():
                print(f"You have provided a directory '{p}', but not selected the --find-all option.", file=sys.stderr)
                sys.exit(1)
    if find_all:
        for p in path:
            if Path(p).is_file():
                print(f"You have provided a file '{p}', but selected the --find-all option.", file=sys.stderr)
                sys.exit(1)


if __name__ == '__main__':
    gll()
