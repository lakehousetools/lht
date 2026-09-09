"""Exception types raised by LHT.

Library code should raise one of these instead of calling exit()/sys.exit(),
so that applications embedding LHT can catch and handle failures themselves.
"""


class LHTError(Exception):
    """Base class for all LHT errors."""


class SalesforceAuthError(LHTError):
    """Raised when a Salesforce request fails due to an invalid/expired session."""


class SalesforceAPIError(LHTError):
    """Raised when a Salesforce API call fails for a reason other than auth."""


class UnknownFieldTypeError(LHTError):
    """Raised when a Salesforce field type has no known Snowflake/pandas mapping."""
