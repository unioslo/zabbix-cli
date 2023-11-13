import pytest

from zabbix_cli.version import StrictVersion


# as of now, we only use the StrictVersion class in the application, hence
# we only test that class


mark_compfail = pytest.mark.xfail(strict=True, raises=AssertionError)
"""Test must fail with an AssertionError."""


@pytest.mark.parametrize(
    "input",
    [
        pytest.param(
            "7.0.0",
            id="full version",
        ),
        pytest.param(
            "7.0",
            id="no patch",
        ),
        pytest.param(
            "7.1.2a1",
            id="with alpha (a)",
        ),
        pytest.param(
            "7.0a1",
            id="with alpha (a) (no patch)",
        ),
        pytest.param(
            "7.0.0alpha7",
            id="with alpha (alpha)",
        ),
        pytest.param(
            "7.0.0b7",
            id="with beta (b)",
        ),
        pytest.param(
            "7.0.0beta7",
            id="with beta (beta)",
        ),
        pytest.param(
            "7.0.0rc7",
            id="with rc",
        ),
        pytest.param(
            "7",
            id="no minor (FAIL)",
            marks=pytest.mark.xfail(strict=True, raises=ValueError),
        ),
    ],
)
def test_strict_version_init(input: str):
    """Tests that we can instantiate a StrictVersion object."""
    s = StrictVersion(input)
    assert s.version is not None


@pytest.mark.parametrize(
    "input,other",
    [
        # OK cases
        pytest.param("7.0", "7.0", id="no patch"),
        pytest.param("7.0.0", "7.0", id="with patch (input)"),
        pytest.param("7.0", "7.0.0", id="with patch (other)"),
        # FAIL cases (input != other)
        pytest.param("7.0", "6.0", id="major (FAIL)", marks=mark_compfail),
        pytest.param("6.0", "6.4", id="minor (FAIL)", marks=mark_compfail),
        pytest.param("7.0.0", "7.0.0rc1", id="rc (FAIL)", marks=mark_compfail),
    ],
)
def test_strict_version_eq(input: str, other: str):
    assert StrictVersion(input) == StrictVersion(other)


@pytest.mark.parametrize(
    "input,other",
    [
        # OK cases
        pytest.param("6.0.0", "7.0.0", id="major"),
        pytest.param("6.0", "7.0.0", id="major (no patch)"),
        pytest.param("7.0.0", "7.1.0", id="minor"),
        pytest.param("7.0", "7.1", id="minor (no patch)"),
        pytest.param("7.0.1", "7.1.0", id="minor (input.patch > other.patch)"),
        pytest.param("7.0.1", "7.1", id="input w/ patch, other w/o patch"),
        pytest.param("6.0", "6.4", id="minor"),
        pytest.param("7.0rc1", "7.0.0", id="rc"),  # rc is treated as lesser than non-rc
        # FAIL cases (input > other)
        pytest.param("7.0", "6.0", id="major (FAIL)", marks=mark_compfail),
        pytest.param("7.0", "7.0.0rc1", id="rc (FAIL)", marks=mark_compfail),
        pytest.param(
            "7.0.0",
            "6.9.9",
            id="greater major (lesser minor+patch) (FAIL)",
            marks=mark_compfail,
        ),
    ],
)
def test_strict_version_lt(input: str, other: str):
    assert StrictVersion(input) < StrictVersion(other)


@pytest.mark.parametrize(
    "input,other",
    [
        # OK cases
        pytest.param("7.1", "7.1", id="equal major+minor"),
        pytest.param("7.1.2", "7.1.2", id="equal major+minor+patch"),
        pytest.param("6.0.0", "7.0.0", id="lesser major"),
        pytest.param("7.0.0", "7.1.0", id="lesser minor"),
        pytest.param("7.0.0", "7.0.1", id="lesser patch"),
        pytest.param("7.1.2", "7.2.3", id="lesser minor+patch"),
        pytest.param("6.0", "7.0.0", id="lesser major (no patch)"),
        pytest.param("7.0", "7.1", id="lesser minor (no patch)"),
        pytest.param("7.0.1", "7.1.0", id="lesser minor (input.patch > other.patch)"),
        pytest.param("7.0.1", "7.1", id="lesser input w/ patch, other w/o patch"),
        pytest.param("6.0", "6.4", id="lesser minor"),  # 6.4 sanity check
        pytest.param("7.0rc1", "7.0.0", id="rc"),
        pytest.param("7.0rc1", "7.0.0rc1", id="rc (equal)"),
        pytest.param("7.0rc1", "7.0.0rc2", id="rc (lesser)"),
        # FAIL cases (input > other)
        pytest.param("7.0", "7.0.0rc1", id="rc (FAIL)", marks=mark_compfail),
        pytest.param("7.0", "6.0", id="greater major (FAIL)", marks=mark_compfail),
        pytest.param(
            "7.0.0",
            "6.9.9",
            id="greater major (lesser minor+patch) (FAIL)",
            marks=mark_compfail,
        ),
    ],
)
def test_strict_version_le(input: str, other: str):
    assert StrictVersion(input) <= StrictVersion(other)


@pytest.mark.parametrize(
    "input,other",
    [
        # OK cases
        pytest.param("7.0.0", "6.0.0", id="major"),
        pytest.param("7.0", "6.0.0", id="major (no patch)"),
        pytest.param("7.1.0", "7.0.0", id="minor"),
        pytest.param("7.1", "7.0", id="minor (no patch)"),
        pytest.param("7.1.1", "7.0.1", id="minor (input.patch < other.patch)"),
        pytest.param("7.1.1", "7.0", id="input w/ patch, other w/o patch"),
        pytest.param("6.4", "6.0", id="minor"),  # sanity check for 6.4 (important)
        pytest.param(
            "7.0.0", "7.0.0rc1", id="no rc"
        ),  # rc is treated as lesser than non-rc
        pytest.param("7.0.0rc2", "7.0.0rc1", id="rc (greater)"),
        # FAIL cases (input > other)
        pytest.param("7.0.0rc1", "7.0.0", id="rc (FAIL)", marks=mark_compfail),
        pytest.param("6.9.9", "7.0.0", id="major (FAIL)", marks=mark_compfail),
        pytest.param(
            "6.0",
            "7.0",
            id="major (no patch) (FAIL)",
            marks=mark_compfail,
        ),
    ],
)
def test_strict_version_gt(input: str, other: str):
    assert StrictVersion(input) > StrictVersion(other)


@pytest.mark.parametrize(
    "input,other",
    [
        # OK cases
        pytest.param("7.0.0", "7.0.0", id="equal"),
        pytest.param("7.0.0", "7.0.0", id="equal (no patch)"),
        pytest.param("7.0.0", "6.0.0", id="greater major"),
        pytest.param("7.0", "6.0.0", id="greater major"),
        pytest.param("7.1.0", "7.0.0", id="greater minor"),
        pytest.param("7.1", "7.1.0", id="greater minor (no patch)"),
        pytest.param("7.1.1", "7.0.1", id="minor (input.patch < other.patch)"),
        pytest.param("7.1.1", "7.0", id="input w/ patch, other w/o patch"),
        pytest.param("6.4", "6.0", id="minor"),
        pytest.param(
            "7.0.0", "7.0.0rc1", id="no rc"
        ),  # rc is treated as lesser than non-rc
        pytest.param("7.0.0rc1", "7.0.0rc1", id="rc (equal)"),
        pytest.param("7.0.0rc2", "7.0.0rc1", id="rc (greater)"),
        # FAIL cases (input > other)
        pytest.param("7.0.0rc1", "7.0.0", id="rc (FAIL)", marks=mark_compfail),
        pytest.param("6.9.9", "7.0.0", id="major (FAIL)", marks=mark_compfail),
        pytest.param(
            "6.0",
            "7.0",
            id="major (no patch) (FAIL)",
            marks=mark_compfail,
        ),
    ],
)
def test_strict_version_ge(input: str, other: str):
    assert StrictVersion(input) >= StrictVersion(other)
