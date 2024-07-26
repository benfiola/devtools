import json
import pathlib
from typing import Any, ClassVar

from .command import run_command
from .logs import get_logger

logger = get_logger(__name__)


class Tool:
    """
    Represents a package installed by a parent language

    (e.g., 'black' python pip package, 'prettier' node npm package)
    """

    language: ClassVar[str] = ""
    name: ClassVar[str] = ""
    meta: ClassVar[dict[str, Any]] = {}


class Language:
    """
    Represents a language

    (e.g., python, node).
    """

    name: ClassVar[str]
    path: pathlib.Path
    tools: dict[str, Tool]

    def __init__(self):
        self.tools = {}

    def install(self):
        """
        Installs the language to `self.path`.

        "Installation" is defined as the steps required to prepare `self.path`
        so that tools can be installed into it.

        (e.g., create a python virtual environment)
        """
        raise NotImplementedError()

    def install_tool(self, tool: Tool) -> list[str]:
        """
        Installs the tool.

        Oftentimes, this is simply invoking the language's package manager using
        `self.path`.
        """
        raise NotImplementedError()

    def add_tool(self, tool: Tool):
        """
        Adds a tool to the language
        """
        self.tools[tool.name] = tool

    def __getattr__(self, tool_name: str) -> list[str]:
        """
        Retrieves a tool for the given language - installing it if needed.
        """
        tool = self.tools[tool_name]
        return self.install_tool(tool)


class Node(Language):
    """
    Language implementation of nodejs
    """

    name = "node"

    def install(self):
        """
        Creates a 'private' package at `self.path`.  This enables npm to install
        packages into `{self.path}/node_modules`.
        """
        if not self.path.exists():
            logger.info(f"creating npm package directory")
            self.path.mkdir(parents=True)
        package_json = self.path.joinpath("package.json")
        if not package_json.exists():
            logger.info(f"creating package.json file")
            package_json.write_text(json.dumps({"private": True}))

    def install_tool(self, tool: Tool) -> list[str]:
        """
        Invokes npm to install npm packages within the node_modules folder
        in `self.path`.
        """
        binary = tool.meta["binary"]
        binary = self.path.joinpath(f"node_modules/.bin/{binary}")
        if not binary.exists():
            npm_package = tool.meta["npm_package"]
            npm_extra_packages = tool.meta.get("npm_extra_packages", [])
            logger.info(
                f"installing npm packages: {[npm_package, *npm_extra_packages]}"
            )
            run_command(
                ["npm", "install", npm_package, *npm_extra_packages], cwd=self.path
            )
        if not binary.exists():
            raise RuntimeError(f"tool install failed: {tool}")
        return [f"{binary}"]

    def add_tool(self, tool: Tool):
        """
        Ensures that a tool specifies an 'npm_packages' field
        """
        npm_package = tool.meta.get("npm_package")
        if not npm_package:
            raise ValueError(f"meta.npm_package unset: {tool}")
        binary = tool.meta.get("binary")
        if not binary:
            raise ValueError(f"meta.binary unset: {tool}")
        super().add_tool(tool)


class Python(Language):
    """
    Language implementation for python
    """

    name = "python"

    def install(self):
        """
        Creates a virtual environment at `self.path`
        """
        python_bin = self.path.joinpath("bin/python")
        if not python_bin.exists():
            logger.info(f"creating python virtual environment")
            run_command(["python", "-m", "venv", f"{self.path}"])

    def install_tool(self, tool: Tool):
        """
        Uses pip to install packages within the virtual environment located at `self.path`.
        """
        pip_package = tool.meta["pip_package"]
        pip_extra_packages = tool.meta.get("pip_extra_packages", [])
        python_bin = self.path.joinpath("bin/python")
        found_package = list(self.path.glob(f"lib/*/site-packages/{pip_package}"))
        if not found_package:
            logger.info(
                f"installing pip packages: {[pip_package, *pip_extra_packages]}"
            )
            run_command(
                [
                    f"{python_bin}",
                    "-m",
                    "pip",
                    "install",
                    pip_package,
                    *pip_extra_packages,
                ]
            )
        binary = tool.meta.get("binary")
        if binary:
            binary = self.path.joinpath(f"bin/{binary}")
            return [f"{binary}"]
        return [f"{python_bin}", "-m", pip_package]

    def add_tool(self, tool: Tool):
        """
        Ensures that a tool specifies a 'pip_package' field.
        """
        pip_package = tool.meta.get("pip_package")
        if pip_package is None:
            raise ValueError(f"meta.pip_package unset: {tool}")
        super().add_tool(tool)


class Black(Tool):
    """
    Tool definition for python's black formatter
    """

    language = "python"
    meta = {"pip_package": "black", "binary": "black"}
    name = "black"


class Build(Tool):
    """
    Tool definition for python's build package
    """

    language = "python"
    meta = {"pip_package": "build"}
    name = "build"


class Isort(Tool):
    """
    Tool definition for python's isort import organizer
    """

    language = "python"
    meta = {"pip_package": "isort", "binary": "isort"}
    name = "isort"


class Prettier(Tool):
    """
    Tool definition for nodejs' prettier formatter
    """

    language = "node"
    meta = {"npm_package": "prettier", "binary": "prettier"}
    name = "prettier"


class Vsce(Tool):
    """
    Tool definition for nodejs' 'vsce' binary
    """

    language = "node"
    meta = {"npm_package": "@vscode/vsce", "binary": "vsce"}
    name = "vsce"


class Prefix:
    """
    A prefix is a directory holding various languages and their tools
    """

    languages: dict[str, Language]
    path: pathlib.Path

    def __init__(self, path: pathlib.Path):
        self.languages = {}
        self.path = path

        for language_cls in Language.__subclasses__():
            self.add_language(language_cls)

        for tool_cls in Tool.__subclasses__():
            self.add_tool(tool_cls)

    def bootstrap(self):
        pass

    def add_language(self, language_cls: type[Language]):
        """
        Adds a language implementation to the prefix
        """
        language = language_cls()
        language.path = self.path.joinpath(language.name)
        self.languages[language.name] = language

    def add_tool(self, tool_cls: type[Tool]):
        """
        Adds a tool definition to the prefix
        """
        tool = tool_cls()
        self.languages[tool.language].add_tool(tool)

    def __getattr__(self, language_name: str) -> Language:
        """
        Installs the language and returns it
        """
        if not self.path.exists():
            run_command(["mkdir", "-p", f"{self.path}"])
        language = self.languages[language_name]
        language.install()
        return language
