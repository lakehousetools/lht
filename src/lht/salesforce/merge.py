"""
Merge Salesforce records inside Salesforce, driven by a Snowflake SQL query.

The Bulk API cannot merge, so this uses the SOAP API's merge() call. The query returns one row per
record to merge away: "MasterId" is the record that survives, "LoserId" is merged into it.
Salesforce moves the loser's related records (activities, child records) to the master and puts
the loser in the Recycle Bin with MasterRecordId set. Only the master's type and Id are sent, so
the master keeps all of its own field values.
"""

import logging
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape

import requests

logger = logging.getLogger(__name__)

API_VERSION = "62.0"
# Salesforce limits: a merge request names the master plus at most two records to merge into it,
# and one merge() call carries at most 200 requests.
MAX_LOSERS_PER_REQUEST = 2
MAX_REQUESTS_PER_CALL = 200

_ID = re.compile(r"^[A-Za-z0-9]{15}([A-Za-z0-9]{3})?$")
_SOBJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_PARTNER = "urn:partner.soap.sforce.com"


class MergeInputError(ValueError):
    """The query returned pairs that cannot be merged as given."""


def _cell(row, name):
    for key, value in row.items():
        if key.lower() == name.lower():
            return None if value is None else str(value).strip()
    raise MergeInputError(f"query must return a {name} column")


def plan_requests(rows):
    """
    Turn (MasterId, LoserId) rows into merge requests: [(master_id, [loser_id, ...]), ...].

    Losers are grouped by master and split into requests of at most two. Refuses anything
    ambiguous rather than guessing: a missing or malformed Id, a record merged into itself, a loser
    listed twice, or a record that is both a master and a loser -- merging a record that has just
    been merged away would fail, or worse, follow the chain somewhere unintended.
    """
    losers_by_master = OrderedDict()
    seen_losers = set()
    for n, row in enumerate(rows, start=1):
        master, loser = _cell(row, "MasterId"), _cell(row, "LoserId")
        if not master or not loser:
            raise MergeInputError(f"row {n}: MasterId and LoserId are both required")
        for value in (master, loser):
            if not _ID.match(value):
                raise MergeInputError(f"row {n}: {value!r} is not a Salesforce Id")
        if master[:15] == loser[:15]:
            raise MergeInputError(f"row {n}: {master} cannot be merged into itself")
        if loser[:15] in seen_losers:
            raise MergeInputError(f"row {n}: {loser} is listed as a loser more than once")
        seen_losers.add(loser[:15])
        losers_by_master.setdefault(master, []).append(loser)

    both = {m[:15] for m in losers_by_master} & seen_losers
    if both:
        raise MergeInputError(f"{len(both)} record(s) are both a master and a loser, e.g. {sorted(both)[0]}")

    plan = []
    for master, losers in losers_by_master.items():
        for i in range(0, len(losers), MAX_LOSERS_PER_REQUEST):
            plan.append((master, losers[i:i + MAX_LOSERS_PER_REQUEST]))
    return plan


def soap_envelope(session_id, sobject, merge_requests):
    """The SOAP body for one merge() call."""
    if not _SOBJECT.match(sobject):
        raise MergeInputError(f"{sobject!r} is not a Salesforce object name")
    body = []
    for master, losers in merge_requests:
        body.append(
            "<urn:request>"
            f"<urn:masterRecord><urn1:type>{sobject}</urn1:type><urn1:Id>{master}</urn1:Id></urn:masterRecord>"
            + "".join(f"<urn:recordToMergeIds>{loser}</urn:recordToMergeIds>" for loser in losers)
            + "</urn:request>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:urn="urn:partner.soap.sforce.com" xmlns:urn1="urn:sobject.partner.soap.sforce.com">'
        f"<soapenv:Header><urn:SessionHeader><urn:sessionId>{escape(session_id)}</urn:sessionId>"
        "</urn:SessionHeader></soapenv:Header>"
        f"<soapenv:Body><urn:merge>{''.join(body)}</urn:merge></soapenv:Body>"
        "</soapenv:Envelope>"
    )


def parse_response(xml_text, merge_requests):
    """One result per request, in request order, as dicts."""
    root = ET.fromstring(xml_text)
    fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
    if fault is not None:
        raise RuntimeError(f"Salesforce merge fault: {fault.findtext('faultstring') or ET.tostring(fault, 'unicode')}")
    results = root.findall(f".//{{{_PARTNER}}}result")
    if len(results) != len(merge_requests):
        raise RuntimeError(f"expected {len(merge_requests)} merge results, got {len(results)}")
    parsed = []
    for (master, losers), result in zip(merge_requests, results):
        parsed.append({
            "master_id": master,
            "loser_ids": losers,
            "success": result.findtext(f"{{{_PARTNER}}}success") == "true",
            "merged_ids": [e.text for e in result.findall(f"{{{_PARTNER}}}mergedRecordIds")],
            "updated_related_ids": [e.text for e in result.findall(f"{{{_PARTNER}}}updatedRelatedIds")],
            "errors": [
                f"{e.findtext(f'{{{_PARTNER}}}statusCode')}: {e.findtext(f'{{{_PARTNER}}}message')}"
                for e in result.findall(f"{{{_PARTNER}}}errors")
            ],
        })
    return parsed


def merge(session, access_info, sobject, query, dry_run=False):
    """
    Read (MasterId, LoserId) pairs from Snowflake and merge them in Salesforce.

    Returns {'requests', 'records_to_merge', 'merged', 'failed', 'results'}. With dry_run nothing is
    sent to Salesforce; the plan is validated and returned.
    """
    rows = [row.asDict() for row in session.sql(query).collect()]
    plan = plan_requests(rows)
    summary = {
        "requests": len(plan),
        "records_to_merge": sum(len(losers) for _, losers in plan),
        "merged": 0,
        "failed": [],
        "results": [],
    }
    if dry_run or not plan:
        return summary

    url = f"{access_info['instance_url']}/services/Soap/u/{API_VERSION}"
    headers = {"Content-Type": "text/xml; charset=UTF-8", "SOAPAction": "merge"}
    for i in range(0, len(plan), MAX_REQUESTS_PER_CALL):
        chunk = plan[i:i + MAX_REQUESTS_PER_CALL]
        response = requests.post(url, data=soap_envelope(access_info["access_token"], sobject, chunk).encode("utf-8"),
                                 headers=headers, timeout=300)
        # A SOAP fault comes back as HTTP 500 with a Fault body; parse_response raises it legibly.
        for result in parse_response(response.text, chunk):
            summary["results"].append(result)
            if result["success"]:
                summary["merged"] += len(result["merged_ids"])
            else:
                summary["failed"].append(result)
        logger.info(f"merge call {i // MAX_REQUESTS_PER_CALL + 1}: {len(chunk)} request(s)")
    return summary
