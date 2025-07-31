import logging
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd
import numpy as np
from calendar import monthrange
import traceback

# --- 1. Imports ---
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


def safe_execute(func, description, *args, **kwargs):
    """Executes a function with error handling and print output."""
    print(f"\n[INFO] Iniciando: {description}...")
    try:
        result = func(*args, **kwargs)
        print(f"[SUCCESS] Etapa '{description}' concluída com sucesso.")
        return result
    except Exception as e:
        print(f"[ERROR] Falha na etapa '{description}': {str(e)}")
        # Uncomment the line below for full error details during deep debugging
        # print(traceback.format_exc())
        return None

# --- 2. Main Execution Block ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # --- 3. Analysis Parameters ---
    CENTER_LAT = -22.818
    CENTER_LON = -47.069
    AREA_SIZE_KM = 3.0
    NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")
    CONFIDENCE_THRESHOLD = 0.3
    RISK_AMPLIFICATION_FACTOR = 0.2
    
    # Flags to skip long steps during debugging
    SKIP_DOWNLOADS = False
    SKIP_POOL_DETECTION = False # Set to False to run the full analysis

    print("="*60)
    print("🚀 INICIANDO PIPELINE DE ANÁLISE DE RISCO DE DENGUE - NAIÁ 🚀")
    print("="*60)
    
    if AREA_SIZE_KM < 15:
        print(f"[WARNING] A área de estudo de {AREA_SIZE_KM} km é pequena. Os dados climáticos (ERA5) podem não ter resolução suficiente e aparecer como vazios.")

    # --- 4. Setup and Area Clipping ---
    output_dir = paths.OUTPUT_DIR / f"analysis_{CENTER_LAT}_{CENTER_LON}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[SETUP] Resultados desta análise serão salvos em: {output_dir}")
    
    area_geojson_path = output_dir / "area_of_interest.geojson"
    study_area_gdf = safe_execute(create_study_area_geojson, "Recorte da área de estudo",
                                  national_shapefile_path=NATIONAL_SHAPEFILE_PATH, center_lat=CENTER_LAT, 
                                  center_lon=CENTER_LON, size_km=AREA_SIZE_KM, output_geojson_path=area_geojson_path)
    if study_area_gdf is None: exit()
    study_area_gdf['CD_SETOR'] = study_area_gdf['CD_SETOR'].astype(np.int64)

    # --- 5 & 6. Data Downloads ---
    bbox = list(study_area_gdf.total_bounds)
    date_config = settings.DATA_RANGES['monitoramento_dengue']
    time_interval = (date_config['start'], date_config['end'])
    s1_raw_path = paths.RAW_SENTINEL_DIR / f"{output_dir.name}_s1.tiff"
    s2_raw_path = paths.RAW_SENTINEL_DIR / f"{output_dir.name}_s2.tiff"
    climate_raw_path = paths.RAW_CLIMATE_DIR / f"{output_dir.name}_era5.nc"

    if not SKIP_DOWNLOADS:
        auth_config = {"client_id": settings.SH_CLIENT_ID, "client_secret": settings.SH_CLIENT_SECRET}
        safe_execute(download_and_save_sentinel_data, "Download de dados Sentinel-1", 'S1', auth_config, bbox, time_interval, s1_raw_path)
        safe_execute(download_and_save_sentinel_data, "Download de dados Sentinel-2", 'S2', auth_config, bbox, time_interval, s2_raw_path)
        year, month = date_config['start'][:4], date_config['start'][5:7]
        days = [str(d).zfill(2) for d in range(1, monthrange(int(year), int(month))[1] + 1)]
        area_cds = [bbox[3], bbox[0], bbox[1], bbox[2]]
        safe_execute(download_era5_land_data, "Download de dados climáticos ERA5", ['total_precipitation', '2m_temperature'], year, month, days, ['00:00', '12:00'], area_cds, climate_raw_path)
    else:
        print("\n[INFO] Pulando etapa de DOWNLOADS (SKIP_DOWNLOADS=True).")

    # --- 7. Feature Extraction ---
    s1_processed_dir = output_dir / "processed_images/sentinel-1"
    s2_processed_dir = output_dir / "processed_images/sentinel-2"
    safe_execute(clip_raster_by_sectors, "Recorte de imagens Sentinel-1", s1_raw_path, area_geojson_path, s1_processed_dir)
    safe_execute(clip_raster_by_sectors, "Recorte de imagens Sentinel-2", s2_raw_path, area_geojson_path, s2_processed_dir)
    climate_features_path = output_dir / "climate_features.csv"
    safe_execute(aggregate_climate_by_sector, "Agregação de dados climáticos por setor", climate_raw_path, area_geojson_path, climate_features_path)
    image_features_path = output_dir / "image_features.csv"
    safe_execute(calculate_image_metrics, "Cálculo de métricas de imagem (NDVI, etc.)", s1_processed_dir, s2_processed_dir, image_features_path)
    final_features_path = output_dir / "final_features.csv"
    safe_execute(merge_features, "União de todas as features", climate_features_path, image_features_path, final_features_path)

    # --- 8. Baseline Risk Calculation ---
    features_df = pd.read_csv(final_features_path)
    baseline_risk_df = safe_execute(calculate_risk_score, "Cálculo do score de risco base", features_df)
    if baseline_risk_df is None: exit()

    # --- 9. Pool Detection ---
    detected_pools = []
    if not SKIP_POOL_DETECTION:
        detected_pools = safe_execute(find_pools_in_sectors, "Detecção de piscinas com Google Maps e IA",
                                      risk_sectors_gdf=study_area_gdf, api_key=os.getenv("Maps_API_KEY"),
                                      raw_images_dir=output_dir / "google_raw_images",
                                      detected_images_dir=output_dir / "google_detected_images",
                                      confidence_threshold=CONFIDENCE_THRESHOLD)
        if detected_pools is None: detected_pools = []
    else:
        print("\n[INFO] Pulando etapa de DETECÇÃO DE PISCINAS (SKIP_POOL_DETECTION=True).")
    
    # --- 10. Consolidation, Amplification, and Final Map ---
    final_risk_gdf = study_area_gdf.merge(baseline_risk_df, on='CD_SETOR', how='left')
    
    pools_df = pd.DataFrame(detected_pools)
    
    # <<< THE FIX: Ensure 'dirty_pool_count' column is created in all cases >>>
    if not pools_df.empty:
        pool_counts = pools_df.groupby('sector_id').size().reset_index(name='dirty_pool_count')
        pool_counts['sector_id'] = pool_counts['sector_id'].astype(np.int64)
        final_risk_gdf = final_risk_gdf.merge(pool_counts, left_on='CD_SETOR', right_on='sector_id', how='left')
        final_risk_gdf.drop(columns=['sector_id'], inplace=True, errors='ignore')
    
    # If the column doesn't exist yet (because detection was skipped or no pools were found), create it.
    if 'dirty_pool_count' not in final_risk_gdf.columns:
        final_risk_gdf['dirty_pool_count'] = 0

    final_risk_gdf['dirty_pool_count'] = final_risk_gdf['dirty_pool_count'].fillna(0)
    final_risk_gdf['risk_score'] = final_risk_gdf['risk_score'].fillna(0)
    final_risk_gdf['amplified_risk_score'] = final_risk_gdf['risk_score'] + (final_risk_gdf['dirty_pool_count'] * RISK_AMPLIFICATION_FACTOR)
    
    # Re-classify risk level based on the amplified score
    conditions = [
        final_risk_gdf['amplified_risk_score'] > 0.75,
        final_risk_gdf['amplified_risk_score'] > 0.50
    ]
    choices = ['Alto', 'Médio']
    final_risk_gdf['risk_level'] = np.select(conditions, choices, default='Baixo')

    pools_gdf = None
    if not pools_df.empty:
        pools_gdf = gpd.GeoDataFrame(pools_df, geometry=gpd.points_from_xy(pools_df.pool_lon, pools_df.pool_lat), crs="EPSG:4326")
        pools_gdf['sector_id'] = pools_gdf['sector_id'].astype(np.int64)
        pools_gdf = pools_gdf.merge(final_risk_gdf[['CD_SETOR', 'risk_level']], left_on='sector_id', right_on='CD_SETOR', how='left')

    map_path = output_dir / "mapa_de_risco_e_priorizacao.html"
    safe_execute(create_priority_map, "Geração do mapa interativo final",
                 sectors_risk_gdf=final_risk_gdf,
                 dirty_pools_gdf=pools_gdf,
                 output_html_path=map_path)

    # --- 11. Final Report ---
    print("\n" + "="*60)
    print("📊 RELATÓRIO FINAL DA ANÁLISE 📊")
    print("="*60)
    print(f"Setores analisados na área de estudo: {len(final_risk_gdf)}")
    print(f"Piscinas sujas detectadas: {len(detected_pools)}")
    
    if 'risk_level' in final_risk_gdf.columns:
        print("\nDistribuição de Risco Final por Setor:")
        risk_counts = final_risk_gdf['risk_level'].value_counts()
        for level, count in risk_counts.items():
            print(f"  - Nível '{level}': {count} setores")
    
    print(f"\n🗺️  Mapa interativo final salvo em: {map_path}")
    print("\n✅ ANÁLISE COMPLETA CONCLUÍDA!")