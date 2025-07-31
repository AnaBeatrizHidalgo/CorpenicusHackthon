import json
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
    print(f"\n[PIPELINE] Iniciando: {description}...")
    try:
        result = func(*args, **kwargs)
        if result is None and "Geração do mapa" not in description:
             print(f"[PIPELINE-WARN] Etapa '{description}' não produziu resultados, mas o pipeline continuará.")
        print(f"[PIPELINE-SUCCESS] Etapa '{description}' concluída.")
        return result
    except Exception as e:
        print(f"[PIPELINE-ERROR] Falha crítica na etapa '{description}': {str(e)}")
        print(traceback.format_exc())
        raise e

# --- 2. Main Pipeline Function ---
def execute_pipeline(center_lat, center_lon, area_size_km, job_id):
    """Executes the complete end-to-end risk analysis pipeline."""
    # --- Parameters ---
    NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")
    CONFIDENCE_THRESHOLD = 0.3
    RISK_AMPLIFICATION_FACTOR = 0.2
    SKIP_DOWNLOADS_AND_PROCESSING = True # Flag inicial
    SKIP_POOL_DETECTION = False

    output_dir = paths.OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[PIPELINE-SETUP] Resultados para {job_id} serão salvos em: {output_dir}")
    
    area_geojson_path = output_dir / "area_of_interest.geojson"
    study_area_gdf = safe_execute(create_study_area_geojson, "Recorte da área de estudo",
                                  national_shapefile_path=NATIONAL_SHAPEFILE_PATH, center_lat=center_lat, 
                                  center_lon=center_lon, size_km=area_size_km, output_geojson_path=area_geojson_path)
    if study_area_gdf is None: return None
    study_area_gdf['CD_SETOR'] = study_area_gdf['CD_SETOR'].astype(np.int64)

    # --- CORREÇÃO: Detecção inteligente de primeira execução ---
    final_features_path = output_dir / "final_features.csv"
    
    # Se quiser pular downloads MAS o arquivo não existe, força processamento completo
    if SKIP_DOWNLOADS_AND_PROCESSING and not final_features_path.exists():
        print(f"\n[PIPELINE-AUTODETECT] 🔍 Primeira execução detectada!")
        print(f"[PIPELINE-AUTODETECT] ❌ Arquivo necessário não encontrado: {final_features_path}")
        print(f"[PIPELINE-AUTODETECT] ⚡ Forçando execução completa do pipeline...")
        SKIP_DOWNLOADS_AND_PROCESSING = False

    # --- Conditional Data Processing Pipeline ---
    if not SKIP_DOWNLOADS_AND_PROCESSING:
        print("\n[PIPELINE] 🚀 Executando pipeline COMPLETO de download e processamento de dados.")
        
        # --- Data Downloads ---
        bbox = list(study_area_gdf.total_bounds)
        date_config = settings.DATA_RANGES['monitoramento_dengue']
        time_interval = (date_config['start'], date_config['end'])
        s1_raw_path = paths.RAW_SENTINEL_DIR / f"{job_id}_s1.tiff"
        s2_raw_path = paths.RAW_SENTINEL_DIR / f"{job_id}_s2.tiff"
        climate_raw_path = paths.RAW_CLIMATE_DIR / f"{job_id}_era5.nc"
        auth_config = {"client_id": settings.SH_CLIENT_ID, "client_secret": settings.SH_CLIENT_SECRET}
        
        safe_execute(download_and_save_sentinel_data, "Download de dados Sentinel-1", 'S1', auth_config, bbox, time_interval, s1_raw_path)
        safe_execute(download_and_save_sentinel_data, "Download de dados Sentinel-2", 'S2', auth_config, bbox, time_interval, s2_raw_path)
        
        year, month = date_config['start'][:4], date_config['start'][5:7]
        days = [str(d).zfill(2) for d in range(1, monthrange(int(year), int(month))[1] + 1)]
        area_cds = [bbox[3], bbox[0], bbox[1], bbox[2]]
        safe_execute(download_era5_land_data, "Download de dados climáticos ERA5", ['total_precipitation', '2m_temperature'], year, month, days, ['00:00', '12:00'], area_cds, climate_raw_path)
    
        # --- Feature Extraction ---
        s1_processed_dir = output_dir / "processed_images/sentinel-1"
        s2_processed_dir = output_dir / "processed_images/sentinel-2"
        safe_execute(clip_raster_by_sectors, "Recorte de imagens Sentinel-1", s1_raw_path, area_geojson_path, s1_processed_dir)
        safe_execute(clip_raster_by_sectors, "Recorte de imagens Sentinel-2", s2_raw_path, area_geojson_path, s2_processed_dir)
        
        climate_features_path = output_dir / "climate_features.csv"
        safe_execute(aggregate_climate_by_sector, "Agregação de dados climáticos por setor", climate_raw_path, area_geojson_path, climate_features_path)
        
        image_features_path = output_dir / "image_features.csv"
        safe_execute(calculate_image_metrics, "Cálculo de métricas de imagem (NDVI, etc.)", s1_processed_dir, s2_processed_dir, image_features_path)
        safe_execute(merge_features, "União de todas as features", climate_features_path, image_features_path, final_features_path)
        
        print(f"[PIPELINE-SUCCESS] ✅ Pipeline de processamento concluído! Arquivo criado: {final_features_path}")
        
    else:
        print(f"\n[PIPELINE] ⚡ Pulando downloads e processamento. Usando arquivo de features existente: {final_features_path}")
        
        # Verificação final de segurança
        if not final_features_path.exists():
            error_msg = f"ERRO CRÍTICO: Arquivo de features ainda não existe após o processamento: {final_features_path}"
            print(f"[PIPELINE-ERROR] {error_msg}")
            raise FileNotFoundError(error_msg)

    # --- Verificação de integridade do arquivo ---
    try:
        features_df = pd.read_csv(final_features_path)
        if features_df.empty:
            raise ValueError("Arquivo de features está vazio")
        print(f"[PIPELINE-INFO] ✅ Arquivo de features carregado com sucesso. Shape: {features_df.shape}")
    except Exception as e:
        error_msg = f"Erro ao carregar arquivo de features {final_features_path}: {str(e)}"
        print(f"[PIPELINE-ERROR] {error_msg}")
        raise Exception(error_msg)

    # --- Baseline Risk Calculation ---
    baseline_risk_df = safe_execute(calculate_risk_score, "Cálculo do score de risco base", features_df)
    if baseline_risk_df is None: return None

    # --- Pool Detection ---
    detected_pools = []
    if not SKIP_POOL_DETECTION:
        detected_pools = safe_execute(find_pools_in_sectors, "Deteção de piscinas com Google Maps e IA",
                                      risk_sectors_gdf=study_area_gdf, api_key=os.getenv("Maps_API_KEY"),
                                      raw_images_dir=output_dir / "google_raw_images",
                                      detected_images_dir=output_dir / "google_detected_images",
                                      confidence_threshold=CONFIDENCE_THRESHOLD)
        if detected_pools is None: detected_pools = []
    else:
        print("\n[PIPELINE] ⏭️ Pulando etapa de DETECÇÃO DE PISCINAS (SKIP_POOL_DETECTION=True).")
    
    # --- Consolidation and Map Generation ---
    final_risk_gdf = study_area_gdf.merge(baseline_risk_df, on='CD_SETOR', how='left')
    pools_df = pd.DataFrame(detected_pools)

    if not pools_df.empty:
        pool_counts = pools_df.groupby('sector_id').size().reset_index(name='dirty_pool_count')
        pool_counts['sector_id'] = pool_counts['sector_id'].astype(np.int64)
        final_risk_gdf = final_risk_gdf.merge(pool_counts, left_on='CD_SETOR', right_on='sector_id', how='left')
    
    if 'dirty_pool_count' not in final_risk_gdf.columns:
        final_risk_gdf['dirty_pool_count'] = 0

    final_risk_gdf['dirty_pool_count'] = final_risk_gdf['dirty_pool_count'].fillna(0)
    final_risk_gdf['risk_score'] = final_risk_gdf['risk_score'].fillna(0)
    final_risk_gdf['amplified_risk_score'] = final_risk_gdf['risk_score'] + (final_risk_gdf['dirty_pool_count'] * RISK_AMPLIFICATION_FACTOR)
    
    conditions = [final_risk_gdf['amplified_risk_score'] > 0.75, final_risk_gdf['amplified_risk_score'] > 0.50]
    choices = ['Alto', 'Médio']
    final_risk_gdf['risk_level'] = np.select(conditions, choices, default='Baixo')

    pools_gdf = None
    if not pools_df.empty:
        pools_gdf = gpd.GeoDataFrame(pools_df, geometry=gpd.points_from_xy(pools_df.pool_lon, pools_df.pool_lat), crs="EPSG:4326")
        pools_gdf = pools_gdf.merge(final_risk_gdf[['CD_SETOR', 'risk_level']], left_on='sector_id', right_on='CD_SETOR', how='left')

    map_path = output_dir / "mapa_de_risco_e_priorizacao.html"
    safe_execute(create_priority_map, "Geração do mapa interativo final",
                 sectors_risk_gdf=final_risk_gdf, dirty_pools_gdf=pools_gdf, output_html_path=map_path)

    # --- Summary Generation for Frontend ---
    summary_path = output_dir / "summary.json"
    
    avg_ndvi = final_risk_gdf['ndvi_mean'].mean() if 'ndvi_mean' in final_risk_gdf.columns else np.nan
    avg_temp_k = final_risk_gdf['t2m_mean'].mean() if 't2m_mean' in final_risk_gdf.columns else np.nan
    avg_precip_m = final_risk_gdf['tp_mean'].mean() if 'tp_mean' in final_risk_gdf.columns else np.nan
    
    summary_data = {
        "map_url": str(Path(map_path).relative_to(Path.cwd())).replace('\\', '/'),
        "summary_url": str(Path(summary_path).relative_to(Path.cwd())).replace('\\', '/'),
        "total_sectors": int(len(final_risk_gdf)),
        "dirty_pools_found": int(len(detected_pools)),
        "risk_distribution": {k: int(v) for k, v in final_risk_gdf['risk_level'].value_counts().to_dict().items()},
        "avg_ndvi": f"{avg_ndvi:.3f}" if pd.notna(avg_ndvi) else "N/D",
        "avg_temp_celsius": f"{avg_temp_k - 273.15:.1f}" if pd.notna(avg_temp_k) else "N/D",
        "total_precip_mm": f"{avg_precip_m * 1000 * 30:.1f}" if pd.notna(avg_precip_m) else "N/D",
    }
    
    with open(summary_path, 'w') as f:
        json.dump(summary_data, f, indent=4)
    
    print(f"[PIPELINE-FINAL] 🎉 Pipeline concluído com sucesso!")
    print(f"[PIPELINE-FINAL] 📊 Resumo: {len(final_risk_gdf)} setores, {len(detected_pools)} piscinas detectadas")
    print(f"[PIPELINE-FINAL] 🗺️ Mapa salvo em: {map_path}")
        
    return summary_data