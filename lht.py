#!/usr/bin/env python3
"""
LHT Command Line Interface

Main entry point for LHT CLI commands.
"""

import sys
import os

# Add the src directory to the Python path so we can import from lht
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from lht.cli import main

if __name__ == "__main__":
    sys.exit(main())

