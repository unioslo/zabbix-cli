"""Experimental self-update module. Powers the `update` command.


This code is largely untested and is reliant on too many external factors
to be reliably testable. It was primarily written to be used for installations
of Zabbix-CLI that are distributed as PyInstaller binaries. However, it
ended up growing in scope to encompass all the supported installation methods.

The primary use case we focus on is updating PyInstaller binaries. The other
installation methods are supported, but rely on some less-than-ideal heuristics
for detection."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
import tempfile
from abc import ABC
from abc import abstractmethod
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Set
from typing import Type

import httpx
from pydantic import BaseModel
from rich.progress import Progress
from strenum import StrEnum
from typing_extensions import Self

from zabbix_cli.__about__ import __version__
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import exit_ok

logger = logging.getLogger(__name__)

ZCLI_PACKAGES = ["zabbix-cli", "zabbix-cli-uio"]


class UpdateError(ZabbixCLIError):  # move to zabbix_cli.exceptions?
    """Base class for update errors."""


class Updater(ABC):
    def __init__(self, installation_info: InstallationInfo) -> None:
        self.installation_info = installation_info

    @abstractmethod
    def update(self) -> Optional[UpdateInfo]:
        """Update the application to the latest version.

        May return information about the update, such as the new version."""
        raise NotImplementedError


class GitUpdater(Updater):
    def update(self) -> UpdateInfo:
        # TODO: let user pass git remote, branch and other args
        subprocess.run(["git", "pull"], cwd=self.installation_info.bindir)
        # subprocess.run(["git", "-C", str(repoself.installation_info.bindir_path.absolute()), "pull"])
        return UpdateInfo(self.installation_info.method, "latest")


class PypiUpdater(Updater):
    """ABC Updater for packages installed via PyPI."""

    @property
    @abstractmethod
    def package_manager(self) -> str:
        """The name of package manager used to install the package."""
        raise NotImplementedError

    @property
    @abstractmethod
    def uninstall_command(self) -> List[str]:
        """The command used to uninstall the package."""
        raise NotImplementedError

    @property
    @abstractmethod
    def upgrade_command(self) -> List[str]:
        """The command used to upgrade the package."""
        raise NotImplementedError

    @abstractmethod
    def get_packages(self) -> Set[str]:
        """Get a list of installed packages."""
        raise NotImplementedError

    def detect_package_name(self) -> str:
        """Get the name of the package to update.

        As of v3.1.3, `zabbix-cli` is released under the alias `zabbix-cli-uio` on PyPI.
        In the future, we might obtain the name `zabbix-cli` on PyPI, and
        we need to support updating both the aliased name (`zabbix-cli-uio`)
        and the actual name (`zabbix-cli`). This method detects the name of the
        package to update based on what is installed.
        """
        packages = self.get_packages()

        # BOTH zabbix-cli and zabbix-cli-uio are installed
        if "zabbix-cli-uio" in packages and "zabbix-cli" in packages:
            # BOTH zabbix-cli and zabbix-cli-uio are installed
            if self.installation_info.executable:
                if self.installation_info.executable.name in [
                    "zabbix-cli",
                    "zabbix-cli-uio",
                ]:
                    return self.installation_info.executable.name
                else:
                    raise UpdateError(
                        f"Unknown executable: {self.installation_info.executable}"
                    )
            raise UpdateError(
                "Found both [code]zabbix-cli[/] and [code]zabbix-cli-uio[/]. "
                "Unable to determine which package to update. "
                "Uninstall zabbix-cli or zabbix-cli-uio with "
                f"[code]{' '.join(self.uninstall_command)} <package>[/code] and try again."
            )
        elif "zabbix-cli-uio" in packages:
            return "zabbix-cli-uio"
        elif "zabbix-cli" in packages:
            return "zabbix-cli"
        raise UpdateError(f"Unable to detect package name from {self.package_manager}.")

    def update(self) -> None:
        package = self.detect_package_name()
        cmd = self.upgrade_command + [package]
        subprocess.run(cmd)


class PipxListOutput(BaseModel):
    # pipx_spec_version: str # ignore this for now
    venvs: Dict[str, Any]  # we just care about the keys

    @classmethod
    def from_json(cls, j: str) -> Self:
        return cls.model_validate_json(j)

    def package_names(self) -> Set[str]:
        """Get installed package names."""
        return set(self.venvs.keys())


class PipxUpdater(PypiUpdater):
    @property
    def package_manager(self) -> str:
        """The name of package manager used to install the package."""
        return "pipx"

    @property
    def uninstall_command(self) -> List[str]:
        """The command used to uninstall the package."""
        return ["pipx", "uninstall"]

    @property
    @abstractmethod
    def upgrade_command(self) -> List[str]:
        """The command used to upgrade the package."""
        return ["pipx", "upgrade"]

    def get_packages(self) -> Set[str]:
        out = subprocess.check_output(["pipx", "list", "--json"], text=True)

        try:
            return PipxListOutput.from_json(out).package_names()
        except Exception as e:
            raise UpdateError(f"Unable to parse pipx list output: {e}") from e


class PipUpdater(PypiUpdater):
    """Updater for bare pip installations (PLEASE DONT USE THIS!!!!)"""

    @property
    def package_manager(self) -> str:
        """The name of package manager used to install the package."""
        return "pip"

    @property
    def uninstall_command(self) -> List[str]:
        """The command used to uninstall the package."""
        return ["pip", "uninstall"]

    @property
    @abstractmethod
    def upgrade_command(self) -> List[str]:
        """The command used to upgrade the package."""
        return ["pip", "install", "--upgrade"]

    def get_packages(self) -> Set[str]:
        pkgs: Set[str] = set()

        out = subprocess.check_output(["pip", "freeze"], text=True)
        lines = out.splitlines()
        for line in lines:
            if " @ " in line:
                pkg, _, _ = line.partition(" @ ")
            else:
                pkg, _, _ = line.partition("==")
            pkgs.add(pkg)
        return pkgs

    def detect_package_name(self) -> str:
        # Special case for pip, since if we are at the point where
        # we have both zabbix-cli and zabbix-cli-uio installed, we
        # might have already migrated to a mirror package on PyPI
        # where `zabbix-cli-uio` has a single dependency on `zabbix-cli`
        # in which case, we can just assume we can update `zabbix-cli`
        #
        # NOTE: there could be some edge cases where this assumption
        # is wrong, especially as we migrate to a new package name
        # however, that is such as special case - especially considering
        # NO ONE should be using pip instead of pipx or uv anyway
        packages = self.get_packages()
        if "zabbix-cli" in packages:
            return "zabbix-cli"
        elif "zabbix-cli-uio" in packages:
            return "zabbix-cli-uio"
        raise UpdateError(f"Unable to detect package name from {self.package_manager}.")


class UvUpdater(PypiUpdater):
    @property
    def package_manager(self) -> str:
        """The name of package manager used to install the package."""
        return "uv"

    @property
    def uninstall_command(self) -> List[str]:
        """The command used to uninstall the package."""
        return ["uv", "tool" "uninstall"]

    @property
    @abstractmethod
    def upgrade_command(self) -> List[str]:
        """The command used to upgrade the package."""
        return ["uv", "tool", "upgrade"]

    def get_packages(self) -> Set[str]:
        pkgs: Set[str] = set()

        out = subprocess.check_output(["uv", "tool", "list"], text=True)

        lines = out.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("-"):
                continue
            pkg, _, _ = line.partition(" ")
            pkgs.add(pkg)
        return pkgs


def download_file(url: str, destination: Path) -> None:
    logger.debug("Downloading %s to %s", url, destination)
    with httpx.stream("GET", url, follow_redirects=True) as response:
        with Progress() as progress:
            if response.status_code != 200:
                raise UpdateError(
                    f"Unable to download file {url}, status code {response.status_code}"
                )
            total = int(response.headers["Content-Length"])
            task = progress.add_task("[red]Downloading...[/red]", total=total)
            with open(destination, "wb") as file:
                for data in response.iter_bytes():
                    progress.update(
                        task,
                        advance=len(data),
                        description="[yellow]Downloading...[/yellow]",
                    )
                    file.write(data)
                progress.update(task, description="[green]Download Complete[/green]")
    logger.info("Downloaded %s to %s", url, destination)


# NOTE: Move to zabbix_cli.utils.fs?
def make_executable(path: Path) -> None:
    """Make a file executable."""
    if not path.exists():
        raise FileNotFoundError(
            f"File {path} does not exist. Unable to make it executable."
        )
    mode = path.stat().st_mode
    new_mode = mode | (mode & 0o444) >> 2  # copy R bits to X
    if new_mode != mode:
        path.chmod(new_mode)
        logger.info("Changed file mode of %s from %o to %o", path, mode, new_mode)
    else:
        logger.debug("File %s is already executable", path)


def move_file(src: Path, dest: Path) -> None:
    """Move a file to a new location."""
    src.rename(dest)
    logger.info(f"Moved {src} to {dest}")


class GitHubRelease(BaseModel):
    tag_name: str


class PyInstallerUpdater(Updater):
    BIN_NAMES: Dict[str, Dict[str, str]] = {
        "linux": {"x86_64": "zabbix-cli-ubuntu-latest-3.12"},
        "darwin": {"arm64": "zabbix-cli-macos-latest-3.12"},
        "win32": {"x86_64": "zabbix-cli-windows-latest-3.12.exe"},
    }
    URL_FMT = "https://github.com/unioslo/zabbix-cli/releases/latest/download/{bin}"
    """URL format for downloading the latest release."""

    URL_API_LATEST = "https://api.github.com/repos/unioslo/zabbix-cli/releases/latest"
    """URL for latest release info from API."""

    def update(self) -> Optional[UpdateInfo]:
        if not self.installation_info.bindir:
            raise UpdateError("Unable to determine PyInstaller binary directory")
        if not self.installation_info.executable:
            raise UpdateError("Unable to determine PyInstaller executable")
        dest_path = self.resolve_path(self.installation_info.executable)
        version = self.get_release_version()
        if version == __version__:
            exit_ok(f"Application is already up-to-date ({version})")
        self.download(dest_path)

    def get_release_version(self) -> str:
        """Get the latest release info."""
        resp = httpx.get(self.URL_API_LATEST)
        if resp.status_code != 200:
            raise UpdateError(f"Failed to get latest release: {resp.text}")
        release = GitHubRelease.model_validate_json(resp.text)
        return release.tag_name

    def resolve_path(self, path: Path) -> Path:
        """Attempts to resolve a Path in strict mode, falling back to resolving aliases."""
        try:
            return path.resolve(strict=True)
        except FileNotFoundError:
            # File does not exist, assume it's a shell alias, resolve that
            alias_path = self.resolve_alias(path.name)
            # Special case for python alias - we failed to resolve it properly here
            # and ended up resolving it to a Python interpreter instead of the
            # Zabbix-CLI pyinstaller executable
            if alias_path.name == "python":
                raise UpdateError(
                    "Unable to resolve PyInstaller executable. Please update manually."
                )
            return alias_path

    @staticmethod
    def resolve_alias(alias: str) -> Path:
        """Resolve a shell alias to its target path."""
        if sys.platform == "win32":
            raise UpdateError(f"Unable to resolve alias {alias!r} on Windows")

        out = subprocess.check_output(["type", "-a", alias], env=os.environ, text=True)
        lines = out.splitlines()
        logger.debug("Resolved alias %s to %s", alias, lines)
        for line in lines:
            if any(x in line for x in ["is an alias for", "is a shell function"]):
                logger.debug("Skipping line when resolving alias: %s", line)
                continue
            alias, _, path_str = line.partition(" is ")
            path_str = path_str.strip()
            return Path(path_str).resolve()
        raise UpdateError(f"Unable to resolve alias {alias}")

    @classmethod
    def get_url(cls) -> str:
        arch = platform.machine()
        try:
            b = cls.BIN_NAMES[sys.platform][arch]
        except KeyError:
            raise UpdateError(f"Unsupported platform + arch: {sys.platform} ({arch})")
        # NOTE: Pyright seems a bit confused about the string formatting here
        # It claims that LiteralString is not a valid str return type (??)
        return str(cls.URL_FMT.format(bin=b))

    def download(self, executable: Path) -> None:
        # TODO: Refactor: Moving and making executable should be part
        #       of the `update()` method. This method should just download
        #       the file. That will require us to pass the destination path
        #       to this method.
        #
        # TODO: improve resiliency and error handling here
        with tempfile.TemporaryDirectory() as tmpdir:
            url = self.get_url()
            logger.info(f"Downloading {url}")
            dest = Path(tmpdir) / "zabbix-cli"
            download_file(url, dest)
            # Move file to bindir
            # Assert dest file is readable and non-empty?
            move_file(dest, executable)
            make_executable(executable)


class InstallationMethod(StrEnum):
    GIT = "git"
    PIP = "pip"
    PIPX = "pipx"
    UV = "uv"
    PYINSTALLER = "pyinstaller"


class InstallationInfo(NamedTuple):
    method: InstallationMethod
    package: Optional[str] = None
    executable: Optional[Path] = None
    bindir: Optional[Path] = None


def to_path(p: str) -> Optional[Path]:
    try:
        return Path(p).expanduser().resolve()
    except Exception as e:
        logger.debug(f"Unable to resolve path {p}: {e}")
    return None


def cmd_exists(command: str, help: bool = True) -> bool:
    """Check if a command is available in the system."""
    cmd = [command, "--help"] if help else [command]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


# TODO: Consider moving static methods into each updater class
# or maybe even move all the detection methods into the updaters
# and have the InstallationMethodDetector just call `updater.detect()`


class InstallationMethodDetector:
    def __init__(self) -> None:
        self.executable = Path(sys.argv[0])
        self.parent_dir = self.executable.parent

    @classmethod
    def detect(cls) -> InstallationInfo:
        try:
            return cls().do_detect()
        except Exception as e:
            raise UpdateError(f"Unable to detect installation method: {e}") from e

    def do_detect(self) -> InstallationInfo:
        for method in [
            # Methods ranked in order of best->worst detection heuristics
            # as well as likelyhood of being used by the user
            self.detect_pyinstaller,
            self.detect_uv,
            self.detect_pipx,
            self.detect_pip,
            self.detect_git,
        ]:
            if (info := method()) is not None:
                logger.info("Detected installation method: %s", info.method)
                return info
        raise NotImplementedError("No detection methods succeeded")

    def detect_git(self) -> Optional[InstallationInfo]:
        """Get the path of the local Git repository."""
        f = Path(__file__).resolve()
        package_dir = f.parent.parent
        git_dir = package_dir / ".git"
        if not git_dir.exists():
            return
        if not git_dir.is_dir():
            return
        return InstallationInfo(method=InstallationMethod.GIT, bindir=package_dir)

    @staticmethod
    def get_pipx_bin_dir() -> Optional[Path]:
        if (bd := os.environ.get("PIPX_BIN_DIR")) and (bindir := to_path(bd)):
            return bindir
        try:
            t = subprocess.check_output(
                ["pipx", "environment", "--value", "PIPX_BIN_DIR"], text=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get pipx bin dir with command {e.cmd!r}: {e}")
            return
        except FileNotFoundError:
            return  # pipx not installed
        return to_path(t)

    def detect_pipx(self) -> Optional[InstallationInfo]:
        if not cmd_exists("pipx"):
            return
        bindir = self.get_pipx_bin_dir()
        if not bindir:
            return
        if not (self.parent_dir == bindir or self.parent_dir in bindir.parents):
            return
        return InstallationInfo(method=InstallationMethod.PIPX, bindir=bindir)

    @staticmethod
    def has_pip_package(pkg: str) -> bool:
        try:
            subprocess.check_call(["pip", "show", pkg])
        except subprocess.CalledProcessError:
            return False
        return True

    def detect_pip(self) -> Optional[InstallationInfo]:
        if not cmd_exists("pip"):
            return
        for pkg in ["zabbix-cli", "zabbix-cli-uio"]:
            if self.has_pip_package(pkg):
                return InstallationInfo(method=InstallationMethod.PIP, package=pkg)

    def detect_pyinstaller(self) -> Optional[InstallationInfo]:
        if not hasattr(sys, "_MEIPASS"):
            return
        # TODO: resolve alias, symlinks, etc.
        return InstallationInfo(
            method=InstallationMethod.PYINSTALLER,
            executable=self.executable,
            bindir=self.parent_dir,
        )

    @staticmethod
    def get_uv_bin_dir() -> Optional[Path]:
        try:
            t = subprocess.check_output(["uv", "tool", "dir"], text=True)
        except subprocess.CalledProcessError:
            return
        except FileNotFoundError:
            return
        return to_path(t)

    @staticmethod
    def get_uv_pkg_name() -> Optional[str]:
        for pkg in ZCLI_PACKAGES:
            try:
                subprocess.check_output(["uv", "tool", "list", pkg])
            except subprocess.CalledProcessError:
                continue
            return pkg

    def detect_uv(self) -> Optional[InstallationInfo]:
        if not cmd_exists("uv"):
            return
        bindir = self.get_uv_bin_dir()
        if not bindir:
            return
        if not (self.parent_dir == bindir or self.parent_dir in bindir.parents):
            return
        return InstallationInfo(method=InstallationMethod.UV, bindir=bindir)


UPDATERS: Dict[InstallationMethod, Type[Updater]] = {
    InstallationMethod.PYINSTALLER: PyInstallerUpdater,
    # InstallationMethod.GIT: GitUpdater,
    # InstallationMethod.PIP: PipUpdater,
    # InstallationMethod.PIPX: PipxUpdater,
    # InstallationMethod.UV: UvUpdater,
}


class UpdateInfo(NamedTuple):
    method: InstallationMethod
    version: str


def get_updater(method: InstallationMethod) -> Type[Updater]:
    updater = UPDATERS.get(method)
    if updater is None:
        raise UpdateError(f"No updater available for installation method {method}")
    return updater


def update(update_method: Optional[InstallationMethod] = None) -> Optional[UpdateInfo]:
    """Update the application to the latest version.

    Args:
        update_method (Optional[InstallationMethod], optional):
            Update using a specific update method. Defaults to None.
            Auto-detects the installation method if not provided.

    Raises:
        UpdateError: If the update fails.

    Returns:
        Optional[UpdateInfo]: Information about the update, such as version, method, etc.
    """
    if not update_method:
        info = InstallationMethodDetector.detect()
    else:
        info = InstallationInfo(method=update_method)

    updater = get_updater(info.method)

    try:
        return updater(info).update()
    except Exception as e:
        raise UpdateError(f"Failed to update using {info.method}: {e}") from e
