"""retl: every source row is sent exactly once, and NULLs clear fields only when asked to."""

from unittest import mock

from lht.salesforce import retl


class _Row:
    def __init__(self, **kv):
        self._kv = kv

    def asDict(self):
        return dict(self._kv)


class _Session:
    """Counts queries; returns the rows in a different order on every call, as Snowflake may."""

    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def sql(self, query):
        self.queries.append(query)
        call = len(self.queries)
        rows = self.rows[call % len(self.rows):] + self.rows[:call % len(self.rows)]
        return mock.Mock(collect=mock.Mock(return_value=rows))


def _run_upsert(rows, batch_size, **kw):
    sent = []
    posted = mock.Mock(status_code=200, json=mock.Mock(return_value={"id": "750x"}))
    with mock.patch.object(retl.requests, "post", return_value=posted), \
         mock.patch.object(retl.ingest, "send_file", side_effect=lambda a, j, data: sent.append(data)), \
         mock.patch.object(retl.ingest, "job_close", return_value={}), \
         mock.patch.object(retl.ingest, "job_status", return_value={"id": "750x", "state": "JobComplete"}), \
         mock.patch.object(retl, "_log_job"):
        session = _Session(rows)
        result = retl.upsert(session, {"access_token": "t", "instance_url": "https://x"},
                             "Account", "SELECT 1", "Ext__c", batch_size=batch_size, **kw)
    return session, sent, result


def test_upsert_reads_the_query_once_and_sends_each_row_once():
    rows = [_Row(Ext__c=f"K{i}", Name=f"n{i}") for i in range(7)]
    session, sent, result = _run_upsert(rows, batch_size=3)

    # One read, however many batches -- re-running it per batch is what lost rows.
    assert len(session.queries) == 1
    assert result["total_batches"] == 3
    keys = [line.split(",")[0] for payload in sent for line in payload.strip().splitlines()[1:]]
    assert sorted(keys) == sorted(f"K{i}" for i in range(7))


def test_nulls_are_empty_cells_by_default():
    rows = [_Row(Ext__c="K1", Floor_Suite__c=None)]
    _, sent, _ = _run_upsert(rows, batch_size=10)
    assert sent[0].strip().splitlines()[1] == "K1,"


def test_clear_nulls_sends_na_so_salesforce_clears_the_field():
    rows = [_Row(Ext__c="K1", Floor_Suite__c=None)]
    _, sent, _ = _run_upsert(rows, batch_size=10, clear_nulls=True)
    assert sent[0].strip().splitlines()[1] == "K1,#N/A"


def test_update_honours_clear_nulls():
    captured = {}
    posted = mock.Mock(json=mock.Mock(return_value={"id": "750y"}))
    session = mock.Mock()
    session.sql.return_value.collect.return_value = [_Row(Id="001A", Floor_Suite__c=None)]
    with mock.patch.object(retl.requests, "post", return_value=posted), \
         mock.patch.object(retl.ingest, "send_file", side_effect=lambda a, j, data: captured.setdefault("csv", data)), \
         mock.patch.object(retl.ingest, "job_close", return_value={}), \
         mock.patch.object(retl.ingest, "job_status", return_value={"id": "750y", "state": "JobComplete"}), \
         mock.patch.object(retl, "_log_job"):
        retl.update(session, {"access_token": "t", "instance_url": "https://x"}, "Account",
                    "SELECT 1", clear_nulls=True)
    assert captured["csv"].strip().splitlines()[1] == "001A,#N/A"


def test_clear_nulls_leaves_a_blank_match_field_blank_so_the_row_is_created():
    # Upserting on Id, a new record has no Id. '#N/A' there would be an invalid Id and fail the
    # row; only an empty cell means "create". Every other NULL still clears its field.
    rows = [_Row(Id=None, Name="New", Floor_Suite__c=None),
            _Row(Id="001A", Name="Old", Floor_Suite__c=None)]
    sent = []
    posted = mock.Mock(status_code=200, json=mock.Mock(return_value={"id": "750z"}))
    with mock.patch.object(retl.requests, "post", return_value=posted), \
         mock.patch.object(retl.ingest, "send_file", side_effect=lambda a, j, data: sent.append(data)), \
         mock.patch.object(retl.ingest, "job_close", return_value={}), \
         mock.patch.object(retl.ingest, "job_status", return_value={"id": "750z", "state": "JobComplete"}), \
         mock.patch.object(retl, "_log_job"):
        session = mock.Mock()
        session.sql.return_value.collect.return_value = rows
        retl.upsert(session, {"access_token": "t", "instance_url": "https://x"}, "Account",
                    "SELECT 1", "Id", clear_nulls=True)
    lines = sent[0].strip().splitlines()
    assert lines[1] == ",New,#N/A"
    assert lines[2] == "001A,Old,#N/A"
