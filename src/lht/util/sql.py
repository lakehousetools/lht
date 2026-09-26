"""Guards for values interpolated into Snowflake SQL."""

import re

# One name part: unquoted (letters, digits, _ and $, not starting with a digit)
# or double-quoted with no quote characters inside.
_PART = r'(?:[A-Za-z_][A-Za-z0-9_$]*|"[^"\']+")'
_IDENTIFIER = re.compile(rf'^{_PART}(?:\.{_PART}){{0,2}}$')


def identifier(name) -> str:
    """Returns name unchanged if it is a valid Snowflake object name, else raises.

    Database, schema and table names reach SQL through string formatting, so a
    name like ``X; DROP TABLE Y`` must be rejected before it gets there. Names
    are validated rather than quoted because quoting would make them
    case-sensitive and change which object an existing command refers to.
    Accepts ``TABLE``, ``SCHEMA.TABLE`` and ``DB.SCHEMA.TABLE``.
    """
    text = str(name).strip()
    if not _IDENTIFIER.match(text):
        raise ValueError(f"Not a valid Snowflake identifier: {name!r}")
    return text


def literal(value) -> str:
    """Renders value as a single-quoted SQL string literal, or NULL."""
    if value is None:
        return 'NULL'
    return "'{}'".format(str(value).replace("'", "''"))
