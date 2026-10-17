#!/usr/bin/env python3
"""Run Quanta from a source checkout:  python main.py --small"""
import sys

from quanta.cli import main

if __name__ == "__main__":
    sys.exit(main())
