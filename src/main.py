#!/usr/bin/env python3
"""
StarVoyage AI Video Engine — CLI entry point.

Usage:
  python main.py run --topic "成都火锅的百年历史" --niche china_food --duration 180
  python main.py draft --topic "上海外滩的清晨" --niche china_city
  python main.py init-db
  python main.py list-projects
  python main.py list-niches
  python main.py check-quality output/final.mp4
"""

import sys
from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
