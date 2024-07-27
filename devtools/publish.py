import json
import os
import pathlib
from typing import Literal

import packaging.utils
import packaging.version
import toml

from .command import run_command
from .logs import get_logger
from .prefix import Prefix

logger = get_logger(__name__)
PublishFlavor = (
    Literal["docker"]
    | Literal["package"]
    | Literal["executable"]
    | Literal["vscode-extension"]
)

ProjectType = Literal["python"] | Literal["node"]


def determine_project_type() -> ProjectType:
    if pathlib.Path.cwd().joinpath("pyproject.toml"):
        return "python"
    elif pathlib.Path.cwd().joinpath("package.json"):
        return "node"
    raise NotImplementedError()


def get_project_name(project_type: ProjectType):
    if project_type == "python":
        pyproject_file = pathlib.Path.cwd().joinpath("pyproject.toml")
        data = toml.loads(pyproject_file.read_text())
        name = data["project"]["name"]
        return name
    elif project_type == "node":
        package_json_file = pathlib.Path.cwd().joinpath("package.json")
        data = json.loads(package_json_file.read_text())
        name = data["name"]
        return name
    raise NotImplementedError()


def set_project_version(project_type: ProjectType, version: str):
    if project_type == "python":
        pyproject_file = pathlib.Path.cwd().joinpath("pyproject.toml")
        data = toml.loads(pyproject_file.read_text())
        data["project"]["version"] = version
        pyproject_file.write_text(toml.dumps(data))
    elif project_type == "node":
        package_json_file = pathlib.Path.cwd().joinpath("package.json")
        data = json.loads(package_json_file.read_text())
        data["version"] = version
        package_json_file.write_text(json.dumps(data, indent=2))
    raise NotImplementedError()


def publish_github_action(prefix: Prefix, *, flavor: PublishFlavor, token: str):
    project_type = determine_project_type()
    version = run_command(["devtools", "print-next-version", "--flavor=git"]).strip()
    version = run_command(["devtools", "print-next-version", "--flavor=semver"]).strip()

    pyproject_file = pathlib.Path.cwd().joinpath("pyproject.toml")
    if not pyproject_file.exists():
        raise RuntimeError(f"pyproject.toml not found")
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if not github_output_path:
        raise RuntimeError(f"github output env unset")

    with open(github_output_path, "a") as github_output:
        project_data = toml.loads(pyproject_file.read_text())
        name = project_data["project"]["name"]

        logger.info("writing version")
        version = run_command(["devtools", "print-next-version", "--as-tag"]).strip()
        logger.info(f"version: {version}")
        project_data["project"]["version"] = version
        pyproject_file.write_text(toml.dumps(project_data))
        github_output.writelines([f"version={version}"])

        logger.info("writing tag")
        tag = run_command(["devtools", "print-next-version", "--as-tag"]).strip()
        logger.info(f"tag: {tag}")
        github_output.writelines([f"tag={tag}"])

        logger.info(f"check formatting")
        run_command(["devtools", "format", "--check", "."])

        if flavor == "python":
            logger.info("build python package")
            run_command(["python", "-m", "build"])
            logger.info("publish python package")
            pkg_name = packaging.utils.canonicalize_name(name).replace("-", "_")
            pkg_version = packaging.utils.canonicalize_version(
                version, strip_trailing_zero=False
            )
            logger.info(f"package name: {pkg_name}")
            logger.info(f"package version: {pkg_version}")
            globs = [
                f"dist/{pkg_name}-{pkg_version}-*.whl",
                f"dist/{pkg_name}-{pkg_version}.tar.gz",
            ]
            files = []
            for glob in globs:
                files.extend(pathlib.Path.cwd().glob(glob))
            if not files:
                raise RuntimeError(f"unable to find wheel/sdist files: {globs}")
            run_command(
                [
                    "twine",
                    "--no-color",
                    "upload",
                    "--disable-progress-bar",
                    "--username=__token__",
                    f"--password={token}",
                    *list(map(str, files)),
                ]
            )
        elif flavor == "docker":
            logger.info("log into docker")
            run_command(
                ["docker", "login", "--username=benfiola", f"--password={token}"]
            )
            logger.info("build and publish docker image")
            base_image = f"docker.io/benfiola/{name}"
            publish_latest = not packaging.version.Version(version).is_prerelease
            image_version = version.replace("+", "-")
            logger.info(f"image: {base_image}:{image_version}")
            logger.info(f"publish latest: {publish_latest}")
            cmd = [
                "docker",
                "buildx",
                "build",
                "--platform=linux/arm64,linux/amd64",
                "--progress=plain",
                "--push",
                f"--tag={base_image}:{image_version}",
            ]
            if publish_latest:
                cmd.extend([f"--tag={base_image}:latest"])
            cmd.extend(["."])
            run_command(cmd)
