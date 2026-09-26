# Security Policy

## Supported versions

Security fixes go into the latest release on [PyPI](https://pypi.org/project/lht/). Upgrade with `pip install --upgrade lht`.

## Reporting a vulnerability

**Don't open a public issue for a security problem.** Report it privately through GitHub's [private vulnerability reporting](https://github.com/lakehousetools/lht/security/advisories/new), or email **dan@lakehousetools.com** with "lht security" in the subject.

Please include the affected version, steps to reproduce, and the impact you expect. You'll get an acknowledgement within 3 business days. We'll agree a disclosure date with you once a fix is available.

## How lht handles credentials

- Saved connections live in `~/.solomo/connections.toml`. lht creates the directory with mode `0700` and writes the file and copied private keys with mode `0600`.
- Salesforce client secrets are sent only in the POST body of the OAuth token request, never in a URL. They are never printed or logged.
- lht supports passing credentials directly from a secret manager, so no local file is needed.
- All Salesforce HTTP calls use TLS with certificate verification and a timeout.
- Database, schema and table names are validated before they're formatted into SQL.

If you think a Salesforce client secret was exposed, for example in shell history, logs or an older lht version that put credentials in the token URL, rotate it in Salesforce.
