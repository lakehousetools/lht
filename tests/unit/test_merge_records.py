"""lht merge: pairs are validated and grouped the way Salesforce's merge() requires, and results map back."""

import re
from unittest import mock

import pytest

from lht.salesforce import merge as m

A = "001000000000001AAA"
B = "001000000000002AAA"
C = "001000000000003AAA"
D = "001000000000004AAA"
E = "001000000000005AAA"


def _rows(*pairs):
    return [{"MasterId": master, "LoserId": loser} for master, loser in pairs]


def test_losers_are_grouped_by_master_at_most_two_per_request():
    plan = m.plan_requests(_rows((A, B), (A, C), (A, D), (E, "001000000000006AAA")))
    assert plan == [(A, [B, C]), (A, [D]), (E, ["001000000000006AAA"])]


def test_column_names_are_case_insensitive():
    assert m.plan_requests([{"MASTERID": A, "loserid": B}]) == [(A, [B])]


@pytest.mark.parametrize("pairs, message", [
    (((A, A),), "into itself"),
    (((A, B), (C, B)), "more than once"),
    (((A, B), (B, C)), "both a master and a loser"),
    (((A, "not-an-id"),), "not a Salesforce Id"),
    (((A, None),), "both required"),
])
def test_ambiguous_pairs_are_refused(pairs, message):
    with pytest.raises(m.MergeInputError, match=message):
        m.plan_requests(_rows(*pairs))


def test_a_15_character_id_matches_its_18_character_form():
    with pytest.raises(m.MergeInputError, match="into itself"):
        m.plan_requests(_rows((A, A[:15])))


def test_envelope_sends_only_type_and_id_for_the_master_and_escapes_the_token():
    xml = m.soap_envelope("tok<&>", "Account", [(A, [B, C])])
    assert "<urn:sessionId>tok&lt;&amp;&gt;</urn:sessionId>" in xml
    assert f"<urn:masterRecord><urn1:type>Account</urn1:type><urn1:Id>{A}</urn1:Id></urn:masterRecord>" in xml
    assert xml.count("<urn:recordToMergeIds>") == 2


def test_object_name_is_validated():
    with pytest.raises(m.MergeInputError):
        m.soap_envelope("t", "Account</urn1:type>", [(A, [B])])


def _response(results):
    body = "".join(
        "<result>"
        + "".join(f"<errors><message>{msg}</message><statusCode>{code}</statusCode></errors>" for code, msg in r.get("errors", []))
        + f"<id>{r['id']}</id>"
        + "".join(f"<mergedRecordIds>{i}</mergedRecordIds>" for i in r.get("merged", []))
        + f"<success>{'true' if r['ok'] else 'false'}</success></result>"
        for r in results
    )
    return ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns="urn:partner.soap.sforce.com"><soapenv:Body><mergeResponse>'
            f"{body}</mergeResponse></soapenv:Body></soapenv:Envelope>")


def test_results_map_back_to_requests_in_order():
    plan = [(A, [B]), (C, [D])]
    parsed = m.parse_response(_response([
        {"id": A, "ok": True, "merged": [B]},
        {"id": C, "ok": False, "errors": [("ENTITY_IS_DELETED", "entity is deleted")]},
    ]), plan)
    assert parsed[0]["success"] and parsed[0]["merged_ids"] == [B]
    assert not parsed[1]["success"] and parsed[1]["errors"] == ["ENTITY_IS_DELETED: entity is deleted"]


def test_a_soap_fault_is_raised():
    fault = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
             "<soapenv:Fault><faultcode>sf:INVALID_SESSION_ID</faultcode><faultstring>Invalid Session ID</faultstring>"
             "</soapenv:Fault></soapenv:Body></soapenv:Envelope>")
    with pytest.raises(RuntimeError, match="Invalid Session ID"):
        m.parse_response(fault, [(A, [B])])


class _Row(dict):
    def asDict(self):
        return dict(self)


def _session(rows):
    session = mock.Mock()
    session.sql.return_value.collect.return_value = [_Row(r) for r in rows]
    return session


def test_dry_run_sends_nothing():
    with mock.patch.object(m.requests, "post") as post:
        summary = m.merge(_session(_rows((A, B), (A, C), (A, D))), {"access_token": "t", "instance_url": "https://x"},
                          "Account", "SELECT 1", dry_run=True)
    post.assert_not_called()
    assert summary["requests"] == 2 and summary["records_to_merge"] == 3


def test_requests_are_split_into_calls_of_at_most_200():
    # Distinct in the first 15 characters: the last 3 of an 18-character Id are only a checksum, so
    # Ids that differ there alone are the same record.
    masters = [f"001M{n:011d}AAA" for n in range(1, 202)]
    losers = [f"001L{n:011d}AAA" for n in range(1, 202)]
    calls = []

    def fake_post(url, data, headers, timeout):
        text = data.decode("utf-8")
        calls.append(text)
        ids = re.findall(r"<urn1:Id>([^<]+)</urn1:Id>", text)
        merged = re.findall(r"<urn:recordToMergeIds>([^<]+)</urn:recordToMergeIds>", text)
        return mock.Mock(text=_response([{"id": i, "ok": True, "merged": [l]} for i, l in zip(ids, merged)]))

    with mock.patch.object(m.requests, "post", side_effect=fake_post):
        summary = m.merge(_session(_rows(*zip(masters, losers))),
                          {"access_token": "t", "instance_url": "https://x"}, "Account", "SELECT 1")
    assert len(calls) == 2
    assert calls[0].count("<urn:request>") == 200 and calls[1].count("<urn:request>") == 1
    assert summary["merged"] == 201 and summary["failed"] == []
