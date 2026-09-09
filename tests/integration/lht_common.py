"""
Shared helpers for the lht live integration suite (conftest.py, test_sync_scenario.py,
discover_fields.py).

Reuses lht's own connection storage and Salesforce OAuth (lht.user.*) instead of
re-implementing auth, so it authenticates against the same connection the `lht`
CLI itself uses. Everything here talks to a real Salesforce org and a real
Snowflake warehouse -- see this directory's README before running any of it.
"""
import datetime
import json
import logging
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Optional

import requests

API_VERSION = "v62.0"
PROJECT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_DIR / "reports"
STATE_DIR = PROJECT_DIR / "state"


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

class Config:
    def __init__(self, path: Path):
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        self.sf_org: str = raw["salesforce"]["org"]
        self.database: str = raw["snowflake"]["database"]
        self.sobject: str = raw["sync"]["sobject"]
        # Uppercase by default: lht's table_creator.py used to create the table
        # via a quoted (case-preserving) identifier while intelligent_sync.py's
        # incremental-sync date lookup referenced it unquoted (case-folded to
        # uppercase by Snowflake) -- a mixed-case table name made that lookup
        # silently fail every time. table_creator.py has since been fixed to
        # uppercase everything itself, but staying all-caps here matches lht's
        # own CLI examples and avoids relying on that fix being in place.
        self.table: str = raw["sync"].get("table", self.sobject.upper())
        self.snowflake_connection: Optional[str] = raw.get("snowflake", {}).get("connection")
        self.schema_override: Optional[str] = raw.get("snowflake", {}).get("schema")


def load_config(path: str = "config.toml") -> Config:
    return Config(PROJECT_DIR / path)


def load_field_toml(sobject: str, path: Optional[str] = None) -> dict:
    p = Path(path) if path else PROJECT_DIR / f"{sobject}.toml"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run discover_fields.py first to generate it."
        )
    with open(p, "rb") as f:
        return tomllib.load(f)


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

def setup_logging(run_id: str) -> logging.Logger:
    REPORTS_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("lht.tests.integration")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(REPORTS_DIR / f"run_{run_id}.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# --------------------------------------------------------------------------
# lht connection helpers (reuse lht's own stored connections)
# --------------------------------------------------------------------------

def get_access_info(sf_org: str) -> dict:
    from lht.user.salesforce_auth import get_salesforce_access_info
    return get_salesforce_access_info(sf_org)


def resolve_snowflake_connection(explicit: Optional[str] = None) -> str:
    from lht.user.connections import get_primary_connection, load_connection, list_connections

    if explicit:
        return explicit

    name = get_primary_connection("snowflake")
    if name:
        return name

    candidates = []
    for n in list_connections():
        creds = load_connection(n) or {}
        if creds.get("connection_type", "snowflake").lower() == "snowflake":
            candidates.append(n)

    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(
        "Could not resolve a Snowflake connection: no primary set and "
        f"{len(candidates)} candidate connections found. Set one with "
        "`lht set-primary <name>` or add `connection = \"<name>\"` under "
        "[snowflake] in config.toml."
    )


def get_snowflake_session(connection_name: str):
    from lht.user.auth import create_session
    return create_session(connection_name=connection_name)


def get_snowflake_schema(connection_name: str, override: Optional[str] = None) -> str:
    if override:
        return override
    from lht.user.connections import load_connection
    creds = load_connection(connection_name) or {}
    schema = creds.get("schema")
    if not schema:
        raise RuntimeError(
            f"Snowflake connection '{connection_name}' has no default schema and "
            "none was set in config.toml under [snowflake] schema."
        )
    return schema


# --------------------------------------------------------------------------
# Salesforce REST helpers (direct calls, using access_info from lht's OAuth)
# --------------------------------------------------------------------------

def _headers(access_info: dict) -> dict:
    return {
        "Authorization": f"Bearer {access_info['access_token']}",
        "Content-Type": "application/json",
    }


def describe_sobject(access_info: dict, sobject: str) -> dict:
    url = f"{access_info['instance_url']}/services/data/{API_VERSION}/sobjects/{sobject}/describe"
    r = requests.get(url, headers=_headers(access_info))
    r.raise_for_status()
    return r.json()


def soql_query(access_info: dict, soql: str, all_rows: bool = False) -> list:
    endpoint = "queryAll" if all_rows else "query"
    url = f"{access_info['instance_url']}/services/data/{API_VERSION}/{endpoint}"
    records = []
    r = requests.get(url, headers=_headers(access_info), params={"q": soql})
    r.raise_for_status()
    data = r.json()
    records.extend(data.get("records", []))
    while not data.get("done", True):
        url = access_info["instance_url"] + data["nextRecordsUrl"]
        r = requests.get(url, headers=_headers(access_info))
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
    return records


def composite_create(access_info: dict, sobject: str, records: list[dict]) -> list[dict]:
    url = f"{access_info['instance_url']}/services/data/{API_VERSION}/composite/sobjects"
    body = {
        "allOrNone": False,
        "records": [{"attributes": {"type": sobject}, **rec} for rec in records],
    }
    r = requests.post(url, headers=_headers(access_info), data=json.dumps(body))
    r.raise_for_status()
    return r.json()


def composite_update(access_info: dict, sobject: str, records: list[dict]) -> list[dict]:
    """Each record dict must include 'Id'."""
    url = f"{access_info['instance_url']}/services/data/{API_VERSION}/composite/sobjects"
    body = {
        "allOrNone": False,
        "records": [{"attributes": {"type": sobject}, **rec} for rec in records],
    }
    r = requests.patch(url, headers=_headers(access_info), data=json.dumps(body))
    r.raise_for_status()
    return r.json()


def composite_delete(access_info: dict, ids: list[str]) -> list[dict]:
    """Standard delete -- moves records to the Recycle Bin (soft delete)."""
    url = f"{access_info['instance_url']}/services/data/{API_VERSION}/composite/sobjects"
    r = requests.delete(
        url, headers=_headers(access_info),
        params={"ids": ",".join(ids), "allOrNone": "false"},
    )
    r.raise_for_status()
    return r.json()


def hard_delete(access_info: dict, ids: list[str]) -> list[dict]:
    """Purges records from the Recycle Bin (permanent / hard delete)."""
    url = f"{access_info['instance_url']}/services/data/{API_VERSION}/sobjects/RecycleBin"
    r = requests.delete(
        url, headers=_headers(access_info),
        params={"ids": ",".join(ids), "allOrNone": "false"},
    )
    if r.status_code >= 300:
        return [{"success": False, "errors": [{"statusCode": r.status_code, "message": r.text}]}]
    return r.json()


def summarize_composite_result(result: list[dict]) -> tuple[list[str], list[dict]]:
    succeeded_ids, failures = [], []
    for r in result:
        if r.get("success"):
            if r.get("id"):
                succeeded_ids.append(r["id"])
        else:
            failures.append(r)
    return succeeded_ids, failures


# --------------------------------------------------------------------------
# Test-record payload building (placeholders resolved from <Sobject>.toml)
# --------------------------------------------------------------------------

def resolve_placeholders(value, n: int, run_id: str):
    if not isinstance(value, str) or "{" not in value:
        return value
    now = datetime.datetime.utcnow()
    try:
        return value.format(
            n=n,
            run_id=run_id,
            today=now.strftime("%Y-%m-%d"),
            now=now.strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
        )
    except (KeyError, IndexError):
        return value


def build_create_records(field_toml: dict, num_records: int, run_id: str) -> list[dict]:
    fields = field_toml.get("fields", {})
    default_rt_id = field_toml.get("record_types", {}).get("default_id")
    records = []
    for i in range(1, num_records + 1):
        rec = {k: resolve_placeholders(v, i, run_id) for k, v in fields.items()}
        if default_rt_id and "RecordTypeId" not in rec:
            rec["RecordTypeId"] = default_rt_id
        records.append(rec)
    return records


def build_update_payload(field_toml: dict, run_id: str) -> dict:
    update_fields = {k: v for k, v in field_toml.get("update_fields", {}).items() if not k.startswith("#")}
    return {k: resolve_placeholders(v, 0, run_id) for k, v in update_fields.items()}


# --------------------------------------------------------------------------
# Snowflake verification helpers
# --------------------------------------------------------------------------

def qualified_table(cfg: Config, schema: str) -> str:
    return f'"{cfg.database}"."{schema}"."{cfg.table}"'


def latest_rows_for_ids(session, cfg: Config, schema: str, ids: list[str]) -> dict[str, dict]:
    """
    Older lht builds INSERTed each sync batch rather than MERGE-ing, so a given
    Salesforce Id could end up with multiple rows after repeated syncs. This
    always returns the most-recently-loaded row per Id (by SYSTEMMODSTAMP,
    falling back to LASTMODIFIEDDATE), which is what "the record synced
    correctly" should mean regardless of that behavior -- see
    duplicate_id_counts() for the check that catches the behavior itself.
    """
    if not ids:
        return {}
    id_list = ",".join(f"'{i}'" for i in ids)
    table = qualified_table(cfg, schema)
    order_col = "SYSTEMMODSTAMP" if _column_exists(session, cfg, schema, "SYSTEMMODSTAMP") else "LASTMODIFIEDDATE"
    query = f"""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY ID ORDER BY {order_col} DESC NULLS LAST) AS RN
            FROM {table}
            WHERE ID IN ({id_list})
        ) WHERE RN = 1
    """
    rows = session.sql(query).collect()
    return {row["ID"]: row.asDict() for row in rows}


def duplicate_id_counts(session, cfg: Config, schema: str, ids: Optional[list[str]] = None) -> dict[str, int]:
    """
    Salesforce's Id is unique per record (18 chars, case-sensitive, globally
    unique, same field name on every standard and custom object) -- so any Id
    appearing more than once in the target table is a bug, not legitimate data.
    Restrict to `ids` to check just a known set of records, or omit for a
    whole-table scan.
    """
    table = qualified_table(cfg, schema)
    where = ""
    if ids:
        id_list = ",".join(f"'{i}'" for i in ids)
        where = f"WHERE ID IN ({id_list})"
    query = f"""
        SELECT ID, COUNT(*) AS CNT
        FROM {table}
        {where}
        GROUP BY ID
        HAVING COUNT(*) > 1
        ORDER BY CNT DESC
    """
    rows = session.sql(query).collect()
    return {row["ID"]: row["CNT"] for row in rows}


def check_no_duplicate_ids(report: "TestReport", step_name: str, session, cfg: Config, schema: str,
                            ids: list[str]) -> None:
    """Asserts (via report.check) that `ids` -- and the table as a whole -- have no duplicate Ids."""
    dupes_scoped = duplicate_id_counts(session, cfg, schema, ids=ids)
    report.check(step_name, f"no duplicate rows among the {len(ids)} test record IDs",
                 not dupes_scoped, f"duplicated: {dupes_scoped}" if dupes_scoped else "")

    dupes_all = duplicate_id_counts(session, cfg, schema)
    detail = ""
    if dupes_all:
        sample = dict(list(dupes_all.items())[:5])
        detail = f"{len(dupes_all)} id(s) duplicated table-wide (showing up to 5): {sample}"
    report.check(step_name, "no duplicate ID values anywhere in the target table", not dupes_all, detail)


def table_row_count(session, cfg: Config, schema: str) -> int:
    table = qualified_table(cfg, schema)
    result = session.sql(f"SELECT COUNT(*) AS C FROM {table}").collect()
    return result[0]["C"]


def table_id_set(session, cfg: Config, schema: str) -> set[str]:
    table = qualified_table(cfg, schema)
    rows = session.sql(f"SELECT DISTINCT ID FROM {table}").collect()
    return {row["ID"] for row in rows}


def _column_exists(session, cfg: Config, schema: str, column: str) -> bool:
    result = session.sql(
        "SELECT COUNT(*) AS C FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{cfg.table}' AND COLUMN_NAME = '{column}'"
    ).collect()
    return result[0]["C"] > 0


# --------------------------------------------------------------------------
# lht CLI wrapper (the actual "run a command to sync" step)
# --------------------------------------------------------------------------

def run_lht_sync(cfg: Config, logger: logging.Logger, force_full_sync: bool = False) -> dict:
    # Resolved relative to the interpreter actually running pytest, so this
    # picks up whatever venv/environment lht was installed into (editable
    # install of the working tree, in the normal case) rather than assuming a
    # fixed path.
    lht_bin = str(Path(sys.executable).parent / "lht")
    cmd = [
        lht_bin, "sync",
        "--sobject", cfg.sobject,
        "--table", cfg.table,
        "--database", cfg.database,
        "--salesforce", cfg.sf_org,
    ]
    if cfg.snowflake_connection:
        cmd += ["--snowflake", cfg.snowflake_connection]
    if cfg.schema_override:
        cmd += ["--schema", cfg.schema_override]
    if force_full_sync:
        cmd.append("--force-full-sync")

    logger.info(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    logger.debug(proc.stdout)
    if proc.stderr:
        logger.debug(proc.stderr)

    actual_records = None
    for line in proc.stdout.splitlines():
        if line.strip().startswith("Actual Records:"):
            try:
                actual_records = int(line.split(":", 1)[1].strip().replace(",", ""))
            except ValueError:
                pass

    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "actual_records": actual_records,
        "success": proc.returncode == 0,
    }


# --------------------------------------------------------------------------
# State persistence (tracks created test-record ids across steps/re-runs)
# --------------------------------------------------------------------------

def state_path(run_id: str) -> Path:
    STATE_DIR.mkdir(exist_ok=True)
    return STATE_DIR / f"run_{run_id}.json"


def save_state(run_id: str, data: dict) -> None:
    with open(state_path(run_id), "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_state(run_id: str) -> dict:
    with open(state_path(run_id)) as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

class TestReport:
    def __init__(self, run_id: str, cfg: Config, logger: logging.Logger):
        self.run_id = run_id
        self.cfg = cfg
        self.logger = logger
        self.steps: list[dict] = []
        self.issues: list[str] = []

    def step(self, name: str):
        return _StepContext(self, name)

    def check(self, step_name: str, description: str, passed: bool, detail: str = ""):
        icon = "PASS" if passed else "FAIL"
        self.logger.info(f"  [{icon}] {description}" + (f" -- {detail}" if detail else ""))
        for s in reversed(self.steps):
            if s["name"] == step_name:
                s["checks"].append({"description": description, "passed": passed, "detail": detail})
                if not passed:
                    s["status"] = "FAIL"
                return
        raise ValueError(f"No active step named {step_name!r}")

    def note_issue(self, text: str):
        self.issues.append(text)
        self.logger.warning(f"ISSUE: {text}")

    @property
    def all_passed(self) -> bool:
        return all(s["status"] == "PASS" for s in self.steps)

    def status_of(self, step_name: str) -> str:
        for s in reversed(self.steps):
            if s["name"] == step_name:
                return s["status"]
        raise ValueError(f"No step named {step_name!r}")

    def render_markdown(self) -> Path:
        REPORTS_DIR.mkdir(exist_ok=True)
        path = REPORTS_DIR / f"lht_test_report_{self.run_id}.md"
        lines = [
            f"# lht Integration Test Report -- {self.run_id}",
            "",
            f"- Salesforce org: `{self.cfg.sf_org}`",
            f"- Snowflake database: `{self.cfg.database}`",
            f"- SObject / table: `{self.cfg.sobject}` -> `{self.cfg.table}`",
            f"- Overall result: **{'PASS' if self.all_passed else 'FAIL'}**",
            "",
            "## Steps",
            "",
        ]
        for s in self.steps:
            duration = s.get("duration_seconds")
            dur_str = f"{duration:.1f}s" if duration is not None else "n/a"
            lines.append(f"### {s['status']} -- {s['name']} ({dur_str})")
            if s.get("error"):
                lines.append(f"- **Error:** `{s['error']}`")
            for c in s["checks"]:
                icon = "PASS" if c["passed"] else "FAIL"
                lines.append(f"- [{icon}] {c['description']}" + (f" -- {c['detail']}" if c["detail"] else ""))
            lines.append("")

        if self.issues:
            lines.append("## Issues found")
            lines.append("")
            for issue in self.issues:
                lines.append(f"- {issue}")
            lines.append("")

        path.write_text("\n".join(lines))

        json_path = REPORTS_DIR / f"lht_test_report_{self.run_id}.json"
        json_path.write_text(json.dumps({
            "run_id": self.run_id,
            "config": {"sf_org": self.cfg.sf_org, "database": self.cfg.database,
                       "sobject": self.cfg.sobject, "table": self.cfg.table},
            "all_passed": self.all_passed,
            "steps": self.steps,
            "issues": self.issues,
        }, indent=2, default=str))

        return path


class _StepContext:
    def __init__(self, report: TestReport, name: str):
        self.report = report
        self.name = name
        self.record = {"name": name, "status": "PASS", "checks": [], "error": None}

    def __enter__(self):
        self.report.logger.info(f"\n=== {self.name} ===")
        self.record["started_at"] = time.time()
        self.report.steps.append(self.record)
        return self.report

    def __exit__(self, exc_type, exc, tb):
        self.record["duration_seconds"] = time.time() - self.record["started_at"]
        if exc is not None:
            self.record["status"] = "FAIL"
            self.record["error"] = f"{exc_type.__name__}: {exc}"
            self.report.logger.error(f"  [FAIL] {self.name} raised {exc_type.__name__}: {exc}")
            return True  # swallow -- caller continues to next step
        return False


def now_run_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
