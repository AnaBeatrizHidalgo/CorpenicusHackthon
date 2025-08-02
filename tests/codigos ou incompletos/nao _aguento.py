import logging
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd
import numpy as np
from calendar import monthrange
import traceback

# --- 1. Imports dos Módulos do Projeto ---
# (Assumindo que os nomes dos arquivos e funções estão como nas suas últimas versões)
from src.config import settings
from src.utils import paths
from src.utils.geoprocessing import create_study_area_geojson
from src.data.sentinel_downloader import download_and_save_sentinel_data
from src.data.climate_downloader import download_era5_land_data
from src.features.image_processor import clip_raster_by_sectors
from src.features.climate_feature_builder import aggregate_climate_by_sector
from src.features.metrics_calculator import calculate_image_metrics, merge_features
from src.analysis.risk_assessor import calculate_risk_score
from src.models.pool_detector import find_pools_in_sectors
from src.analysis.map_generator import create_priority_map

# --- 2. Bloco Principal de Execução ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    from dotenv import load_dotenv
    load_dotenv()
    logger = logging.getLogger(__name__)

    # --- 3. PARÂMETROS DA ANÁLISE ---
    CENTER_LAT = -22.818
    CENTER_LON = -47.069
    AREA_SIZE_KM = 3.0 # Para garantir dados climáticos, áreas maiores (ex: >15km) são melhores
    NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")
    CONFIDENCE_THRESHOLD = 0.3
    RISK_AMPLIFICATION_FACTOR = 0.2

    # Flags para pular etapas longas durante o debug
    SKIP_DOWNLOADS = True # Mude para False para baixar os dados novamente

    # --- 4. SETUP E RECORTE DA ÁREA ---
    output_dir = paths.OUTPUT_DIR / f"analysis_{CENTER_LAT}_{CENTER_LON}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Resultados desta análise serão salvos em: {output_dir}")
    area_geojson_path = output_dir / "area_of_interest.geojson"
    study_area_gdf = create_study_area_geojson(national_shapefile_path=NATIONAL_SHAPEFILE_PATH, center_lat=CENTER_LAT, center_lon=CENTER_LON, size_km=AREA_SIZE_KM, output_geojson_path=area_geojson_path)
    if study_area_gdf is None: exit()
    study_area_gdf['CD_SETOR'] = study_area_gdf['CD_SETOR'].astype(np.int64)

    # --- 5 & 6. DOWNLOAD DE DADOS (COPERNICUS) ---
    bbox = list(study_area_gdf.total_bounds)
    date_config = settings.DATA_RANGES['monitoramento_dengue']
    time_interval = (date_config['start'], date_config['end'])
    s1_raw_path = paths.RAW_SENTINEL_DIR / f"{output_dir.name}_s1.tiff"
    s2_raw_path = paths.RAW_SENTINEL_DIR / f"{output_dir.name}_s2.tiff"
    climate_raw_path = paths.RAW_CLIMATE_DIR / f"{output_dir.name}_era5.nc"

    if not SKIP_DOWNLOADS:
        logger.info("--- INICIANDO ETAPA DE DOWNLOADS ---")
        auth_config = {"client_id": settings.SH_CLIENT_ID, "client_secret": settings.SH_CLIENT_SECRET}
        download_and_save_sentinel_data('S1', auth_config, bbox, time_interval, s1_raw_path)
        download_and_save_sentinel_data('S2', auth_config, bbox, time_interval, s2_raw_path)

        year, month = date_config['start'][:4], date_config['start'][5:7]
        days = [str(d).zfill(2) for d in range(1, monthrange(int(year), int(month))[1] + 1)]
        area_cds = [bbox[3], bbox[0], bbox[1], bbox[2]]
        download_era5_land_data(['total_precipitation', '2m_temperature'], year, month, days, ['00:00', '12:00'], area_cds, climate_raw_path)
    else:
        logger.info("--- PULANDO ETAPA DE DOWNLOADS (SKIP_DOWNLOADS=True) ---")

    # --- 7. EXTRAÇÃO DE FEATURES ---
    logger.info("--- INICIANDO EXTRAÇÃO DE FEATURES ---")
    s1_processed_dir = output_dir / "processed_images/sentinel-1"
    s2_processed_dir = output_dir / "processed_images/sentinel-2"
    clip_raster_by_sectors(s1_raw_path, area_geojson_path, s1_processed_dir)
    clip_raster_by_sectors(s2_raw_path, area_geojson_path, s2_processed_dir)
    
    climate_features_path = output_dir / "climate_features.csv"
    aggregate_climate_by_sector(climate_raw_path, area_geojson_path, climate_features_path)
    
    image_features_path = output_dir / "image_features.csv"
    calculate_image_metrics(s1_processed_dir, s2_processed_dir, image_features_path)
    
    final_features_path = output_dir / "final_features.csv"
    merge_features(climate_features_path, image_features_path, final_features_path)

    # --- 8. CÁLCULO DE RISCO BASE ---
    logger.info("--- INICIANDO ANÁLISE DE RISCO ---")
    features_df = pd.read_csv(final_features_path)
    baseline_risk_df = calculate_risk_score(features_df)

   #  --- 9. DETECÇÃO DE PISCINAS ---
    logger.info("--- INICIANDO DETECÇÃO DE PISCINAS ---")
    detected_pools = find_pools_in_sectors(
        risk_sectors_gdf=study_area_gdf, 
        api_key=os.getenv("Maps_API_KEY"),
        raw_images_dir=output_dir / "google_raw_images",
        detected_images_dir=output_dir / "google_detected_images",
        confidence_threshold=CONFIDENCE_THRESHOLD
    )
    detected_pools = []
    # --- 10. CONSOLIDAÇÃO E AMPLIFICAÇÃO DE RISCO ---
    logger.info("--- CONSOLIDANDO RESULTADOS ---")
    final_risk_gdf = study_area_gdf.merge(baseline_risk_df, on='CD_SETOR', how='left')
    
    pools_df = pd.DataFrame(detected_pools)
    if not pools_df.empty:
        pool_counts = pools_df.groupby('sector_id').size().reset_index(name='dirty_pool_count')
        pool_counts['sector_id'] = pool_counts['sector_id'].astype(np.int64)
        
        final_risk_gdf = final_risk_gdf.merge(pool_counts, left_on='CD_SETOR', right_on='sector_id', how='left')
        final_risk_gdf.drop(columns=['sector_id'], inplace=True, errors='ignore')
    else:
        final_risk_gdf['dirty_pool_count'] = 0

    final_risk_gdf['dirty_pool_count'] = final_risk_gdf['dirty_pool_count'].fillna(0)
    final_risk_gdf['amplified_risk_score'] = final_risk_gdf['risk_score'].fillna(0) + (final_risk_gdf['dirty_pool_count'] * RISK_AMPLIFICATION_FACTOR)
    
    # Re-executa o risk_assessor apenas no DataFrame final para garantir consistência
    # O risk_assessor já foi alterado por você para ser robusto
    final_risk_gdf['final_risk_level'] = calculate_risk_score(final_risk_gdf)['risk_level']

    # --- 11. GERAÇÃO DO MAPA FINAL ---
    logger.info("--- GERANDO MAPA FINAL ---")
    pools_gdf = None
    if not pools_df.empty:
        pools_gdf = gpd.GeoDataFrame(pools_df, geometry=gpd.points_from_xy(pools_df.pool_lon, pools_df.pool_lat), crs="EPSG:4326")
        
    map_path = output_dir / "mapa_de_risco_e_priorizacao.html"
    create_priority_map(
        sectors_risk_gdf=final_risk_gdf,
        dirty_pools_gdf=pools_gdf,
        output_html_path=map_path
    )
    
    logger.info(f"ANÁLISE COMPLETA CONCLUÍDA! O mapa interativo está em: {map_path}")
