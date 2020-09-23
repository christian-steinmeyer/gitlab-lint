#!/usr/bin/env python3
# script to validate .gitlab-ci.yml
#
import re
import sys
from glob import glob
from pathlib import Path
from typing import Tuple
from typing import Union

import click
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

CONTENT_TAG = "content"
STATUS_TAG = "status"
ERROR_TAG = "errors"
VALID_TAG = "valid"
INVALID_TAG = "invalid"
WARNING_TAG = "valid with warnings"
CI_LINT_ENDPOINT = "/api/v4/ci/lint"
DEFAULT_FILE_NAME = ".gitlab-ci.yml"
PLACE_HOLDER = "X"

SKIPPED_ERRORS = ["jobs config should contain at least one visible job",
                  f"Local file {PLACE_HOLDER} does not have project!"]


@click.command()
@click.option("--domain", "-d", envvar='GITLAB_LINT_DOMAIN', default="gitlab.com",
              help="Gitlab Domain. You can set envvar GITLAB_LINT_DOMAIN")
@click.option("--token", "-t", envvar='GITLAB_LINT_TOKEN',
              help="Gitlab Personal Token. You can set envvar GITLAB_LINT_TOKEN")
@click.option("--path", "-p", default=[DEFAULT_FILE_NAME],
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
        for directory in path:
            files_with_leading_dot = glob(f"{directory}/**/.*.yml", recursive=True)
            files_without_leading_dot = glob(f"{directory}/**/*.yml", recursive=True)
            filenames = files_with_leading_dot + files_without_leading_dot
            for filename in filenames:
                data[filename] = get_validation_data(filename, domain, token, verify)
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
        url = f"https://{domain}{CI_LINT_ENDPOINT}"
        r = requests.post(url, json={CONTENT_TAG: f.read()}, params=params, verify=verify)
    if r.status_code != 200:
        raise click.ClickException(
            f"API endpoint returned invalid response: \n {r.text} \n confirm your `domain` and `token` have been set "
            f"correctly")
    data = r.json()
    return data


def pre_process(filename: str, response: dict) -> dict:
    """
    Ensures the status of a response with non-errors is only warning,
    not invalid. Non-errors are defined as those only affecting parent
    CI scripts. It is assumed, that the parent has the default name.

    :param filename: name of the file in question
    :param response: gitlab ci lint response for file in question
    :return dict: updated response with updated status
    """
    if response[STATUS_TAG] == VALID_TAG or filename == DEFAULT_FILE_NAME:
        # no pre processing necessary
        return response

    status = WARNING_TAG
    for error in response[ERROR_TAG]:
        if not should_be_skipped(error):
            status = INVALID_TAG
    response[STATUS_TAG] = status
    return response


def generate_exit_info(data: dict):
    """
    Parses response data and generates exit message and code
    :param data: json gitlab API ci/lint response data
    """
    exit_code = 0
    for file_path, response in data.items():
        filename = Path(file_path).name
        response = pre_process(filename, response)
        status = response[STATUS_TAG]
        print(f"{format_as_string(file_path)} is {status}")
        for error in response[ERROR_TAG]:
            log_error(error, filename, status)
        if status not in [VALID_TAG, WARNING_TAG]:
            exit_code = 1
    sys.exit(exit_code)


def should_be_skipped(error: str) -> bool:
    """
    Some errors while useful for the main .gitlab-ci.yml are irrelevant for e.g. included files.
    :param error: error message in question
    :return: true if the error in question should be skipped.
    """

    return re.sub(r'`.+`', PLACE_HOLDER, error) in SKIPPED_ERRORS


def log_error(error: str, filename: str, status: str) -> None:
    """
    Gitlab ci/lint expects all files to be called the same.
    By replacing the default name with the actual file name,
    the output of this tool becomes more readable.

    :param error: original error message
    :param filename: replaces the default name
    :param status: kind of error, defined by tags
    """
    error = error.replace(DEFAULT_FILE_NAME, filename)
    error = format_error(error, status)
    print(f"\t{error}")


def format_as_string(string: str):
    """
    Formats a given string in a different color using ANSI escape sequences
    (see https://stackoverflow.com/a/287944/5299750) and adds double quotes
    :param string: to be printed
    """
    ansi_start = '\033[32m'
    ansi_end = '\033[0m'
    return f"{ansi_start}\"{string}\"{ansi_end}"


def format_error(string: str, status: str):
    """
    Formats a given message in an error color using ANSI escape sequences
    (see https://stackoverflow.com/a/287944/5299750
    and https://stackoverflow.com/a/33206814/5299750)
    :param string: to be printed
    :param status: determines the color of the error
    """
    if status == WARNING_TAG:
        ansi_start = '\033[93m'
    else:
        ansi_start = '\033[91m'
    ansi_end = '\033[0m'
    return f"{ansi_start}{string}{ansi_end}"


if __name__ == '__main__':
    gll()
