# config/settings.py
"""
Arquivo de configuração central para o projeto NAIÁ.

Contém todas as variáveis globais, como credenciais, parâmetros da área de estudo
e intervalos de datas para análise.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Carrega variáveis de ambiente do arquivo .env na raiz do projeto
# Isso garante que as credenciais fiquem seguras e fora do código
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

# --- Credenciais de API ---
# Lendo os nomes de variáveis que o seu script original usava
SH_CLIENT_ID = os.getenv('CLIENT_ID')
SH_CLIENT_SECRET = os.getenv('CLIENT_SECRET_ID')

# --- Parâmetros da Área de Estudo ---
STUDY_AREA = {
    "name": "Barao_Geraldo_Campinas",
    # CORREÇÃO CRÍTICA: Coordenadas estavam invertidas!
    # Formato correto: [min_lon, min_lat, max_lon, max_lat]
    # Barão Geraldo está em: lat ~-22.81, lon ~-47.07
    "bbox": [-47.11, -22.85, -47.03, -22.77], # [min_lon, min_lat, max_lon, max_lat] - CORRIGIDO
    "crs": "EPSG:4326",
    "tile_size": 512
}

# --- Intervalos de Tempo para Análise ---
# Permite ter múltiplas configurações de data para diferentes análises
DATA_RANGES = {
    "monitoramento_dengue": {
        "start": "2024-07-01",
        "end": "2024-07-30",
        "description": "Período de alta sazonalidade para monitoramento."
    },
    "validacao_historica": {
        "start": "2023-01-15",
        "end": "2023-02-15",
        "description": "Dados para validar o modelo com casos passados."
    }
}

# --- Parâmetros do Modelo de Machine Learning ---
MODEL_PARAMS = {
    "test_size": 0.2,
    "random_state": 42,
    "epochs": 50
}