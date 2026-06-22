#!/usr/bin/env python3
"""
StarVoyage AI Video Engine — CLI entry point.

Allows running via ``python -m src`` (or ``python src/__main__.py``).
"""

import sys
from src.cli import main

sys.exit(main())
