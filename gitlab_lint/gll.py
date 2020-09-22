#!/usr/bin/env python3
# script to validate .gitlab-ci.yml
#

import sys
from pathlib import Path
from typing import Tuple
from typing import Union

import click
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning


@click.command()
@click.option("--domain", "-d", envvar='GITLAB_LINT_DOMAIN', default="gitlab.com",
              help="Gitlab Domain. You can set envvar GITLAB_LINT_DOMAIN")
@click.option("--token", "-t", envvar='GITLAB_LINT_TOKEN',
              help="Gitlab Personal Token. You can set envvar GITLAB_LINT_TOKEN")
@click.option("--path", "-p", default=[".gitlab-ci.yml"],
              help="Path to .yml or directory (see --find-all), defaults to .gitlab-ci.yml in local directory, "
                   "can be repeated",
              type=click.Path(exists=True, readable=True, file_okay=True), multiple=True)
@click.option("--verify", "-v", default=False, is_flag=True,
              help="Enables HTTPS verification, which is disabled by default to support privately hosted instances")
@click.option("--find-all", "-f", default=False, is_flag=True,
              help="Traverse directory given in --path argument recursively and check all .yml files")
def gll(domain: str, token: Union[None, str], path: Tuple[str], verify: bool, find_all: bool):
    validate_arguments(find_all, path)
    data = {}
    if not find_all:
        for filename in path:
            data[filename] = get_validation_data(filename, domain, token, verify)
    else:
        # traverse
        filename = None
        data[filename] = get_validation_data(path, domain, token, verify)
    generate_exit_info(data)


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


def get_validation_data(path, domain, token, verify):
    """
    Creates a post to gitlab ci/lint  api endpoint
    Reference: https://docs.gitlab.com/ee/api/lint.html
    :param path: str path to .gitlab-ci.yml file
    :param domain: str gitlab endpoint defaults to gitlab.com, this can be overriden for privately hosted instances
    :param token: str gitlab token. If your .gitlab-ci.yml file has includes you may need it to authenticate other repos
    :param verify: bool flag to enable/disable https checking. False by default to support privately hosted instances
    :return: data json response data from api request
    """

    if not verify:
        # mask error message for not verifying https if verify is False
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    params = {'private_token': token} if token else None

    with open(path) as f:
        r = requests.post(f"https://{domain}/api/v4/ci/lint", json={'content': f.read()}, params=params, verify=verify)
    if r.status_code != 200:
        raise click.ClickException(
            f"API endpoint returned invalid response: \n {r.text} \n confirm your `domain` and `token` have been set correctly")
    data = r.json()
    return data


def generate_exit_info(data):
    """
    Parses response data and generates exit message and code
    :param data: json gitlab API ci/lint response data
    """
    if data['status'] != 'valid':
        print("GitLab CI configuration is invalid")
        for e in data['errors']:
            print(e, file=sys.stderr)
        sys.exit(1)
    else:
        print("GitLab CI configuration is valid")
        sys.exit(0)


if __name__ == '__main__':
    gll()
