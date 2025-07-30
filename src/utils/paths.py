"""
Módulo para gerenciar a estrutura de diretórios do projeto NAIÁ.

Define todos os caminhos necessários para dados brutos, processados, modelos
e saídas. Inclui uma função para criar esses diretórios, garantindo que a
estrutura esteja pronta para a execução do pipeline.
"""
from pathlib import Path
import logging

# --- Definição dos Caminhos Base ---

# BASE_DIR aponta para a raiz do projeto (naia-dengue/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Diretórios Principais ---
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"
CONFIG_DIR = BASE_DIR / "config"
NOTEBOOKS_DIR = BASE_DIR / "notebooks"
SRC_DIR = BASE_DIR / "src"

# --- Subdiretórios de 'data' ---
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# --- Subdiretórios de 'data/raw' (Dados Brutos) ---
RAW_SENTINEL_DIR = RAW_DIR / "sentinel"
RAW_CLIMATE_DIR = RAW_DIR / "climate"
RAW_GEODATA_DIR = RAW_DIR / "geodata"

# --- Subdiretórios de 'data/processed' (Dados Processados) ---
PROCESSED_IMAGES_DIR = PROCESSED_DIR / "images"

# --- Subdiretórios de 'output' (Resultados Finais) ---
OUTPUT_MAPS_DIR = OUTPUT_DIR / "maps"
OUTPUT_REPORTS_DIR = OUTPUT_DIR / "reports"


# --- Lista de todos os diretórios a serem criados ---
PROJECT_DIRS = [
    DATA_DIR,
    OUTPUT_DIR,
    MODELS_DIR,
    NOTEBOOKS_DIR,
    RAW_DIR,
    PROCESSED_DIR,
    RAW_SENTINEL_DIR,
    RAW_CLIMATE_DIR,
    RAW_GEODATA_DIR,
    PROCESSED_IMAGES_DIR,
    OUTPUT_MAPS_DIR,
    OUTPUT_REPORTS_DIR
]


def create_project_dirs():
    """
    Cria todos os diretórios definidos para o projeto, se ainda não existirem.

    Esta função deve ser chamada no início do pipeline principal (main.py)
    para garantir que toda a estrutura de pastas necessária esteja presente.
    """
    logging.info("Verificando e criando a estrutura de diretórios do projeto...")
    try:
        for path in PROJECT_DIRS:
            path.mkdir(parents=True, exist_ok=True)
        logging.info("Estrutura de diretórios criada com sucesso.")
    except OSError as e:
        logging.error(f"Erro ao criar o diretório: {e}")
        raise

if __name__ == '__main__':
    # Este bloco permite executar o script diretamente para criar as pastas
    # Exemplo de uso: python -m src.utils.paths
    logging.basicConfig(level=logging.INFO)
    create_project_dirs()
    print("Todos os diretórios do projeto foram verificados/criados.")
    print(f"Diretório Raiz: {BASE_DIR}")