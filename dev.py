import pathlib

from devtools.logs import configure_logging
from devtools.prefix import Prefix
from devtools.version import Version, get_next_version


def main():
    prefix = Prefix(pathlib.Path("/tmp/devtools"))
    release = Version.from_string(f"1.0.0")
    dev = Version.from_string(f"1.0.0-rc.1")
    alpha = Version.from_string(f"1.0.0-alpha.1+testing")
    get_next_version(prefix)


if __name__ == "__main__":
    configure_logging("debug")
    main()
