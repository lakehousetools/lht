"""lht (Lakehouse Tools): Salesforce <-> Snowflake sync. Bring Your Own Data Warehouse."""

try:
    from importlib.metadata import version as _version, PackageNotFoundError
    __version__ = _version("lht")
except PackageNotFoundError:  # running from a source checkout that isn't installed
    __version__ = "0+unknown"
