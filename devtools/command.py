import io
import pathlib
import select
import subprocess

from .logs import get_logger

logger = get_logger(__name__)


def run_command(
    cmd: list[str],
    cwd: pathlib.Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """
    Helper method that runs a command.

    """
    kwargs = {
        "cwd": cwd,
        "encoding": "utf-8",
        "env": env,
        "stderr": subprocess.PIPE,
        "stdout": subprocess.PIPE,
    }

    logger.command(cmd, env=kwargs.get("env"), cwd=kwargs.get("cwd"))
    stdout = io.StringIO()
    stderr = io.StringIO()
    popen = subprocess.Popen(cmd, **kwargs)

    while popen.returncode is None:
        popen.poll()
        readables, _, _ = select.select([popen.stdout, popen.stderr], [], [], 0.01)
        for readable in readables:
            buf = stdout
            if readable == popen.stderr:
                buf = stderr
            for line in readable:
                buf.write(line)
                logger.command_output(line)

    stdout.seek(0)
    stderr.seek(0)
    stdout = stdout.read()
    stderr = stderr.read()

    if popen.returncode:
        raise subprocess.CalledProcessError(
            cmd=cmd, output=stdout, returncode=popen.returncode, stderr=stderr
        )


    return stdout