"""
The `lht` command must start without the Snowflake client installed.

Snowpark is an optional extra, and on Databricks -- or anywhere only
`pip install "lht[databricks]"` was run -- it is absent. The entry point imports
every command's module before it parses an argument, so one module importing
Snowpark at the top used to crash the whole CLI, `lht retl --databricks`
included. The library-level guard in test_databricks.py did not see this: it
imports the reverse-ETL modules, not the CLI.

These run in a subprocess with `snowflake.*` made unimportable, because the
failure is at import time.
"""

import subprocess
import sys

import pytest

_BLOCK_SNOWPARK = '''
import sys
from importlib.abc import MetaPathFinder


class Blocked(MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] == 'snowflake':
            raise ImportError("blocked for this test: " + name, name=name)
        return None


sys.meta_path.insert(0, Blocked())
from lht.cli import main
'''

SUBCOMMANDS = [
    'create-connection', 'list-connections', 'edit-connection', 'set-primary', 'connect',
    'sync', 'retl', 'merge', 'list-jobs', 'show-job', 'get-job-results', 'delete-job',
]


def _run(call):
    return subprocess.run([sys.executable, '-c', _BLOCK_SNOWPARK + call],
                          capture_output=True, text=True)


def test_the_cli_imports_without_snowpark():
    result = _run('')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('command', SUBCOMMANDS)
def test_every_subcommand_shows_its_help_without_snowpark(command):
    result = _run(f'main([{command!r}, "--help"])')
    # argparse exits 0 after printing help.
    assert result.returncode == 0, result.stderr
    assert 'usage:' in result.stdout


def test_the_databricks_flag_is_reachable_without_snowpark():
    result = _run('main(["retl", "--help"])')
    assert result.returncode == 0, result.stderr
    assert '--databricks' in result.stdout


def test_lht_sync_without_snowpark_says_what_to_install():
    # Sync is Snowflake-only, so it genuinely needs the client. It must say so,
    # before connecting to anything, rather than failing on an import.
    result = _run('raise SystemExit(main(["sync", "--sobject", "Account", "--table", "ACCOUNT"]))')
    assert result.returncode == 1
    assert 'lht[snowflake]' in result.stdout
    assert 'Traceback' not in result.stderr
