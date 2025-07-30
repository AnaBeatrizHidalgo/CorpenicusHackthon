#!/usr/bin/env python3
import sys
import logging
from pathlib import Path

# Adicionar src ao path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from main import run_naia_pipeline

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_naia_pipeline()