import logging
import os
import pathlib
import shlex
import sys
from typing import Literal, cast

import devtools

LogLevel = Literal["debug"] | Literal["info"]
log_level_map: dict[LogLevel, int] = {"debug": logging.DEBUG, "info": logging.INFO}


class Logger(logging.Logger):
    def info(self, msg: str):
        """
        Called when an informational message needs to be logged
        """
        super().info(f"> {msg}")

    def debug(self, msg: str):
        """
        Called when a debug message needs to be logged
        """
        super().debug(f"> {msg}")

    def warning(self, msg: str):
        """
        Called when a warning message needs to be logged
        """
        super().warning(f"> {msg}")

    def command(
        self,
        cmd: list[str],
        env: dict[str, str] | None = None,
        cwd: pathlib.Path | None = None,
    ):
        """
        Called when a command is invoked
        """
        env = env or dict(os.environ)
        cwd = cwd or pathlib.Path.cwd()

        to_print = f"$ {shlex.join(cmd)}"

        env_diff = {}
        for key, value in env.items():
            if os.environ.get(key) == value:
                continue
            env_diff[key] = value
        if env_diff:
            env_str = [f"{k}={v}" for k, v in env_diff.items()]
            env_str = sorted(env_str)
            env_str = ", ".join(env_str)
            env_str = f"(env: {env_str})"
            to_print += f" {env_str}"

        if cwd != pathlib.Path.cwd():
            cwd_str = f"(cwd: {cwd})"
            to_print += f" {cwd_str}"

        super().debug(to_print)

    def command_output(self, data: str):
        """
        Called to log a line of output from an invoked command
        """
        if data.endswith("\n"):
            data = data[:-1]
        super().debug(data)


def get_logger(name: str) -> Logger:
    """
    Implements logging.getLogger - but guarantees that the function returns
    an instance of the custom `Logger` class.
    """
    original = logging.getLoggerClass()
    logging.setLoggerClass(Logger)
    logger = cast(Logger, logging.getLogger(name))
    logging.setLoggerClass(original)
    return logger


def configure_logging(log_level: LogLevel):
    """
    Configures application logging
    """
    logger = get_logger(devtools.__name__)
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level_map[log_level])
