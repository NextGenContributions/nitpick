"""TOML tests."""

from nitpick.constants import PYTHON_PYPROJECT_TOML
from nitpick.plugins.toml import TomlPlugin
from nitpick.violations import Fuss, SharedViolations
from tests.helpers import ProjectMock


def test_pyproject_has_no_configuration(tmp_path):
    """File should not be deleted unless explicitly asked."""
    ProjectMock(tmp_path).style("").pyproject_toml("").api_check_then_fix()


def test_pyproject_toml_file_present(tmp_path):
    """Suggest poetry init when pyproject.toml does not exist."""
    ProjectMock(tmp_path, pyproject_toml=False).style(
        """
        [nitpick.files.present]
        "pyproject.toml" = "Do something"
        """
    ).api_check_then_fix(Fuss(False, PYTHON_PYPROJECT_TOML, 103, " should exist: Do something")).cli_run(
        f"{PYTHON_PYPROJECT_TOML}:1: NIP103  should exist: Do something", violations=1
    )


def test_suggest_initial_contents(tmp_path):
    """Suggest contents when TOML files do not exist."""
    filename = "my.toml"
    expected_toml = """
        [section]
        key = "value"
        number = 10
        list = [ "a", "b", "c",]
    """
    ProjectMock(tmp_path).style(
        f"""
        ["{filename}".section]
        key = "value"
        number = 10
        list = ["a", "b", "c"]
        """
    ).api_check_then_fix(
        Fuss(
            True,
            filename,
            SharedViolations.CREATE_FILE_WITH_SUGGESTION.code + TomlPlugin.violation_base_code,
            " was not found. Create it with this content:",
            expected_toml,
        )
    ).assert_file_contents(
        filename, expected_toml
    )


def test_missing_different_values_pyproject_toml(tmp_path):
    """Test missing and different values on pyproject.toml."""
    ProjectMock(tmp_path).style(
        """
        ["pyproject.toml".something]
        yada = "after"

        ["pyproject.toml".tool]
        missing = "value"

        ["pyproject.toml".config]
        list = ["a", "b", "c"]
        """
    ).pyproject_toml(
        """
        [something]
        x = 1  # comment for x
        yada = "before"  # comment for yada yada
        abc = "123" # comment for abc

        [config]
        list = ["a", "b"] # comment for list
        """
    ).api_check_then_fix(
        Fuss(
            True,
            PYTHON_PYPROJECT_TOML,
            319,
            " has different values. Use this:",
            """
            [something]
            yada = "after"
            """,
        ),
        Fuss(
            True,
            PYTHON_PYPROJECT_TOML,
            318,
            " has missing values:",
            """
            [tool]
            missing = "value"

            [config]
            list = [ "c",]
            """,
        ),
    ).assert_file_contents(
        PYTHON_PYPROJECT_TOML,
        """
        [something]
        x = 1  # comment for x
        yada = "after"  # comment for yada yada
        abc = "123" # comment for abc

        [config]
        list = ["a", "b", "c"] # comment for list

        [tool]
        missing = "value"
        """,
    )


def test_missing_different_values_any_toml(tmp_path):
    """Test different and missing keys/values on any TOML."""
    filename = "any.toml"
    ProjectMock(tmp_path).save_file(
        filename,
        """
        [section]
        # Line comment
        key = "original value"
        """,
    ).style(
        f"""
        ["{filename}".section]
        key = "new value"
        number = 5
        list = ["a", "b", "c"]
        """
    ).api_check_then_fix(
        Fuss(
            True,
            filename,
            TomlPlugin.violation_base_code + SharedViolations.DIFFERENT_VALUES.code,
            " has different values. Use this:",
            """
            [section]
            key = "new value"
            """,
        ),
        Fuss(
            True,
            filename,
            TomlPlugin.violation_base_code + SharedViolations.MISSING_VALUES.code,
            " has missing values:",
            """
            [section]
            number = 5
            list = [ "a", "b", "c",]
            """,
        ),
    ).assert_file_contents(
        filename,
        """
        [section]
        # Line comment
        key = "new value"
        number = 5
        list = ["a", "b", "c"]
        """,
    )


def test_falsy_values_should_be_reported_and_fixed(tmp_path, datadir):
    """Test that falsy and truthy values are included in the report."""
    filename = "foo/file.toml"
    project = ProjectMock(tmp_path).save_file(filename, datadir / "falsy_values/actual.toml")
    project.style(datadir / "falsy_values/desired.toml").api_check_then_fix(
        Fuss(
            True,
            filename,
            319,
            " has different values. Use this:",
            """
            boolean_true_unmatch = true
            boolean_false_unmatch = false
            string_a_unmatch = "string_a"
            string_b_unmatch = "string_b"
            truthy_int_unmatch = 1
            falsy_int_unmatch = 0
            truthy_float_unmatch = 1.0
            falsy_float_unmatch = 0.0
            """,
        )
    ).assert_file_contents(filename, datadir / "falsy_values/expected.toml")
    project.api_check().assert_violations()


def test_missing_quoted_section_should_be_reported_and_fixed(tmp_path):
    """Test that a missing quoted section are reported and added as a fix."""
    filename = "foo/file.toml"
    project = ProjectMock(tmp_path).save_file(
        filename,
        """
        [existing_section]
        key = "value"
        """,
    )
    project.style(
        """
        ["foo/file.toml"."quoted section"]
        key = "value"

        ["foo/file.toml"."quoted section".nested]
        key = "value"
        """
    ).api_check_then_fix(
        Fuss(
            True,
            filename,
            318,
            " has missing values:",
            '["quoted section"]\nkey = "value"\n\n["quoted section".nested]\nkey = "value"',
        ),
    ).assert_file_contents(
        filename,
        """
        [existing_section]
        key = "value"

        ["quoted section"]
        key = "value"

        ["quoted section".nested]
        key = "value"
        """,
    )


def test_modify_quoted_section_value_should_be_reported_and_fixed(tmp_path):
    """Test that modifying a value in a quoted section name works correctly."""
    filename = "foo/file.toml"
    project = ProjectMock(tmp_path).save_file(
        filename,
        """
        [existing_section]
        key = "value"

        ["quoted section"]
        key = "value"

        ["quoted section".nested]
        key = "value"
        """,
    )
    project.style(
        """
        ["foo/file.toml"."quoted section"]
        key = "value_to_modify"

        ["foo/file.toml"."quoted section".nested]
        key = "value_to_modify"
        """
    ).api_check_then_fix(
        Fuss(
            True,
            filename,
            319,
            " has different values. Use this:",
            '["quoted section"]\n'
            'key = "value_to_modify"\n\n'
            '["quoted section".nested]\n'
            'key = "value_to_modify"',
        )
    ).assert_file_contents(
        filename,
        """
        [existing_section]
        key = "value"

        ["quoted section"]
        key = "value_to_modify"

        ["quoted section".nested]
        key = "value_to_modify"
        """,
    )
