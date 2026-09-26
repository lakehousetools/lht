"""Unit tests for lht.util.sql, the guard on names formatted into Snowflake SQL."""
import pytest

from lht.util.sql import identifier, literal


@pytest.mark.parametrize("name", [
    "ACCOUNT",
    "raw_salesforce",
    "DB.SCHEMA.TABLE",
    "SCHEMA.TMP_ACCOUNT",
    '"Mixed Case Table"',
    "TABLE$1",
])
def test_valid_names_pass_through_unchanged(name):
    assert identifier(name) == name


@pytest.mark.parametrize("name", [
    "ACCOUNT; DROP TABLE USERS",
    "ACCOUNT --",
    "A.B.C.D",
    "1TABLE",
    "",
    "'quoted'",
    '"has"quote"',
    "RAW.ACCOUNT)",
])
def test_names_that_could_inject_sql_are_rejected(name):
    with pytest.raises(ValueError):
        identifier(name)


def test_literal_escapes_single_quotes():
    assert literal("O'Brien") == "'O''Brien'"


def test_literal_renders_none_as_null():
    assert literal(None) == "NULL"
