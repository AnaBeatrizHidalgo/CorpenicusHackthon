import os
from pathlib import Path

# Diretórios base
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# Configurações de processamento
TILE_SIZE = 512
STUDY_AREA = {
    'name': 'Barão Geraldo, Campinas',
    'bbox': [-47.1, -22.85, -47.05, -22.8]
}

# Thresholds
THRESHOLDS = {
    'ndwi_min': 0.2,
    'area_min': 50,
    'area_max': 5000,
    'circularity_min': 0.3,
    'dirty_threshold': 0.6
}