import pathlib
from typing import ClassVar

import yaml

from .command import run_command
from .data import data_folder
from .logs import get_logger
from .prefix import Prefix

logger = get_logger(__name__)
all_languages = yaml.load(
    data_folder.joinpath("languages.yaml").read_text(), Loader=yaml.CSafeLoader
)


class Formatter:
    """
    Defines a formatter implementation.

    Accepts class members defining supported languages and additional fragments (i.e., filenames and suffixes).
    On instantiation, will flatten languages and additional fragments into a set of fragments that the formatter supports.
    """

    fragments: set[str]
    name: ClassVar[str]
    languages: ClassVar[list[str]] = []
    additional_fragments: ClassVar[list[str]] = []

    def __init__(self):
        self.fragments = set()
        for language in self.languages:
            language_extensions = all_languages.get(language, {}).get("extensions", [])
            self.fragments.update(language_extensions)
        self.fragments.update(self.additional_fragments)

    def format(self, prefix: Prefix, *, files: list[pathlib.Path], check: bool = False):
        raise NotImplementedError()


class Python(Formatter):
    """
    Defines a python formatter.  Uses isort and black to perform formatting.
    """

    name = "python"
    languages = ["Python"]

    def format(self, prefix: Prefix, *, files: list[pathlib.Path], check: bool = False):
        isort_config = data_folder.joinpath("isort.toml")
        isort_cmd = [*prefix.python.isort, f"--settings={isort_config}"]
        if check:
            isort_cmd.extend(["--check"])
        isort_cmd.extend(map(str, files))
        run_command(isort_cmd)
        black_config = data_folder.joinpath("black.toml")
        black_cmd = [*prefix.python.black, f"--config={black_config}"]
        if check:
            black_cmd.extend(["--check"])
        black_cmd.extend(map(str, files))
        run_command(black_cmd)


class Prettier(Formatter):
    """
    Defines a prettier formatter.  Uses prettier to perform formatting.
    """

    name = "prettier"
    languages = [
        "CSS",
        "PostCSS",
        "Less",
        "SCSS",
        "GraphQL",
        "Handlebars",
        "HTML",
        "Vue",
        "Javascript",
        "Typescript",
        "TSX",
        "JSON",
        "JSON with Comments",
        "JSON5",
        "Markdown",
        "YAML",
    ]
    additional_fragments = [
        ".babelrc",
        ".jscsrc",
        ".jshintrc",
        ".jslintrc",
        "swcrc",
        ".prettierrc",
    ]

    def format(self, prefix: Prefix, *, files: list[pathlib.Path], check: bool = False):
        prettier_config = data_folder.joinpath("prettier.json")
        prettier_cmd = [
            *prefix.node.prettier,
            f"--config={prettier_config}",
            "--write",
        ]
        if check:
            prettier_cmd.extend(["--check"])
        prettier_cmd.extend(map(str, files))
        run_command(prettier_cmd)


# create formatters
formatters = [formatter_cls() for formatter_cls in Formatter.__subclasses__()]

# create a fragment (i.e., filenames and suffixes) -> formatter mapping
fragment_formatters: dict[str, Formatter] = {}
for formatter in formatters:
    for fragment in formatter.fragments:
        fragment_formatters[fragment] = formatter


def format(prefix: Prefix, *, check: bool = False, files: list[pathlib.Path]):
    """
    Formats `files` in-place using different formatters depending on the file extension.
    If 'check' is True, will raise an error if files require formatting.
    """
    batches: dict[Formatter, list[pathlib.Path]] = {}
    for formatter in formatters:
        batches.setdefault(formatter, [])

    for file in files:
        if file.is_dir():
            logger.debug(f"add directory to all formatters: {file}")
            # directories should get passed to all formatters
            for formatter_files in batches.values():
                formatter_files.append(file)
        elif file.is_file():
            formatter = None
            suffixes = [file.stem, *file.suffixes]
            suffix = ""
            # attempt to find formatter for file by incrementally adding suffixes up until the whole filename is checked
            while suffixes and not formatter:
                fragment = f"{suffixes.pop()}{suffix}"
                formatter = fragment_formatters.get(fragment)
            if not formatter:
                # skip file if formatter not found
                continue
            logger.debug(f"add file to formatter {formatter.name}: {file}")
            batches[formatter].append(file)
        else:
            logger.warning(f"file does not exist: {file}")

    for formatter, files in batches.items():
        if not files:
            continue
        logger.info(f"formatting {len(files)} file(s) with {formatter.name} formatter")
        formatter.format(prefix, files=files, check=check)
