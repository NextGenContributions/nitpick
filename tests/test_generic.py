"""Generic functions tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PosixPath, WindowsPath
from typing import Generator
from unittest import mock

import pytest
from furl import furl
from src.nitpick.plugins.ini import Violations
from src.nitpick.violations import Fuss
from testfixtures import compare

from nitpick.constants import EDITOR_CONFIG, GIT_DIR, GIT_IGNORE, PYTHON_TOX_INI
from nitpick.generic import (
    _url_to_posix_path,
    _url_to_windows_path,
    get_global_gitignore_path,
    glob_non_ignored_files,
    relative_to_current_dir,
)
from nitpick.plugins import FileInfo
from tests.helpers import ProjectMock


@mock.patch.object(Path, "cwd")
@mock.patch.object(Path, "home")
def test_relative_to_current_dir(home, cwd):
    """Mock the home and current dirs, and test relative paths to them (testing Linux-only)."""
    if sys.platform == "win32":
        home_dir = "C:\\Users\\john"
        project_dir = f"{home_dir}\\project"
    else:
        home_dir = "/home/john"
        project_dir = f"{home_dir}/project"
    home.return_value = Path(home_dir)
    cwd.return_value = Path(project_dir)
    sep = os.path.sep

    examples = {
        None: "",
        project_dir: "",
        Path(project_dir): "",
        f"{home_dir}{sep}another": f"{home_dir}{sep}another",
        Path(f"{home_dir}{sep}bla{sep}bla"): f"{home_dir}{sep}bla{sep}bla",
        f"{project_dir}{sep}{PYTHON_TOX_INI}": PYTHON_TOX_INI,
        f"{project_dir}{sep}{EDITOR_CONFIG}": EDITOR_CONFIG,
        Path(f"{project_dir}{sep}apps{sep}manage.py"): f"apps{sep}manage.py",
        f"{home_dir}{sep}another{sep}one{sep}bites.py": f"{home_dir}{sep}another{sep}one{sep}bites.py",
        Path(f"{home_dir}{sep}bla{sep}bla.txt"): f"{home_dir}{sep}bla{sep}bla.txt",
    }
    if sys.platform == "win32":
        examples.update(
            {
                "d:\\Program Files\\MyApp": "d:\\Program Files\\MyApp",
                Path("d:\\Program Files\\AnotherApp"): "d:\\Program Files\\AnotherApp",
                "C:\\System32\\win32.dll": "C:\\System32\\win32.dll",
                Path("E:\\network\\file.txt"): "E:\\network\\file.txt",
            }
        )
    else:
        examples.update(
            {
                "/usr/bin/some": "/usr/bin/some",
                Path("/usr/bin/awesome"): "/usr/bin/awesome",
                "/usr/bin/something/wicked/this-way-comes.cfg": "/usr/bin/something/wicked/this-way-comes.cfg",
                Path("/usr/bin/.awesome"): "/usr/bin/.awesome",
            }
        )

    for path, expected in examples.items():
        compare(actual=relative_to_current_dir(path), expected=expected, prefix=f"Path: {path}")


@pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
@pytest.mark.parametrize("test_path", ["C:\\", r"C:\path\file.toml", r"//server/share/path/file.toml"])
def test_url_to_windows_path(test_path):
    """Verify that Path to URL to Path conversion preserves the path."""
    path = WindowsPath(test_path)
    url = furl(path.as_uri())
    assert _url_to_windows_path(url) == path


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only test")
@pytest.mark.parametrize("test_path", ["/", "/path/to/file.toml", "//double/slash/path.toml"])
def test_url_to_posix_path(test_path):
    """Verify that Path to URL to Path conversion preserves the path."""
    path = PosixPath(test_path)
    url = furl(path.as_uri())
    assert _url_to_posix_path(url) == path


@pytest.fixture
def some_directory(tmp_path: Path, request) -> Generator[Path, None, None]:
    """Create some directory with some files."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "file1.txt").touch()
    (project_dir / "README.md").touch()
    src_dir = project_dir / "src"
    src_dir.mkdir()
    (src_dir / "module.py").touch()

    if "local" in request.param:
        (project_dir / GIT_DIR).mkdir()
        (project_dir / GIT_IGNORE).write_text("*.txt")

    output = ""
    if "global" in request.param:
        (project_dir / GIT_DIR).mkdir()
        global_file = tmp_path / "some-global-gitignore-file"
        global_file.write_text("*.md")
        output = str(global_file) + os.linesep

    with mock.patch("subprocess.check_output", return_value=output):
        yield project_dir


@pytest.mark.parametrize("some_directory", ["local"], indirect=True)
def test_glob_local_gitignore(some_directory: Path) -> None:
    """Test globbing non-ignored files."""
    assert set(glob_non_ignored_files(some_directory)) == {
        some_directory / GIT_IGNORE,
        some_directory / "README.md",
        some_directory / "src" / "module.py",
    }
    assert set(glob_non_ignored_files(some_directory, "*.md")) == {some_directory / "README.md"}
    assert set(glob_non_ignored_files(some_directory, "*.txt")) == set()
    assert set(glob_non_ignored_files(some_directory, "**/*.py")) == {some_directory / "src" / "module.py"}


@pytest.mark.parametrize("some_directory", ["no_git_dir"], indirect=True)
def test_glob_no_git_dir(some_directory: Path) -> None:
    """Test globbing non-ignored files."""
    assert set(glob_non_ignored_files(some_directory)) == {
        some_directory / "file1.txt",
        some_directory / "README.md",
        some_directory / "src" / "module.py",
    }


@pytest.mark.parametrize("some_directory", ["global"], indirect=True)
def test_glob_global_gitignore(some_directory: Path) -> None:
    """Test globbing non-ignored files."""
    assert set(glob_non_ignored_files(some_directory)) == {
        some_directory / "file1.txt",
        some_directory / "src" / "module.py",
    }


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (
            subprocess.CalledProcessError(1, "git"),
            "The 'core.excludesFile' configuration is not set or does not exist.",
        ),
        (FileNotFoundError, "Git command not found. Please make sure Git is installed and on the PATH."),
    ],
)
@mock.patch("subprocess.check_output")
def test_error_when_calling_git_config(mock_check_output, capsys, exception: Exception, message: str) -> None:
    """Test error when calling git config."""
    mock_check_output.side_effect = exception
    assert get_global_gitignore_path() is None
    captured = capsys.readouterr()
    assert captured.err.strip().casefold() == message.strip().casefold()


@pytest.mark.parametrize(
    ("filepath", "expected_tags"),
    [
        ("foo/.pylintrc.toml", {"pylintrc", "text", "toml"}),
        ("foo/pylintrc.toml", {"pylintrc", "text", "toml"}),
        ("foo/.pylintrc", {"pylintrc", "text", "ini"}),
        ("foo/pylintrc", {"pylintrc", "text", "ini"}),
    ],
)
def test_different_types_of_pylintrc_config_should_work(filepath: str, expected_tags: set[str], tmp_path: Path):
    """Different pylintrc configs should have different expected tags.

    'pylintrc' is a special case where the config can either be a TOML or INI file.
    Determining the correct tags is important for the plugins to work correctly.
    Having an incorrect plugin working on a file can lead to unexpected results.

    More on how pylint search for and use configuration files:
    https://pylint.pycqa.org/en/latest/user_guide/usage/run.html#command-line-options
    """
    project = ProjectMock(tmp_path)
    info = FileInfo.create(project, filepath)
    assert info.tags == expected_tags


def test_unknown_file_should_raise_unknown_file_error(tmp_path):
    """Test a file with unknown extension and name, which should cause unknown file error."""
    filepath = "conf/.shellcheckrc"
    ProjectMock(tmp_path).save_file(
        filepath,
        """
        ; empty ini file, nothing but a comment
        """,
    ).style(
        f"""
        ["{filepath}".conf]
        enable = "all"
        """
    ).api_check_then_fix(
        Fuss(
            fixed=False,
            filename="nitpick-style.toml",
            code=1,
            message=" has an incorrect style. Invalid config:",
            suggestion="conf/.shellcheckrc: Unknown file. See https://nitpick.rtfd.io/en/latest/plugins.html.",
        )
    )


def test_explicit_files_tags_can_be_used_to_handle_unknown_file(tmp_path):
    """Test explicit files tags can be used to handle unknown file whose extension and name are not recognized."""
    filepath = "conf/.shellcheckrc"
    ProjectMock(tmp_path).save_file(
        filepath,
        """
        ; empty ini file, nothing but a comment
        """,
    ).style(
        f"""
        [nitpick.files.tags]
        "{filepath}" = ["ini"]

        ["{filepath}".conf]
        enable = "all"
        """
    ).api_check_then_fix(
        Fuss(
            fixed=True,
            filename=filepath,
            code=Violations.MISSING_SECTIONS.code,
            message=" has some missing sections. Use this:",
            suggestion="[conf]\nenable = all",
        )
    ).assert_file_contents(
        filepath,
        """
        ; empty ini file, nothing but a comment

        [conf]
        enable = all
        """,
    )
