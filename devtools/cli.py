#!/usr/bin/env python3
import pathlib
import sys
from typing import Any

import click
import pydantic

from devtools.format import format
from devtools.logs import LogLevel, configure_logging
from devtools.prefix import Prefix
from devtools.publish import PublishFlavor, publish_github_action
from devtools.update import check_for_update, update_devtools
from devtools.version import VersionFlavor, get_devtools_version, get_next_version


def validator(type: Any):
    """
    Uses pydantic to create a validator for an arbitrary type.

    Intended to be used with the `type` kwarg to click.argument/option.
    """

    def inner(value: str):
        return pydantic.TypeAdapter(type).validate_python(value)

    return inner


def main():
    try:
        grp_main()
    except Exception as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)


pass_prefix = click.make_pass_decorator(Prefix)


@click.group()
@click.option("--log-level", type=validator(LogLevel), default="info")
@click.option("--prefix", type=pathlib.Path, default=pathlib.Path("/tmp/devtools"))
@click.pass_context
def grp_main(ctx: click.Context, log_level: LogLevel, prefix: pathlib.Path):
    ctx.obj = Prefix(prefix)
    configure_logging(log_level)


@grp_main.command("bootstrap", help="bootstraps devtools")
@pass_prefix
def cmd_bootstrap(prefix: Prefix):
    pass


@grp_main.command("format", help="applies formatting rules to files")
@click.option("--check", is_flag=True, help="only check, do not overwrite files")
@click.argument("files", type=pathlib.Path, nargs=-1)
@pass_prefix
def cmd_format(prefix: Prefix, *, check: bool = False, files: tuple[pathlib.Path, ...]):
    format(prefix, check=check, files=list(files))


@grp_main.command("publish-github-action", help="runs a 'publish' github action")
@click.argument("flavor", type=validator(PublishFlavor))
@click.option("--token", required=True)
@pass_prefix
def cmd_publish_github_action(prefix: Prefix, *, flavor: PublishFlavor, token: str):
    publish_github_action(prefix, flavor=flavor, token=token)


@grp_main.command("print-devtools-version", help="prints the current devtools version")
@pass_prefix
def cmd_print_devtools_version(prefix: Prefix):
    version = get_devtools_version(prefix)
    click.echo(version)


@grp_main.command(
    "print-next-version", help="prints the next version of the current project"
)
@click.option("--flavor", type=validator(VersionFlavor), default="semver")
@pass_prefix
def cmd_print_next_version(prefix: Prefix, *, flavor: VersionFlavor):
    version = get_next_version(prefix, flavor=flavor)
    click.echo(version)


@grp_main.command("update-devtools", help="updates devtools to the latest version")
@pass_prefix
def cmd_update_devtools(prefix: Prefix):
    update_devtools(prefix)


if __name__ == "__main__":
    main()
