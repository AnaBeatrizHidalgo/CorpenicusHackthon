# main.py (Versão Corrigida)
import logging
from calendar import monthrange

# --- 1. Imports ---
# Importa as configurações e os caminhos primeiro
from src.config import settings
from src.utils import paths

# Importa as FUNÇÕES dos módulos de cada etapa
from src.data.sentinel_downloader import download_and_save_sentinel_data
from src.data.climate_downloader import download_era5_land_data
from src.features.climate_feature_builder import aggregate_climate_by_sector
from src.features.image_processor import clip_raster_by_sectors
from src.features.metrics_calculator import calculate_image_metrics, merge_features # <<< NOVO IMPORT


def run_pipeline():
    """
    Pipeline de execução principal do projeto NAIÁ.
    """
    # --- 2. Setup Inicial ---
    logging.info("Iniciando o pipeline do projeto NAIÁ...")
    paths.create_project_dirs()
    logging.info("Estrutura de diretórios verificada.")

    # Define o intervalo de tempo a ser usado do settings.py
    date_config = settings.DATA_RANGES['monitoramento_dengue']
    time_interval_sentinel = (date_config['start'], date_config['end'])

    # --- 3. Aquisição de Dados (Sentinel) ---
    logging.info("Iniciando etapa de aquisição de dados do Sentinel.")
    auth_config = {"client_id": settings.SH_CLIENT_ID, "client_secret": settings.SH_CLIENT_SECRET}
    bbox = settings.STUDY_AREA['bbox']
    s1_output_path = paths.RAW_SENTINEL_DIR / f"s1_{time_interval_sentinel[0]}_{time_interval_sentinel[1]}.tiff"
    s2_output_path = paths.RAW_SENTINEL_DIR / f"s2_{time_interval_sentinel[0]}_{time_interval_sentinel[1]}.tiff"

    try:
        download_and_save_sentinel_data('S1', auth_config, bbox, time_interval_sentinel, s1_output_path)
        download_and_save_sentinel_data('S2', auth_config, bbox, time_interval_sentinel, s2_output_path)
        logging.info("Etapa de aquisição de dados do Sentinel concluída.")
    except Exception as e:
        logging.error(f"Pipeline falhou no download do Sentinel. Erro: {e}")
        return

    # --- 4. Aquisição de Dados (Climáticos) ---
    logging.info("Iniciando etapa de aquisição de dados climáticos (ERA5-Land).")
    year, month = date_config['start'][:4], date_config['start'][5:7]
    num_days_in_month = monthrange(int(year), int(month))[1]
    days_list = [str(day).zfill(2) for day in range(1, num_days_in_month + 1)]
    area_cds = [bbox[3], bbox[0], bbox[1], bbox[2]]
    climate_output_path = paths.RAW_CLIMATE_DIR / f"era5_land_{year}-{month}.nc"

    try:
        download_era5_land_data(
            variables=['total_precipitation', '2m_temperature'],
            year=year, month=month, days=days_list,
            time=['00:00', '06:00', '12:00', '18:00'],
            area=area_cds, output_path=climate_output_path
        )
        logging.info("Etapa de aquisição de dados climáticos concluída.")
    except Exception as e:
        logging.error(f"Pipeline falhou no download de dados climáticos. Erro: {e}")
        return

    # --- 5. Processamento e Criação de Features (Clima) ---
    logging.info("Iniciando etapa de processamento de dados climáticos.")
    geodata_path = paths.RAW_GEODATA_DIR / "setores_barao.geojson"  # Confirme o nome do seu arquivo
    processed_climate_path = paths.PROCESSED_DIR / "climate_features.csv"

    try:
        aggregate_climate_by_sector(
            netcdf_path=climate_output_path,
            geodata_path=geodata_path,
            output_path=processed_climate_path
        )
        logging.info("Features climáticas por setor geradas com sucesso.")
    except Exception as e:
        logging.error(f"Pipeline falhou no processamento de dados climáticos. Erro: {e}")
        return

     # --- 6. Processamento de Imagens de Satélite --- <<< NOVA ETAPA >>>
    logging.info("Iniciando etapa de processamento de imagens (recorte por setor).")
    
    # Define os caminhos de entrada (imagens brutas) e de saída (pastas para imagens recortadas)
    s1_raw_path = paths.RAW_SENTINEL_DIR / f"s1_{time_interval_sentinel[0]}_{time_interval_sentinel[1]}.tiff"
    s2_raw_path = paths.RAW_SENTINEL_DIR / f"s2_{time_interval_sentinel[0]}_{time_interval_sentinel[1]}.tiff"
    geodata_path = paths.RAW_GEODATA_DIR / "setores_barao.geojson"
    
    s1_processed_dir = paths.PROCESSED_DIR / "images" / "sentinel-1"
    s2_processed_dir = paths.PROCESSED_DIR / "images" / "sentinel-2"

    try:
        # Recorta a imagem do Sentinel-1
        clip_raster_by_sectors(
            raster_path=s1_raw_path,
            geodata_path=geodata_path,
            output_dir=s1_processed_dir
        )
        # Recorta a imagem do Sentinel-2
        clip_raster_by_sectors(
            raster_path=s2_raw_path,
            geodata_path=geodata_path,
            output_dir=s2_processed_dir
        )
        logging.info("Processamento de imagens por setor concluído.")
    except Exception as e:
        logging.error(f"Pipeline falhou na etapa de processamento de imagens. Erro: {e}")
        return
 # --- 7. Cálculo de Métricas de Imagem --- <<< NOVA ETAPA >>>
    logging.info("Iniciando etapa de cálculo de métricas de imagem (NDVI, Backscatter).")
    
    # Caminho para salvar as métricas intermediárias de imagem
    image_features_path = paths.PROCESSED_DIR / "image_features.csv"
    
    try:
        calculate_image_metrics(
            s1_images_dir=s1_processed_dir, # Definido na etapa anterior
            s2_images_dir=s2_processed_dir, # Definido na etapa anterior
            output_path=image_features_path
        )
        logging.info("Cálculo de métricas de imagem concluído.")
    except Exception as e:
        logging.error(f"Pipeline falhou no cálculo de métricas de imagem. Erro: {e}")
        return

    # --- 8. Junção de Todas as Features --- <<< NOVA ETAPA >>>
    logging.info("Iniciando etapa final: unindo todas as features.")
    
    # Caminho para o arquivo final
    final_features_path = paths.PROCESSED_DIR / "final_features.csv"
    
    try:
        merge_features(
            climate_features_path=processed_climate_path, # Definido na etapa de clima
            image_features_path=image_features_path,
            output_path=final_features_path
        )
        logging.info("Todos os dados foram processados e unidos com sucesso.")
    except Exception as e:
        logging.error(f"Pipeline falhou na junção final de features. Erro: {e}")
        return

    # --- 9. Finalização do Pipeline ---
    logging.info("PIPELINE CONCLUÍDO COM SUCESSO!")


# Bloco de execução principal para o pipeline
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    run_pipeline()