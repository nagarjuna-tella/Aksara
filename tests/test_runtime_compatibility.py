import pytest

from aksara.runtime_compatibility import python_support_status


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ((3, 9), "too_old"),
        ((3, 10), "too_old"),
        ((3, 11), "supported"),
        ((3, 14), "supported"),
        ((3, 15), "too_new"),
        ((4, 0), "too_new"),
    ],
)
def test_python_support_status(version, expected):
    assert python_support_status(version) == expected
