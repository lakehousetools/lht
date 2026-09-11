"""Bulk API CSV responses are UTF-8 whatever requests guesses.

Salesforce sends `Content-Type: text/csv` with no charset, so requests decodes `.text` as
ISO-8859-1 and every multi-byte character arrives as mojibake. Found 2026-09-11 when a practice
named 'ACME CLINIC – NORTH' would come back into Snowflake as
'ACME CLINIC â\x80\x93 NORTH'.
"""

from unittest import mock

import requests

from lht.util.csv import bulk_csv_text
from lht.salesforce import results_bapi

NAME = "ACME CLINIC – NORTH"


def _csv_response(body: str, *, bom: bool = False) -> requests.Response:
    r = requests.Response()
    r.status_code = 200
    r._content = (b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8")
    r.headers["Content-Type"] = "text/csv"    # exactly what Salesforce sends: no charset
    # What HTTPAdapter.build_response does to every real response.
    r.encoding = requests.utils.get_encoding_from_headers(r.headers)
    return r


def test_requests_alone_gets_it_wrong():
    # The premise of the fix. If requests ever stops defaulting text/* to ISO-8859-1 this
    # fails, and the helper becomes merely redundant rather than wrong.
    r = _csv_response(f'Id,Name\n001,"{NAME}"\n')
    assert r.encoding == "ISO-8859-1"
    assert NAME not in r.text


def test_bulk_csv_text_decodes_utf8():
    r = _csv_response(f'Id,Name\n001,"{NAME}"\n')
    assert bulk_csv_text(r) == f'Id,Name\n001,"{NAME}"\n'


def test_bulk_csv_text_drops_a_byte_order_mark():
    r = _csv_response('Id,Name\n001,x\n', bom=True)
    assert bulk_csv_text(r).startswith("Id,")


def test_results_bapi_reads_non_ascii_correctly():
    body = f'"sf__Id","sf__Created","Name"\n"001","true","{NAME}"\n'
    with mock.patch.object(results_bapi.requests, "get", return_value=_csv_response(body)):
        rows = results_bapi.get_successful_results(
            {"access_token": "t", "instance_url": "https://example.my.salesforce.com"}, "750x")
    assert rows == [{"sf__Id": "001", "sf__Created": "true", "Name": NAME}]
