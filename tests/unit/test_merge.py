"""
Unit tests for lht.util.merge.merge_into_target()'s SQL generation.

No live Snowflake connection - session.sql() is faked so DESCRIBE TABLE calls
return canned column lists and the generated MERGE statement is captured for
inspection instead of actually running anywhere.

These are regression tests for two bugs fixed together:
  - identifiers used to be quoted in table creation but not in later
    queries, so Snowflake's case-folding made them refer to different
    objects for any table name with lowercase letters;
  - the sync write path used a plain INSERT instead of a MERGE, so a record
    that changed in Salesforce and got re-synced was appended as a new row
    instead of updated in place.
"""
import re

import pytest

from lht.util import merge


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows


class FakeSnowparkSession:
    """Stand-in for a Snowpark Session, just enough for merge.py to run.

    describe_by_table maps an (unquoted, uppercase) table name to the list
    of {'name': ..., 'type': ...} rows a `DESCRIBE TABLE` would return.
    Every statement passed to .sql() is recorded in .executed.
    """

    def __init__(self, describe_by_table):
        self.describe_by_table = describe_by_table
        self.executed = []

    def sql(self, query):
        self.executed.append(query)
        match = re.match(r"\s*DESCRIBE TABLE\s+(\S+)", query, re.IGNORECASE)
        if match:
            return _FakeResult(self.describe_by_table.get(match.group(1), []))
        return _FakeResult([])


def _row(name, type_):
    return {"name": name, "type": type_}


@pytest.fixture
def session():
    return FakeSnowparkSession(
        {
            "TMP_ACCOUNT": [_row("ID", "VARCHAR(16777216)"), _row("NAME", "VARCHAR(16777216)")],
            "ACCOUNT": [_row("ID", "VARCHAR(18)"), _row("NAME", "VARCHAR(255)")],
        }
    )


def _merge_statement(session):
    statements = [q for q in session.executed if q.strip().upper().startswith("MERGE INTO")]
    assert len(statements) == 1, f"expected exactly one MERGE statement, got {len(statements)}"
    return statements[0]


def test_merge_is_actually_executed(session):
    # The bug this guards against: merge.py used to build a MERGE string and
    # just return it without ever calling session.sql() on it.
    merge.merge_into_target(session, "TMP_ACCOUNT", "ACCOUNT", "id")
    assert any(q.strip().upper().startswith("MERGE INTO") for q in session.executed)


def test_no_identifier_is_quoted(session):
    merge.merge_into_target(session, "TMP_ACCOUNT", "ACCOUNT", "id")
    assert '"' not in _merge_statement(session)


def test_targets_the_right_table_and_uppercases_the_match_field(session):
    merge.merge_into_target(session, "TMP_ACCOUNT", "ACCOUNT", "id")
    merge_sql = _merge_statement(session)

    assert "MERGE INTO ACCOUNT tgt" in merge_sql
    assert "FROM TMP_ACCOUNT) src" in merge_sql
    assert "ON tgt.ID = src.ID" in merge_sql


def test_has_both_a_matched_update_and_not_matched_insert_branch(session):
    merge.merge_into_target(session, "TMP_ACCOUNT", "ACCOUNT", "id")
    merge_sql = _merge_statement(session)

    assert "WHEN MATCHED THEN UPDATE SET" in merge_sql
    assert "NAME = src.NAME" in merge_sql
    assert "WHEN NOT MATCHED THEN INSERT (ID, NAME)" in merge_sql
    assert "VALUES (src.ID, src.NAME)" in merge_sql


def test_match_field_is_not_reassigned_in_the_update_branch(session):
    merge.merge_into_target(session, "TMP_ACCOUNT", "ACCOUNT", "id")
    merge_sql = _merge_statement(session)

    update_clause = merge_sql.split("WHEN MATCHED THEN UPDATE SET", 1)[1]
    update_clause = update_clause.split("WHEN NOT MATCHED", 1)[0]
    assert "ID = src.ID" not in update_clause


def test_match_field_not_a_target_column_raises(session):
    with pytest.raises(ValueError):
        merge.merge_into_target(session, "TMP_ACCOUNT", "ACCOUNT", "not_a_real_column")
