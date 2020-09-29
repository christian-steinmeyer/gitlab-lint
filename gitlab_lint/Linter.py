import re
from glob import glob
from pathlib import Path
from typing import AnyStr
from typing import Tuple
from typing import Union

import click
import requests
import urllib3


class Linter:
    CONTENT_TAG = "content"
    STATUS_TAG = "status"
    ERROR_TAG = "errors"
    VALID_TAG = "valid"
    INVALID_TAG = "invalid"
    WARNING_TAG = "valid with warnings"
    CI_LINT_ENDPOINT = "/api/v4/ci/lint"
    DEFAULT_FILE_NAME = ".gitlab-ci.yml"
    PLACE_HOLDER = "X"

    SKIPPED_ERRORS = []
    SKIPPED_ERRORS_IF_INCLUDED = ["jobs config should contain at least one visible job"]

    def __init__(self, domain: str, token: Union[None, str], path: Tuple[str], verify: bool, find_all: bool,
                 skip_includes: bool):
        self.domain = domain
        self.token = token
        self.path = path
        self.verify = verify
        self.find_all = find_all
        self.skip_includes = skip_includes
        self.data = {}
        self.exit_code = 0
        if not verify:
            # mask error message for not verifying https if verify is False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def validate(self):
        if not self.find_all:
            for filename in self.path:
                self.process(filename)
        else:
            for directory in self.path:
                files_with_leading_dot = glob(f"{directory}/**/.*.yml", recursive=True)
                files_without_leading_dot = glob(f"{directory}/**/*.yml", recursive=True)
                filenames = files_with_leading_dot + files_without_leading_dot
                for filename in sorted(filenames):
                    self.process(filename)

    def process(self, filepath):
        with open(filepath) as file:
            content = file.read()
            content = self.preprocess(content)
            response = self.lint_remotely(content)
            response = self.postprocess(response, filepath)
            self.handle(response, filepath)

    def lint_remotely(self, content: AnyStr):
        """
            Sends the contents of filename to gitlab ci/lint api endpoint
            Reference: https://docs.gitlab.com/ee/api/lint.html
        """
        params = {'private_token': self.token} if self.token else None
        url = f"https://{self.domain}{CI_LINT_ENDPOINT}"
        response = requests.post(url, json={CONTENT_TAG: content}, params=params, verify=self.verify)
        if response.status_code != 200:
            raise click.ClickException(
                f"API endpoint returned invalid response:\n"
                f"{response.text}\n"
                f"confirm your `domain` and `token` have been set correctly")
        return response.json()

    def preprocess(self, content):
        print(content)
        # TODO remove includes
        return content

    def postprocess(self, response: dict, filepath: str) -> dict:
        if response[STATUS_TAG] == VALID_TAG:
            # no post processing necessary
            return response

        status = WARNING_TAG
        for error in response[ERROR_TAG]:
            if not should_be_skipped(filepath, error):
                status = INVALID_TAG
        response[STATUS_TAG] = status
        return response

    def handle(self, response: dict, filepath: str):
        print(response)
        filename = Path(filepath).name
        status = response[STATUS_TAG]
        print(f"{format_as_string(filepath)} is {status}")
        for error in response[ERROR_TAG]:
            log_error(error, filename, status)
        if status not in [VALID_TAG, WARNING_TAG]:
            self.exit_code = 1
        return response


def should_be_skipped(filename: str, error: str) -> bool:
    """
    Some errors while useful for the main .gitlab-ci.yml are irrelevant for e.g. included files.
    :param filename: file in question
    :param error: error message in question
    :return: true if the error in question should be skipped.
    """
    skipped_errors = SKIPPED_ERRORS
    if not filename.endswith(DEFAULT_FILE_NAME):
        skipped_errors += SKIPPED_ERRORS_IF_INCLUDED
    return re.sub(r'`.+`', PLACE_HOLDER, error) in skipped_errors


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
