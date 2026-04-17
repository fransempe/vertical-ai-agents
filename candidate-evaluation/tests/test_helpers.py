"""Tests unitarios de utils.helpers (sin I/O)."""

import pytest

from utils.helpers import clean_uuid, is_valid_uuid


@pytest.mark.parametrize(
    "value,expected",
    [
        ("550e8400-e29b-41d4-a716-446655440000", True),
        ("00000000-0000-0000-0000-000000000000", True),
        ("not-a-uuid", False),
        ("", False),
        (None, False),
    ],
)
def test_is_valid_uuid(value, expected):
    assert is_valid_uuid(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            "550e8400-e29b-41d4-a716-446655440000",
            "550e8400-e29b-41d4-a716-446655440000",
        ),
        (
            '"550e8400-e29b-41d4-a716-446655440000"',
            "550e8400-e29b-41d4-a716-446655440000",
        ),
        (
            "'550e8400-e29b-41d4-a716-446655440000'",
            "550e8400-e29b-41d4-a716-446655440000",
        ),
        ("  550e8400-e29b-41d4-a716-446655440000  ", "550e8400-e29b-41d4-a716-446655440000"),
        ("invalid", None),
        ("", None),
        (None, None),
    ],
)
def test_clean_uuid(value, expected):
    assert clean_uuid(value) == expected
