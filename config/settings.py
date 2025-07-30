# config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (crie este arquivo na raiz do projeto)
load_dotenv()

# --- Credenciais ---
SH_CLIENT_ID = os.getenv('SH_CLIENT_ID')
SH_CLIENT_SECRET = os.getenv('SH_CLIENT_SECRET')
EE_PROJECT = os.getenv('EE_PROJECT') # Se aplicável

# --- Estrutura de Pastas (Definida em src/utils/paths.py) ---
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"

# --- Parâmetros do Estudo ---
STUDY_AREA_BBOX = [-47.15, -22.95, -46.95, -22.75] # [min_lon, min_lat, max_lon, max_lat]
TIME_INTERVAL = ("2025-06-01", "2025-06-30")
CRS = "EPSG:4326"

# --- Fontes de Dados ---
GEODATA_PATH = RAW_DIR / "geodata/setores_barao.geojson"

# --- Parâmetros do Modelo ---
MODEL_PARAMS = {
    "test_size": 0.2,
    "random_state": 42,
    "epochs": 50,
}