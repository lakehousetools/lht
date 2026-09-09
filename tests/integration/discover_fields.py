#!/usr/bin/env python3
"""
Query the org (describe + a sample of real records) to figure out:
  - which Record Type Ids are valid/active for the sobject in config.toml
  - a reasonable set of fields to populate when creating test records, with
    sample values (picklist values pulled from the object's own active
    picklist, lookups reused from real records, etc.)

Writes/overwrites <Sobject>.toml, which test_sync_scenario.py then reads to
build the test records for the create step. Not a pytest test itself -- run
it by hand once (or whenever the sobject's schema changes) before running the
integration suite.

Usage (from this directory, with the project's venv active):
    python discover_fields.py [--sample-size 25] [--max-fields 15]
"""
import argparse
from pathlib import Path
from typing import Optional

import lht_common as C

SKIP_TYPES = {"address", "location", "base64", "complexvalue", "anyType"}
SKIP_FIELDS = {
    "Id", "IsDeleted", "CreatedDate", "CreatedById", "LastModifiedDate",
    "LastModifiedById", "SystemModstamp", "LastActivityDate", "LastViewedDate",
    "LastReferencedDate",
}


def toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return f'"{toml_escape(str(v))}"'


def pick_active_record_type(describe: dict) -> tuple[Optional[dict], list[dict]]:
    infos = describe.get("recordTypeInfos", [])
    active_non_master = [i for i in infos if i.get("active") and not i.get("master")]
    default = next((i for i in active_non_master if i.get("defaultRecordTypeMapping")), None)
    if default is None and active_non_master:
        default = active_non_master[0]
    return default, active_non_master


def sample_records(access_info: dict, sobject: str, field_names: list[str], sample_size: int) -> list[dict]:
    fields_clause = ", ".join(field_names[:40])  # keep the SOQL URL reasonably short
    soql = f"SELECT {fields_clause} FROM {sobject} ORDER BY CreatedDate DESC LIMIT {sample_size}"
    try:
        return C.soql_query(access_info, soql)
    except Exception as e:
        print(f"Warning: sample query failed ({e}); continuing with describe metadata only.")
        return []


def build_sample_value(field: dict, samples: list[dict], is_name_field: bool) -> Optional[object]:
    ftype = field["type"]
    name = field["name"]

    observed = [r[name] for r in samples if r.get(name) not in (None, "")]

    if ftype in SKIP_TYPES:
        return None

    if is_name_field:
        return "LHT Test {n} {run_id}"

    if ftype == "boolean":
        if observed:
            return max(set(observed), key=observed.count)
        return False

    if ftype in ("picklist",):
        active_values = [pv["value"] for pv in field.get("picklistValues", []) if pv.get("active")]
        for val in observed:
            if val in active_values:
                return val
        return active_values[0] if active_values else None

    if ftype == "multipicklist":
        active_values = [pv["value"] for pv in field.get("picklistValues", []) if pv.get("active")]
        return active_values[0] if active_values else None

    if ftype == "email":
        return "lht.test.{n}.{run_id}@example.com"

    if ftype in ("double", "currency", "percent"):
        return 100
    if ftype == "int":
        return 1

    if ftype == "date":
        return "{today}"
    if ftype == "datetime":
        return "{now}"

    if ftype == "reference":
        if name == "RecordTypeId":
            return None  # handled separately via [record_types]
        if observed:
            return observed[0]
        return None  # skip unset lookups rather than guessing an Id

    if ftype in ("string", "textarea", "phone", "url"):
        if observed:
            return observed[0]
        return "LHT Test {n} {run_id}"

    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-size", type=int, default=25)
    ap.add_argument("--max-fields", type=int, default=15, help="cap on optional (non-required) fields included")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()

    cfg = C.load_config(args.config)
    sobject = cfg.sobject

    print(f"Authenticating to Salesforce org '{cfg.sf_org}'...")
    access_info = C.get_access_info(cfg.sf_org)

    print(f"Describing {sobject}...")
    describe = C.describe_sobject(access_info, sobject)

    name_field = None
    for f in describe["fields"]:
        if f["name"] == "Name" or (f.get("nameField") and f["name"] not in SKIP_FIELDS):
            name_field = f["name"]
            break

    default_rt, active_rts = pick_active_record_type(describe)
    if default_rt:
        print(f"Found {len(active_rts)} active record type(s); default: {default_rt['name']} ({default_rt['recordTypeId']})")
    else:
        print("No non-master record types found (or record types not used for this object).")

    creatable_fields = [
        f for f in describe["fields"]
        if f.get("createable") and f["name"] not in SKIP_FIELDS and f["type"] not in SKIP_TYPES
    ]
    field_names_for_sample = [f["name"] for f in creatable_fields]
    if name_field and name_field not in field_names_for_sample:
        field_names_for_sample.insert(0, name_field)

    print(f"Sampling up to {args.sample_size} existing {sobject} records to learn realistic field usage...")
    samples = sample_records(access_info, sobject, field_names_for_sample, args.sample_size)
    print(f"Sampled {len(samples)} record(s).")

    required_fields = [f for f in creatable_fields if not f.get("nillable") and not f.get("defaultedOnCreate")]
    optional_fields = [f for f in creatable_fields if f not in required_fields]

    # Rank optional fields by how often they're actually populated in the sample.
    def populated_ratio(f):
        if not samples:
            return 0.0
        vals = [r.get(f["name"]) for r in samples]
        return sum(1 for v in vals if v not in (None, "")) / len(samples)

    optional_fields.sort(key=populated_ratio, reverse=True)
    chosen_optional = [f for f in optional_fields if populated_ratio(f) >= 0.5][: args.max_fields]

    selected_fields = required_fields + chosen_optional

    field_values = {}
    for f in selected_fields:
        val = build_sample_value(f, samples, is_name_field=(f["name"] == name_field))
        if val is not None:
            field_values[f["name"]] = val

    out_path = Path(__file__).resolve().parent / f"{sobject}.toml"
    lines = [
        f"# Auto-generated by discover_fields.py for sobject '{sobject}'.",
        "# Placeholders resolved at record-creation time: {n} (record index), {run_id}, {today}, {now}.",
        "# Edit freely -- re-running discover_fields.py will overwrite this file.",
        "",
        "[record_types]",
    ]
    if default_rt:
        lines.append(f"default_id = {toml_value(default_rt['recordTypeId'])}")
        lines.append(f"default_name = {toml_value(default_rt['name'])}")
    else:
        lines.append("# No non-master record types found; RecordTypeId is left unset.")
    for rt in active_rts:
        lines.append("")
        lines.append("[[record_types.available]]")
        lines.append(f"id = {toml_value(rt['recordTypeId'])}")
        lines.append(f"name = {toml_value(rt['name'])}")

    lines += ["", "[fields]"]
    for k, v in field_values.items():
        lines.append(f"{k} = {toml_value(v)}")

    lines += [
        "",
        "[update_fields]",
        "# Applied to all test records during the update-scenario step.",
    ]
    desc_field = next((f for f in creatable_fields if f["name"] == "Description"), None)
    if desc_field:
        lines.append('Description = "Updated by lht test harness on {now}"')
    else:
        first_updatable_string = next(
            (f["name"] for f in creatable_fields if f["type"] in ("string", "textarea") and f["name"] != name_field),
            None,
        )
        if first_updatable_string:
            lines.append(f'{first_updatable_string} = "Updated by lht test harness on {{now}}"')
        else:
            lines.append("# No obvious text field found to update -- add one manually, e.g.:")
            lines.append('# SomeField__c = "Updated by lht test harness on {now}"')

    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {out_path}")
    print(f"  Required fields included: {len(required_fields)}")
    print(f"  Optional fields included: {len(chosen_optional)} (of {len(optional_fields)} candidates)")
    if not field_values:
        print("  WARNING: no fields were populated -- review the file before running the test suite.")


if __name__ == "__main__":
    main()
