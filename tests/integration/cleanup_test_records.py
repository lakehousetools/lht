#!/usr/bin/env python3
"""
Hard-deletes any test records left over from a previous integration-suite run
(e.g. one that failed before step 9, or was run with --keep-test-records).

Not a pytest test -- an imperative cleanup you run by hand.

Usage (from this directory, with the project's venv active):
    python cleanup_test_records.py <run_id>

<run_id> is the timestamp printed at the start of a `pytest -m integration -v`
run (also the suffix on state/run_<run_id>.json and reports/lht_test_report_<run_id>.md).
"""
import argparse

import lht_common as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    args = ap.parse_args()

    logger = C.setup_logging(f"cleanup_{args.run_id}")
    state = C.load_state(args.run_id)
    cfg = C.load_config(state["config_path"])
    access_info = C.get_access_info(cfg.sf_org)

    ids = state.get("record_ids", [])
    if not ids:
        logger.info("No tracked record ids in state file -- nothing to clean up.")
        return

    logger.info(f"Cleaning up {len(ids)} leftover test record(s): {ids}")
    try:
        C.composite_delete(access_info, ids)
    except Exception as e:
        logger.warning(f"Soft-delete during cleanup failed (may already be deleted): {e}")

    result = C.hard_delete(access_info, ids)
    _, failures = C.summarize_composite_result(result)
    if failures:
        logger.warning(f"Hard-delete failures during cleanup: {failures}")
    else:
        logger.info("Cleanup complete.")


if __name__ == "__main__":
    main()
