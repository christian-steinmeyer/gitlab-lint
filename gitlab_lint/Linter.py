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
        url = f"https://{self.domain}{self.CI_LINT_ENDPOINT}"
        response = requests.post(url, json={self.CONTENT_TAG: content}, params=params, verify=self.verify)
        if response.status_code != 200:
            raise click.ClickException(
                f"API endpoint returned invalid response:\n"
                f"{response.text}\n"
                f"confirm your `domain` and `token` have been set correctly")
        return response.json()

    def preprocess(self, content: str) -> str:
        content = self.remove_includes(content)
        return content

    def postprocess(self, response: dict, filepath: str) -> dict:
        if response[self.STATUS_TAG] == self.VALID_TAG:
            # no post processing necessary
            return response

        status = self.WARNING_TAG
        for error in response[self.ERROR_TAG]:
            if not self.should_be_skipped(filepath, error):
                status = self.INVALID_TAG
        response[self.STATUS_TAG] = status
        return response

    def handle(self, response: dict, filepath: str):
        filename = Path(filepath).name
        status = response[self.STATUS_TAG]
        print(f"{format_as_string(filepath)} is {status}")
        for error in response[self.ERROR_TAG]:
            self.log_error(error, filename, status)
        if status not in [self.VALID_TAG, self.WARNING_TAG]:
            self.exit_code = 1
        return response

    def remove_includes(self, content: str) -> str:
        if self.skip_includes:
            lines = content.split("\n")
            processed_lines = lines.copy()
            include_block = False
            for line in lines:
                if "include:" in line:
                    processed_lines.remove(line)
                    include_block = True
                elif include_block and re.match(r'\s*-.*', line):
                    processed_lines.remove(line)
                else:
                    include_block = False
            content = "\n".join(processed_lines)
        return content

    def should_be_skipped(self, filename: str, error: str) -> bool:
        """
        Some errors while useful for the main .gitlab-ci.yml are irrelevant for e.g. included files.
        :param filename: file in question
        :param error: error message in question
        :return: true if the error in question should be skipped.
        """
        skipped_errors = self.SKIPPED_ERRORS
        if not filename.endswith(self.DEFAULT_FILE_NAME):
            skipped_errors += self.SKIPPED_ERRORS_IF_INCLUDED
        return re.sub(r'`.+`', self.PLACE_HOLDER, error) in skipped_errors

    def log_error(self, error: str, filename: str, status: str) -> None:
        """
        Gitlab ci/lint expects all files to be called the same.
        By replacing the default name with the actual file name,
        the output of this tool becomes more readable.

        :param error: original error message
        :param filename: replaces the default name
        :param status: kind of error, defined by tags
        """
        error = error.replace(self.DEFAULT_FILE_NAME, filename)
        error = format_error(error, status == self.WARNING_TAG)
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


def format_error(string: str, is_warning: bool) -> str:
    """
    Formats a given message in an error color using ANSI escape sequences
    (see https://stackoverflow.com/a/287944/5299750
    and https://stackoverflow.com/a/33206814/5299750)
    :param string: to be printed
    :param is_warning: determines the color of the error
    """
    if is_warning:
        ansi_start = '\033[93m'
    else:
        ansi_start = '\033[91m'
    ansi_end = '\033[0m'
    return f"{ansi_start}{string}{ansi_end}"
