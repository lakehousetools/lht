"""Shared HTTP settings for calls to Salesforce."""

# (connect, read) seconds. requests has no default timeout, so without this a
# dropped connection hangs a sync forever. The read timeout is between bytes,
# not for the whole response, so large Bulk API result pages still download.
DEFAULT_TIMEOUT = (30, 300)
