"""Allows `python -m lht ...` as an alternative to the `lht` command."""

import sys

from lht.cli import main

sys.exit(main())
