"""
End-to-end lifecycle test of `lht sync` against a live Salesforce org and a
live Snowflake database, driven by config.toml and <Sobject>.toml (generate
the latter with `python discover_fields.py` first). See README.md in this
directory before running this file -- it authenticates for real and creates,
updates, and deletes real Salesforce records.

Excluded from a plain `pytest` run (see the `integration` marker registered in
conftest.py). Run explicitly:

    pytest -m integration -v
    pytest -m integration -v --num-records 5 --keep-test-records

Tests are numbered and run in file order (pytest's default), each depending
on state left by the ones before it (created record ids, the pre-test
baseline snapshot) via the shared `scenario_state` fixture. A failure in one
step doesn't stop pytest from running the rest, same as any other test file;
steps 3 onward skip themselves (rather than reporting a misleading pass) if
step 2 didn't actually create any records.
"""
import pytest

import lht_common as C

pytestmark = pytest.mark.integration


def _require_record_ids(scenario_state) -> list[str]:
    ids = scenario_state.get("record_ids")
    if not ids:
        pytest.skip("no test records were created in step 2 -- see its failure for why")
    return ids


def test_01_baseline_complete_refresh(report, cfg, logger, snowflake_session, schema, scenario_state):
    name = "1. Baseline complete refresh"
    with report.step(name) as r:
        result = C.run_lht_sync(cfg, logger, force_full_sync=True)
        r.check(name, "lht sync --force-full-sync exited 0", result["success"],
                result["stderr"][-500:] if not result["success"] else "")
        scenario_state["baseline_count"] = C.table_row_count(snowflake_session, cfg, schema)
        scenario_state["baseline_ids"] = list(C.table_id_set(snowflake_session, cfg, schema))
        r.check(name, "captured baseline row count/id set", True, f"{scenario_state['baseline_count']} rows")
    assert report.status_of(name) == "PASS"


def test_02_create_test_records(report, cfg, access_info, field_toml, num_records, run_id, scenario_state):
    name = "2. Create test records"
    with report.step(name) as r:
        payloads = C.build_create_records(field_toml, num_records, run_id)
        result = C.composite_create(access_info, cfg.sobject, payloads)
        record_ids, failures = C.summarize_composite_result(result)
        scenario_state["record_ids"] = record_ids
        C.save_state(run_id, scenario_state)
        r.check(name, f"created {len(record_ids)}/{num_records} records",
                len(record_ids) == num_records, f"failures: {failures}" if failures else "")
    assert report.status_of(name) == "PASS"


def test_03_sync_and_verify_create(report, cfg, logger, access_info, field_toml, num_records, run_id,
                                    snowflake_session, schema, scenario_state):
    name = "3. Sync + verify create"
    record_ids = _require_record_ids(scenario_state)
    with report.step(name) as r:
        result = C.run_lht_sync(cfg, logger)
        r.check(name, "lht sync exited 0", result["success"])
        rows = C.latest_rows_for_ids(snowflake_session, cfg, schema, record_ids)
        r.check(name, f"all {len(record_ids)} created records present in Snowflake",
                len(rows) == len(record_ids), f"found {len(rows)}")
        expected = C.build_create_records(field_toml, num_records, run_id)
        for rec_id, expect in zip(record_ids, expected):
            row = rows.get(rec_id)
            if row is None:
                r.check(name, f"{rec_id} synced", False, "missing from Snowflake table")
                continue
            mismatches = []
            for field, value in expect.items():
                col = field.upper()
                if col not in row:
                    continue
                if str(row[col]) != str(value):
                    mismatches.append(f"{field}: expected={value!r} actual={row[col]!r}")
            r.check(name, f"{rec_id} fields match what was created", not mismatches, "; ".join(mismatches))
        C.check_no_duplicate_ids(r, name, snowflake_session, cfg, schema, record_ids)
    assert report.status_of(name) == "PASS"


def test_04_update_test_records(report, cfg, access_info, field_toml, run_id, scenario_state):
    name = "4. Update test records"
    record_ids = _require_record_ids(scenario_state)
    with report.step(name) as r:
        update_payload = C.build_update_payload(field_toml, run_id)
        if not update_payload:
            r.check(name, "update_fields present in <Sobject>.toml", False,
                    "no [update_fields] configured -- edit the generated TOML")
        else:
            records = [{"Id": rid, **update_payload} for rid in record_ids]
            result = C.composite_update(access_info, cfg.sobject, records)
            updated_ids, failures = C.summarize_composite_result(result)
            r.check(name, f"updated {len(updated_ids)}/{len(record_ids)} records",
                    len(updated_ids) == len(record_ids), f"failures: {failures}" if failures else "")
    assert report.status_of(name) == "PASS"


def test_05_sync_and_verify_update(report, cfg, logger, field_toml, run_id, snowflake_session, schema,
                                    scenario_state):
    name = "5. Sync + verify update"
    record_ids = _require_record_ids(scenario_state)
    with report.step(name) as r:
        result = C.run_lht_sync(cfg, logger)
        r.check(name, "lht sync exited 0", result["success"])
        rows = C.latest_rows_for_ids(snowflake_session, cfg, schema, record_ids)
        update_payload = C.build_update_payload(field_toml, run_id)
        for rec_id in record_ids:
            row = rows.get(rec_id)
            if row is None:
                r.check(name, f"{rec_id} synced", False, "missing from Snowflake table")
                continue
            mismatches = []
            for field, value in update_payload.items():
                col = field.upper()
                if col in row and str(row[col]) != str(value):
                    mismatches.append(f"{field}: expected={value!r} actual={row[col]!r}")
            r.check(name, f"{rec_id} reflects update (latest row by SYSTEMMODSTAMP)",
                    not mismatches, "; ".join(mismatches))
        C.check_no_duplicate_ids(r, name, snowflake_session, cfg, schema, record_ids)
    assert report.status_of(name) == "PASS"


def test_06_soft_delete_test_records(report, cfg, access_info, scenario_state):
    name = "6. Soft-delete test records"
    record_ids = _require_record_ids(scenario_state)
    with report.step(name) as r:
        result = C.composite_delete(access_info, record_ids)
        deleted_ids, failures = C.summarize_composite_result(result)
        r.check(name, f"soft-deleted {len(deleted_ids)}/{len(record_ids)} records",
                len(deleted_ids) == len(record_ids), f"failures: {failures}" if failures else "")
    assert report.status_of(name) == "PASS"


def test_07_sync_and_verify_soft_delete_marked(report, cfg, logger, snowflake_session, schema, scenario_state):
    name = "7. Sync + verify soft-delete marked"
    record_ids = _require_record_ids(scenario_state)
    with report.step(name) as r:
        result = C.run_lht_sync(cfg, logger)
        r.check(name, "lht sync exited 0", result["success"])
        rows = C.latest_rows_for_ids(snowflake_session, cfg, schema, record_ids)
        for rec_id in record_ids:
            row = rows.get(rec_id)
            if row is None:
                r.check(name, f"{rec_id} present in Snowflake", False, "missing -- can't check ISDELETED")
                continue
            is_deleted = row.get("ISDELETED")
            r.check(name, f"{rec_id} ISDELETED = TRUE in Snowflake",
                    bool(is_deleted) is True, f"actual={is_deleted!r}")
        C.check_no_duplicate_ids(r, name, snowflake_session, cfg, schema, record_ids)
    assert report.status_of(name) == "PASS"


def test_08_verify_soft_delete_in_salesforce(report, cfg, access_info, scenario_state):
    name = "8. Verify soft delete in Salesforce"
    record_ids = _require_record_ids(scenario_state)
    with report.step(name) as r:
        id_list = ",".join(f"'{i}'" for i in record_ids)
        sf_rows = C.soql_query(access_info, f"SELECT Id, IsDeleted FROM {cfg.sobject} WHERE Id IN ({id_list})",
                                all_rows=True)
        sf_by_id = {row["Id"]: row for row in sf_rows}
        for rec_id in record_ids:
            row = sf_by_id.get(rec_id)
            r.check(name, f"{rec_id} found via queryAll with IsDeleted=true",
                    bool(row and row.get("IsDeleted")), "" if row else "not found via queryAll")
    assert report.status_of(name) == "PASS"


def test_09_hard_delete_test_records(report, cfg, access_info, keep_test_records, scenario_state):
    if keep_test_records:
        pytest.skip("--keep-test-records set")
    name = "9. Hard-delete test records"
    record_ids = _require_record_ids(scenario_state)
    with report.step(name) as r:
        result = C.hard_delete(access_info, record_ids)
        purged_ids, failures = C.summarize_composite_result(result)
        r.check(name, f"purged {len(purged_ids)}/{len(record_ids)} records",
                len(purged_ids) == len(record_ids), f"failures: {failures}" if failures else "")
        if failures:
            report.note_issue(
                "Hard-delete (DELETE /sobjects/RecycleBin) failed for some records -- this "
                "endpoint requires the 'Hard Delete' permission; if the running user/connected "
                f"app doesn't have it, purge these ids manually: {[f.get('id') for f in failures]}"
            )
    assert report.status_of(name) == "PASS"


def test_10_full_sync_and_verify_back_to_baseline(report, cfg, logger, keep_test_records, snowflake_session,
                                                   schema, scenario_state):
    if keep_test_records:
        pytest.skip("--keep-test-records set")
    name = "10. Full sync + verify back to baseline"
    record_ids = _require_record_ids(scenario_state)
    baseline_count = scenario_state.get("baseline_count")
    with report.step(name) as r:
        result = C.run_lht_sync(cfg, logger, force_full_sync=True)
        r.check(name, "lht sync --force-full-sync exited 0", result["success"])
        final_ids = C.table_id_set(snowflake_session, cfg, schema)
        final_count = C.table_row_count(snowflake_session, cfg, schema)
        leftover = set(record_ids) & final_ids
        r.check(name, "no test record ids remain in Snowflake", not leftover,
                f"leftover: {leftover}" if leftover else "")
        r.check(name, f"row count matches baseline ({baseline_count})", final_count == baseline_count,
                f"baseline={baseline_count} final={final_count} "
                "(a mismatch here can also mean other users changed data in the org "
                "during the test run, not necessarily a sync bug)")
        C.check_no_duplicate_ids(r, name, snowflake_session, cfg, schema, record_ids)
    assert report.status_of(name) == "PASS"
