from pathlib import Path
from datetime import datetime, timedelta

# --- DIRETÓRIOS ---
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # Dados brutos das APIs
PROCESSED_DIR = DATA_DIR / "processed"  # Dados processados
OUTPUT_DIR = BASE_DIR / "output"  # Relatórios/exportações

# --- DATAS CONFIGURÁVEIS --- 
# (Pode ser ajustado para buscar automaticamente o último mês)
DATA_RANGES = {
    "default": {
        "start": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),  # Últimos 30 dias
        "end": datetime.now().strftime("%Y-%m-%d"),
        "time_interval": 5  # Dias entre cenas (evita sobreposição)
    },
    "monitoramento_dengue": {
        "start": "2024-01-01",  # Temporada de dengue
        "end": "2024-07-31",
        "time_interval": 7  # Semanal
    }
}

# --- FONTES DE DADOS ---
DATA_SOURCES = {
    "sentinel1": {
        "collection": "SENTINEL1_IW",
        "bands": ["VV", "VH"],
        "resolucao": 10,  # metros
        "max_cloud_cover": None  # Não aplicável
    },
    "sentinel2": {
        "collection": "SENTINEL2_L2A",
        "bands": ["B02", "B03", "B04", "B08", "B11"],  # RGB + NIR + SWIR
        "resolucao": 10,
        "max_cloud_cover": 0.2  # %
    },
    "copernicus_climate": {
        "dataset": "ERA5_LAND",
        "variaveis": ["temperature_2m", "total_precipitation"],
        "resolucao": 0.1  # graus
    }
}

# --- ÁREA DE ESTUDO ---
STUDY_AREA = {
    "name": "Barão Geraldo, Campinas",
    "bbox": [-47.10, -22.85, -47.03, -22.78],  # [min_lon, min_lat, max_lon, max_lat]
    "crs": "EPSG:4326",  # WGS84
    "tile_size": 512  # pixels
}

# --- DETECÇÃO DE FOCOS ---
DENGUE_PARAMS = {
    "ndwi_threshold": 0.2,  # Índice Água
    "min_water_area": 50,  # m² (áreas muito pequenas são ruído)
    "risk_zones": {
        "baixo": {"distancia": 500, "peso": 1},  # metros
        "medio": {"distancia": 300, "peso": 2},
        "alto": {"distancia": 100, "peso": 3}
    }
}

# --- NOMES DE ARQUIVOS ---
FILE_NAMES = {
    "sentinel1": "s1_{date}.tiff",
    "sentinel2": "s2_{date}.tiff",
    "s1_preview": "s1_preview_{date}.png",
    "s2_preview": "s2_preview_{date}.png",
    "climate_data": "era5_{var}_{date}.nc"
}

# --- AUTENTICAÇÃO ---
AUTH = {
    "copernicus": {
        "token_url": "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        "base_url": "https://sh.dataspace.copernicus.eu"
    }
}