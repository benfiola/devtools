import pathlib

from devtools.format import format
from devtools.logs import configure_logging
from devtools.prefix import Prefix
from devtools.version import get_version


def main():
    prefix = Prefix(pathlib.Path("/tmp/devtools"))
    get_version(prefix)


if __name__ == "__main__":
    configure_logging("debug")
    main()
