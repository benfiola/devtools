import dataclasses
import functools
import re
from typing import Any, Iterator, Literal

import packaging.version

from . import __version__ as devtools_version
from .command import run_command
from .data import data_folder
from .logs import get_logger
from .prefix import Prefix

logger = get_logger(__name__)
devtools_version = data_folder.joinpath("version.txt").read_text().strip()


def get_current_branch() -> str:
    """
    Uses the `git` command line tool to determine the current branch
    """
    branch = run_command(["git", "branch", "--show-current"]).strip()
    return branch


@dataclasses.dataclass
class Commit:
    hash: str
    message: str
    tags: list[str]


def get_commits() -> Iterator[Commit]:
    """
    Returns an iterator of commits starting with HEAD, in reverse order.
    """
    head = run_command(
        [
            "git",
            "rev-list",
            "HEAD",
            "--format=%H",
            "--no-commit-header",
            "--max-count=1",
        ]
    ).strip()
    head = head or None
    commit_hash = head

    skip = 0
    while head is not None and commit_hash is not None:
        skip += 1
        tags = run_command(["git", "tag", "--points-at", commit_hash]).strip().split()
        message = run_command(
            [
                "git",
                "rev-list",
                commit_hash,
                "--format=%B",
                "--no-commit-header",
                "--max-count=1",
            ]
        ).strip()

        commit = Commit(hash=commit_hash, message=message, tags=tags)
        yield commit

        commits = (
            run_command(["git", "rev-list", head, "--max-count=1", f"--skip={skip}"])
            .strip()
            .split()
        )
        commit_hash = commits[0] if commits else None


def get_tags() -> list[str]:
    """
    Uses the `git` command line tool to return a list of tags in the repository
    """
    tags = run_command(["git", "tag"]).strip().splitlines()
    return tags


@dataclasses.dataclass
class VersionRule:
    branch: str
    prerelease_token: str | None = None
    add_build_metadata: bool = False


version_rules = [
    VersionRule(branch="main"),
    VersionRule(branch="dev", prerelease_token="rc"),
    VersionRule(branch=".*", prerelease_token="alpha", add_build_metadata=True),
]


def determine_version_rule(branch: str) -> VersionRule | None:
    """
    Attempts to match a branch with a set of version rules.

    Returns 'None' if a match is not found, otherwise returns the matching rule.
    """
    for rule in version_rules:
        rule_regex = re.compile(rule.branch)
        if not rule_regex.match(branch):
            continue
        return rule
    return None


VersionChangeValue = (
    Literal["none"] | Literal["patch"] | Literal["minor"] | Literal["major"]
)
version_change_values = {"major": 3, "minor": 2, "patch": 1, "none": 0}


@functools.total_ordering
class VersionChange:
    def __init__(self, value: VersionChangeValue):
        self.value = value

    def __int__(self) -> int:
        """
        Used to allow comparisons between scales of version changes.

        (e.g., 'is a "major" change greater than a "patch" change?)
        """
        if self.value == "major":
            return 3
        elif self.value == "minor":
            return 2
        elif self.value == "patch":
            return 1
        elif self.value == "none":
            return 0
        raise NotImplementedError()

    def __str__(self) -> str:
        """
        Returns the 'label' of the version change
        """
        return self.value

    def __lt__(self, other: Any) -> bool:
        """
        Used in conjunction with `functools.total_ordering` to implement
        all other comparison operations.
        """
        if not isinstance(other, VersionChange):
            raise ValueError(other)
        return int(self) < int(other)


VersionFlavor = Literal["semver"] | Literal["docker"] | Literal["node"] | Literal["git"]


@functools.total_ordering
class Maximum:
    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Maximum):
            return False
        return True


version_re = re.compile(
    r"^(?P<major>[\d]+)"
    r"\.(?P<minor>[\d]+)"
    r"\.(?P<patch>[\d]+)"
    r"(?:-(?P<pre_tag>.*)\.(?P<pre_count>[\d]+))?"
    r"(?:\+(?P<metadata>.*))?$"
)


@functools.total_ordering
class Version:
    major: int
    minor: int
    patch: int
    pre: tuple[str, int] | None
    metadata: str | None

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        pre: tuple[str, int] | None = None,
        metadata: str | None = None,
    ):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre = pre
        self.metadata = metadata

    def as_string(self, flavor: "VersionFlavor" = "semver") -> str:
        if flavor == "semver":
            semver = f"{self.major}.{self.minor}.{self.patch}"
            if self.pre:
                tag, count = self.pre
                semver = f"{semver}-{tag}.{count}"
            if self.metadata:
                semver = f"{semver}+{self.metadata}"
            return semver
        elif flavor == "git":
            semver = self.as_string(flavor="semver")
            return f"v{semver}"
        elif flavor == "docker":
            semver = self.as_string(flavor="semver")
            return semver.replace("+", "-")
        elif flavor == "node":
            node = f"{self.major}.{self.minor}.{self.patch}"
            tag, count = None, None
            if self.pre:
                tag, count = self.pre
            if tag:
                node = f"{node}-{tag}"
            if self.metadata:
                node = f"{node}.{self.metadata}"
            if count:
                node = f"{node}.{count}"
            return node
        else:
            raise NotImplementedError(flavor)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            raise ValueError(other)
        self_pre = self.pre or (Maximum(), Maximum())
        other_pre = other.pre or (Maximum(), Maximum())
        self_data = (self.major, self.minor, self.patch, *self_pre)
        other_data = (other.major, other.minor, other.patch, *other_pre)
        return self_data < other_data

    def __str__(self) -> str:
        """
        Converts a version object into a version string compatible with semver.
        (e.g., {major}.{minor}.{patch}(-{pre})?)
        """
        return self.as_string()

    @classmethod
    def from_string(cls, value: str) -> "Version":
        match = version_re.match(value)
        if match is None:
            raise ValueError(value)
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        pre_tag = match.group("pre_tag")
        pre_count = match.group("pre_count")
        if pre_tag and pre_count:
            pre = (pre_tag, int(pre_count))
        metadata = match.group("metadata")
        return cls(major=major, minor=minor, patch=patch, pre=pre, metadata=metadata)


def get_version_change_from_diff(a: Version, b: Version) -> VersionChange:
    """
    Determines the largest difference between two versions.
    (e.g., if a's major version differs from b's major version, returns "major")
    """
    if a.major != b.major:
        return VersionChange("major")
    if a.minor != b.minor:
        return VersionChange("minor")
    if a.patch != b.patch:
        return VersionChange("patch")
    return VersionChange("none")


version_tags: dict[str, VersionChangeValue] = {
    "build:": "patch",
    "chore:": "patch",
    "ci:": "patch",
    "docs:": "patch",
    "feat:": "minor",
    "fix:": "patch",
    "perf:": "patch",
    "style:": "patch",
    "refactor:": "minor",
    "test:": "patch",
}


def get_version_change_from_message(message: str) -> VersionChange:
    """
    Parses a commit message and determines the type of version change that should be performed.

    Returns "none" if the commit does not conform to an expected format.
    """
    lines = message.strip().splitlines()

    if not lines:
        return VersionChange("none")

    header = lines[0]
    change = None
    for tag, current_change in version_tags.items():
        if not header.startswith(tag):
            continue
        change = VersionChange(current_change)
        break
    if not change:
        return VersionChange("none")

    for line in lines[1:]:
        if not line.startswith("BREAKING CHANGE:"):
            continue
        change = VersionChange("major")
        break

    return change


def parse_versions(tags: list[str]) -> list[Version]:
    """
    Returns a list of `Version` objects parsed from a list of tags.

    Assumes that version tags are prefixed with 'v'. (e.g., v0.0.0)
    Unparseable tags are ignored.
    """
    to_return = []
    for tag in tags:
        if not tag.startswith("v"):
            continue
        try:
            version = Version.from_string(tag[1:])
        except packaging.version.InvalidVersion:
            continue
        to_return.append(version)
    return to_return


def get_repo_data() -> Version:
    """
    Iterates over all tags in a repo and returns the latest version.

    If a version is not found, defaults to '0.0.0.'.
    """
    all_sorted_versions = sorted(parse_versions(get_tags()), reverse=True)
    latest_version = (
        all_sorted_versions[0] if all_sorted_versions else Version.from_string("0.0.0")
    )
    return latest_version


def get_ancestral_data() -> tuple[Version, VersionChange]:
    """
    Iterates over the commit history of the current HEAD.  Returns a tuple of [<latest ancestral release>, <largest change>].
    """
    change = VersionChange("none")
    for commit in get_commits():
        sorted_versions = sorted(parse_versions(commit.tags))
        for version in sorted_versions:
            if version.pre:
                continue
            return version, change
        current_change = get_version_change_from_message(commit.message)
        if current_change > change:
            change = current_change
    return Version.from_string("0.0.0"), change


def bump_version(version: Version, version_change: VersionChange) -> Version:
    """
    Bumps `version` by the given `version change`.

    NOTE: Will always strip prerelease information.
    """
    new_version = Version.clone()
    if f"{version_change}" == "major":
        major += 1
        minor = 0
        patch = 0
    elif f"{version_change}" == "minor":
        minor += 1
        patch = 0
    elif f"{version_change}" == "patch":
        patch += 1
    else:
        raise NotImplemented(version_change)
    return Version(f"{major}.{minor}.{patch}")


def bump_prerelease(version: Version, prerelease: str):
    """
    Bumps `version` prerelease field by one *if* prerelease tag matches `prerelease`.
    Otherwise, sets `version` prerelease field to <prerelease>.1
    """
    major, minor, patch = version.release
    pre_name, pre_count = version.pre or (prerelease, 0)
    if pre_name != prerelease:
        pre_name = prerelease
        pre_count = 0
    pre_count += 1
    return Version(f"{major}.{minor}.{patch}-{pre_name}.{pre_count}")


def get_devtools_version(prefix: Prefix) -> str:
    """
    Gets the current devtools version string
    """
    return Version(devtools_version).as_string()


def get_next_version(_: Prefix, flavor: VersionFlavor = "semver") -> str:
    """
    Determines the next version of a repository by using branch rules in conjunction with
    tagged commit messages to perform version bumps.
    """
    logger.info("getting branch")
    branch = get_current_branch()
    logger.info(f"branch: {branch}")

    logger.info("determining rule for branch")
    rule = determine_version_rule(branch)
    if not rule:
        # unable to bump version without matching rules - exit
        raise ValueError(f"no rules match: {branch}")
    logger.info(f"rule: {rule.branch}")

    logger.info(f"getting repo data")
    repo_version = get_repo_data()
    logger.info(f"repo version: {repo_version}")

    logger.info(f"getting ancestral data")
    ancestor_release, change = get_ancestral_data()
    logger.info(f"ancestor release: {ancestor_release}")
    logger.info(f"change: {change}")
    if change == "none":
        # version remains the same if no changes
        return f"{ancestor_release}"

    # drift is the size of the changes between commit history and the overall repo version
    # (e.g., repo_version=1.3.0, ancestor_release=1.0.0, drift="major" because the major version differs)
    drift = get_version_change_from_diff(repo_version, ancestor_release)
    if rule.prerelease_token is not None:
        if drift < change:
            version = bump_version(repo_version, change)
        else:
            version = repo_version
        version = bump_prerelease(version, rule.prerelease_token)
    else:
        if not repo_version.is_prerelease:
            version = bump_version(repo_version, change)
        else:
            if drift < change:
                version = bump_version(repo_version, change)
            else:
                version = Version(repo_version.base_version)
    if rule.add_build_metadata:
        build_metadata = branch.replace("[^a-zA-Z0-9]+", ".")
        version = Version(f"{version}+{build_metadata}")
    logger.info(f"version: {version}")

    return version.as_string(flavor=flavor)
