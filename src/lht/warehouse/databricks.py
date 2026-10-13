"""
Databricks, through a Spark session.

Two ways in, and the point of both is that the lht call in between is the same:

* In a notebook or a Databricks Job, the cluster's ``spark`` is already
  authenticated against Unity Catalog. :func:`connect` finds it.
* On a laptop, :func:`connect` falls back to Databricks Connect, which reads
  the same ``~/.databrickscfg`` profiles as the Databricks CLI. So a query
  developed locally is the query that runs in the notebook, with no local
  config file in the picture at all once it moves there.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from lht.warehouse.base import Warehouse, iso_timestamp

logger = logging.getLogger(__name__)


class DatabricksWarehouse(Warehouse):
    """
    Delta tables on Databricks SQL.

    Three choices worth stating, since they differ from the Snowflake backend:

    * Every string column is ``STRING``. Databricks accepts ``VARCHAR(n)`` but
      stores it as ``STRING`` with no length enforcement, so declaring a width
      would only suggest a constraint that isn't there.
    * No ``PRIMARY KEY``. On Databricks it needs Unity Catalog and is
      ``NOT ENFORCED`` anyway, so it would buy nothing and cost portability.
    * No column ``DEFAULT`` for CREATED_AT. That needs the Delta
      ``allowColumnDefaults`` table feature; :meth:`insert_rows` writes the
      value itself instead, which works on any runtime and on a SQL warehouse.
    """

    name = 'databricks'

    TYPES: Dict[str, str] = {
        'str': 'STRING',
        'str20': 'STRING',
        'str50': 'STRING',
        'str255': 'STRING',
        'str255_not_null': 'STRING NOT NULL',
        'text': 'STRING',
        'key': 'STRING',
        'autoincrement': 'BIGINT GENERATED ALWAYS AS IDENTITY',
        'timestamp': 'TIMESTAMP_NTZ',
        'audit_timestamp': 'TIMESTAMP',
        'int': 'BIGINT',
        'bool': 'BOOLEAN',
    }

    def literal(self, value: Any) -> str:
        """
        A value as a Spark SQL string literal, escaped with backslashes.

        Not the SQL standard's doubled quote, which Spark gets silently wrong:
        it concatenates adjacent string literals, so ``'it''s'`` parses as
        ``'it'`` followed by ``'s'`` and yields ``its`` -- the apostrophe is
        dropped, with no error. A Salesforce error message or a name like
        O'Brien would be quietly corrupted on the way into a log table.

        Backslash is escaped first and for the same reason: inside a Spark
        string literal ``\b`` is a backspace, not two characters, so a raw
        backslash has to be doubled before quotes are escaped against it.

        This assumes Spark's default `spark.sql.parser.escapedStringLiterals=false`
        (backslash escapes active), which is the default on Databricks. Under the
        legacy `true`, a quote in a value would fail to parse rather than corrupt.
        """
        if value is None:
            return 'NULL'
        escaped = str(value).replace('\\', '\\\\').replace("'", "\\'")
        return f"'{escaped}'"

    def timestamp_literal(self, value: Optional[str]) -> str:
        normalized = iso_timestamp(value)
        if normalized is None:
            return 'NULL'
        return f"CAST({self.literal(normalized)} AS TIMESTAMP_NTZ)"


def get_spark_session(profile: Optional[str] = None, **builder_options: Any) -> Any:
    """
    The Spark session to run lht's queries on.

    Order matters: a session the runtime already created is used as-is, because
    on Databricks compute it is the one holding the cluster's Unity Catalog
    credentials, and starting a second one would be both wasteful and wrong.
    Only off-platform does this reach for Databricks Connect.

    Args:
        profile: ``~/.databrickscfg`` profile for Databricks Connect. Ignored
            when a session already exists (a notebook needs no profile).
            Defaults to Databricks Connect's own resolution: ``DATABRICKS_*``
            environment variables, then the ``DEFAULT`` profile.
        **builder_options: Passed to ``DatabricksSession.builder.remote()``,
            e.g. ``cluster_id='0101-...'`` or ``serverless=True``.

    Raises:
        ImportError: Off-platform with Databricks Connect not installed.
        RuntimeError: Databricks Connect is installed but cannot be configured.
    """
    existing = _active_spark_session()
    if existing is not None:
        if profile or builder_options:
            logger.info(
                "Using the Spark session this runtime already provides; "
                "profile and builder options are ignored on Databricks compute."
            )
        logger.debug("Using the existing Spark session")
        return existing

    try:
        from databricks.connect import DatabricksSession
    except ImportError as e:
        raise ImportError(
            "No Spark session is running and Databricks Connect is not installed. "
            "In a Databricks notebook or Job, `spark` already exists and lht will "
            "find it. To run against Databricks from elsewhere, install "
            '`pip install "lht[databricks]"` and configure a profile with '
            "`databricks auth login`."
        ) from e

    options: Dict[str, Any] = dict(builder_options)
    if profile:
        options['profile'] = profile
    try:
        builder = DatabricksSession.builder
        if options:
            builder = builder.remote(**options)
        session = builder.getOrCreate()
    except Exception as e:
        raise RuntimeError(
            f"Could not start a Databricks Connect session: {e}. "
            "Databricks Connect needs a host and token (a ~/.databrickscfg profile "
            "or DATABRICKS_HOST/DATABRICKS_TOKEN) plus compute to run on "
            "(serverless=True, or cluster_id=... / DATABRICKS_CLUSTER_ID)."
        ) from e

    logger.debug("Started a Databricks Connect session")
    return session


# Where a running Spark session might be found, and how to ask. Order matters
# within each class: `active()` returns the active-or-default session, while
# `getActiveSession()` is thread-local and answers None when the session was
# created on another thread -- which a notebook cell easily is, and which would
# send connect() off to start a Databricks Connect session that isn't wanted.
# Verified against PySpark 4.0: off-thread, getActiveSession() is None where
# active() is not.
# PySpark is asked first: on Databricks compute the ambient `spark` is a PySpark
# object, and a Databricks Connect session is one too (a Spark Connect session),
# so these two cover both. DatabricksSession is only a safety net.
_SESSION_SOURCES = (
    ('pyspark.sql.connect.session', 'SparkSession'),
    ('pyspark.sql', 'SparkSession'),
    ('databricks.connect', 'DatabricksSession'),
)
_SESSION_ACCESSORS = ('active', 'getActiveSession')


def _active_spark_session() -> Optional[Any]:
    """
    The Spark session the runtime already has, or None.

    A notebook's ``spark`` is a global in the user's namespace, not something
    lht can see, so this asks Spark itself. Databricks Connect's own session
    answers the same way, which is what makes :func:`connect` behave
    identically in a notebook and on a laptop.
    """
    for module_name, attribute in _SESSION_SOURCES:
        try:
            module = __import__(module_name, fromlist=[attribute])
            session_class = getattr(module, attribute)
        except Exception:
            continue

        for accessor in _SESSION_ACCESSORS:
            try:
                session = getattr(session_class, accessor)()
            except Exception:
                # active() raises when no session exists at all.
                continue
            if session is not None:
                return session

        # Last resort: the global default, set by whoever built the session.
        session = getattr(session_class, '_instantiatedSession', None)
        if session is not None:
            return session
    return None


def connect(
    session: Optional[Any] = None,
    profile: Optional[str] = None,
    **builder_options: Any,
) -> DatabricksWarehouse:
    """
    A Databricks warehouse ready to pass to ``lht.salesforce.retl``.

    In a notebook::

        from lht.warehouse.databricks import connect
        wh = connect()                     # or connect(spark)

    From a laptop, against a profile in ``~/.databrickscfg``::

        wh = connect(profile='my-workspace', serverless=True)

    Args:
        session: An existing Spark session. Passing the notebook's ``spark``
            explicitly is equivalent to letting this find it.
        profile: ``~/.databrickscfg`` profile, for Databricks Connect only.
        **builder_options: Passed to ``DatabricksSession.builder.remote()``.
    """
    if session is None:
        session = get_spark_session(profile=profile, **builder_options)
    return DatabricksWarehouse(session)


# Secret-scope key -> the credentials key it maps to. The names match a
# connections.toml Salesforce entry, so the same credentials work either way;
# `client_secret` is accepted too, since that is what Salesforce's own UI calls
# the value people put in the scope.
_SALESFORCE_SECRET_KEYS = {
    'auth_flow': 'auth_flow',
    'client_id': 'client_id',
    'client_key': 'client_key',
    'client_secret': 'client_key',
    'my_domain': 'my_domain',
    'username': 'username',
    'private_key_pem': 'private_key_pem',
    'private_key_passphrase': 'private_key_passphrase',
    'login_url': 'login_url',
    'sandbox': 'sandbox',
}


def salesforce_access_info(
    scope: Optional[str] = None,
    connection_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Authenticate with Salesforce, from a secret scope on Databricks and from
    connections.toml off it.

    This is the one call that lets a notebook and a laptop run the same file.
    On Databricks compute the credentials come from the secret scope, where they
    belong; elsewhere -- where ``dbutils`` does not exist -- it falls back to the
    connection you already created with `lht create-connection --salesforce`.

    A failure to read a scope that *is* reachable is raised, not fallen back
    from: on a cluster, a missing key is a misconfigured scope, and quietly
    authenticating as somebody else would be worse than stopping.

    Args:
        scope: Databricks secret scope holding the credentials. Its keys are the
            ones a connections.toml Salesforce entry uses --
            ``client_id``/``client_key`` (or ``client_secret``)/``my_domain`` for
            the default client-credentials flow, or ``auth_flow='jwt_bearer'``
            with ``client_id``/``username``/``private_key_pem``.
        connection_name: Salesforce connection to use off Databricks. The
            primary one if None. ``lht.user.connections.register_connection()``
            registers one in memory, with no file on disk.

    Returns:
        ``{'access_token': ..., 'instance_url': ...}``, ready for
        ``lht.salesforce.retl``.
    """
    from lht.user.salesforce_auth import (
        get_salesforce_access_info,
        get_salesforce_access_info_from_credentials,
    )

    if scope and _dbutils() is not None:
        logger.info(f"Reading Salesforce credentials from secret scope '{scope}'")
        return get_salesforce_access_info_from_credentials(_credentials_from_scope(scope))

    if scope:
        logger.info(
            f"Not running on Databricks, so secret scope '{scope}' is unreachable; "
            "using a saved connection instead."
        )
    return get_salesforce_access_info(connection_name)


def _credentials_from_scope(scope: str) -> Dict[str, Any]:
    """Build a Salesforce credentials dict from the keys present in a scope."""
    dbutils = _dbutils()
    try:
        available = {entry.key for entry in dbutils.secrets.list(scope)}
    except Exception as e:
        # list() needs the same READ grant as get(), but don't let a surprise
        # here hide a scope that is perfectly readable key by key.
        logger.debug(f"Could not list secret scope '{scope}' ({e}); trying each key.")
        available = set(_SALESFORCE_SECRET_KEYS)

    credentials: Dict[str, Any] = {}
    for key in _SALESFORCE_SECRET_KEYS:
        if key not in available:
            continue
        try:
            value = dbutils.secrets.get(scope=scope, key=key)
        except Exception:
            continue
        if value == '':
            continue
        credentials[_SALESFORCE_SECRET_KEYS[key]] = value

    if 'sandbox' in credentials:
        credentials['sandbox'] = str(credentials['sandbox']).strip().lower() in ('true', '1', 'yes')

    if not credentials:
        raise ValueError(
            f"Secret scope '{scope}' holds none of the keys lht looks for "
            f"({', '.join(sorted(_SALESFORCE_SECRET_KEYS))}). Create them with "
            f"`databricks secrets put-secret {scope} client_id` and so on."
        )
    return credentials


def secret(scope: str, key: str) -> str:
    """
    One value from a Databricks secret scope.

    Credentials belong in a scope rather than in the notebook, and reading them
    through ``dbutils`` means they are redacted in any output. ``dbutils`` is a
    notebook global, so it is resolved at call time via the SDK rather than
    imported.

    Raises:
        RuntimeError: If ``dbutils`` is not reachable (i.e. not on Databricks).
    """
    dbutils = _dbutils()
    if dbutils is None:
        raise RuntimeError(
            f"Cannot read secret {scope}/{key}: dbutils is not available. "
            "Databricks secret scopes are readable from Databricks compute; "
            "elsewhere, read credentials from the environment or a connections.toml entry."
        )
    return dbutils.secrets.get(scope=scope, key=key)


def _dbutils() -> Optional[Any]:
    """The runtime's ``dbutils``, or None when not running on Databricks."""
    try:  # Inside a notebook, where IPython holds the injected global.
        import IPython  # type: ignore

        shell = IPython.get_ipython()
        if shell is not None and 'dbutils' in shell.user_ns:
            return shell.user_ns['dbutils']
    except Exception:
        pass
    try:  # Databricks Connect and Jobs: the SDK builds an equivalent.
        from databricks.sdk.runtime import dbutils  # type: ignore

        return dbutils
    except Exception:
        return None


def on_databricks() -> bool:
    """Whether this process is running on Databricks compute."""
    return bool(os.environ.get('DATABRICKS_RUNTIME_VERSION'))
