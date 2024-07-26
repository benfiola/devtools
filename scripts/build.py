#!/usr/bin/env python
import subprocess


def main():
    subprocess.run(
        [
            "python",
            # these python flags are passed through to the binary nuitka creates
            "-u",
            "-X",
            "utf8",
            "-m",
            "nuitka",
            # embed non-python files in binary
            "--include-package-data=devtools",
            "--onefile",
            # disable compression to improve startup performance
            "--onefile-no-compression",
            "--output-dir=build",
            "--output-filename=devtools",
            "--standalone",
            # python must be statically linked (otherwise, a standalone binary makes less sense)
            "--static-libpython=yes",
            "devtools/cli.py",
        ]
    )


if __name__ == "__main__":
    main()
