# run_analysis.py
"""
Orquestrador dinâmico para o projeto NAIÁ.

Define uma área de estudo a partir de um ponto central e um tamanho,
recorta os setores censitários de um arquivo nacional e executa o
pipeline completo de análise de risco e detecção de piscinas.
"""
import logging
from pathlib import Path
import os
import pandas as pd

# --- Importações dos Módulos do Projeto ---
from src.config import settings
from src.utils import paths
from src.utils.geoprocessing import create_study_area_geojson
from src.models.pool_detector import find_pools_in_sectors
# (Adicione aqui os imports para os outros módulos quando for integrá-los)

# --- 1. PARÂMETROS DA ANÁLISE (O que você irá mudar) ---
# --------------------------------------------------------
# Defina o centro da sua nova área de estudo
CENTER_LAT = -22.818
CENTER_LON = -47.069

# Defina o tamanho da caixa de análise em quilômetros
AREA_SIZE_KM = 3.0 # Uma caixa de 3km x 3km

# Caminho para o seu shapefile nacional
# ATENÇÃO: Use barras normais (/) no caminho
NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")

# Nível de confiança para o detector de piscinas
CONFIDENCE_THRESHOLD = 0.3
# --------------------------------------------------------

def main():
    """Executa o pipeline dinâmico."""
    
    # --- 2. SETUP DA EXECUÇÃO ---
    # Cria uma pasta de saída única para esta análise
    output_dir = paths.OUTPUT_DIR / f"analysis_{CENTER_LAT}_{CENTER_LON}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Os resultados desta análise serão salvos em: {output_dir}")

    # Caminho para o GeoJSON temporário da nossa área de estudo
    area_geojson_path = output_dir / "area_of_interest.geojson"
    
    # --- 3. RECORTE DA ÁREA DE ESTUDO ---
    study_area_gdf = create_study_area_geojson(
        national_shapefile_path=NATIONAL_SHAPEFILE_PATH,
        center_lat=CENTER_LAT,
        center_lon=CENTER_LON,
        size_km=AREA_SIZE_KM,
        output_geojson_path=area_geojson_path
    )
    
    if study_area_gdf is None:
        logging.error("Não foi possível criar a área de estudo. Abortando.")
        return

    # --- 4. DETECÇÃO DE PISCINAS (MICROANÁLISE) ---
    # (As outras etapas, como download do Sentinel, viriam aqui antes)
    
    logging.info("Iniciando a etapa de microanálise com o Google Maps e YOLO.")
    
    # Define as pastas para salvar as imagens desta análise
    google_raw_dir = output_dir / "google_raw_images"
    google_detected_dir = output_dir / "google_detected_images"
    
    # Carrega a chave da API do ambiente
    api_key = os.getenv("Maps_API_KEY")
    if not api_key:
        logging.error("Chave Maps_API_KEY não encontrada no .env. Abortando.")
        return

    detected_pools = find_pools_in_sectors(
        risk_sectors_gdf=study_area_gdf,
        api_key=api_key,
        raw_images_dir=google_raw_dir,
        detected_images_dir=google_detected_dir,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )

    if detected_pools:
        # Salva a lista de detecções em um arquivo CSV para análise posterior
        detections_df = pd.DataFrame(detected_pools)
        detections_csv_path = output_dir / "detected_pools.csv"
        detections_df.to_csv(detections_csv_path, index=False)
        logging.info(f"Resultados da detecção de piscinas salvos em: {detections_csv_path}")
    else:
        logging.info("Nenhuma piscina foi detectada na área de estudo.")
        
    logging.info("ANÁLISE DINÂMICA CONCLUÍDA COM SUCESSO!")


if __name__ == "__main__":
    # Configuração de logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Carrega variáveis do .env (para a chave da API)
    from dotenv import load_dotenv
    load_dotenv()

    main()