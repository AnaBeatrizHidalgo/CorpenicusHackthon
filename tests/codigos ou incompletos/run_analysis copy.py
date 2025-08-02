import logging
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd
import numpy as np
from calendar import monthrange
import traceback
import json

# --- 1. Imports dos Módulos do Projeto ---
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
    """Executa uma função com tratamento de erro e output com print."""
    print(f"\n[INFO] Iniciando: {description}...")
    try:
        result = func(*args, **kwargs)
        print(f"[SUCCESS] Etapa '{description}' concluída com sucesso.")
        return result
    except Exception as e:
        print(f"[ERROR] Falha na etapa '{description}': {str(e)}")
        # print(traceback.format_exc()) # Descomente para depuração profunda
        return None

# --- 2. Função Principal do Pipeline ---
def execute_pipeline(center_lat, center_lon, area_size_km):
    """
    Executa o pipeline completo de análise de risco de ponta a ponta para uma área definida.
    """
    # --- Parâmetros ---
    NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")
    CONFIDENCE_THRESHOLD = 0.3
    RISK_AMPLIFICATION_FACTOR = 0.2
    SKIP_DOWNLOADS = True
    SKIP_POOL_DETECTION = False

    print("="*60)
    print(f"🚀 INICIANDO ANÁLISE PARA LAT={center_lat}, LON={center_lon} 🚀")
    print("="*60)
    
    # --- Setup e Recorte da Área ---
    output_dir = paths.OUTPUT_DIR / f"analysis_{center_lat}_{center_lon}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[SETUP] Resultados desta análise serão salvos em: {output_dir}")
    
    area_geojson_path = output_dir / "area_of_interest.geojson"
    study_area_gdf = safe_execute(create_study_area_geojson, "Recorte da área de estudo",
                                  national_shapefile_path=NATIONAL_SHAPEFILE_PATH, center_lat=center_lat, 
                                  center_lon=center_lon, size_km=area_size_km, output_geojson_path=area_geojson_path)
    if study_area_gdf is None: return None, None
    study_area_gdf['CD_SETOR'] = study_area_gdf['CD_SETOR'].astype(np.int64)

    # --- Pipeline de Dados Copernicus ---
    # (O código para download e processamento de features permanece o mesmo)
    final_features_path = output_dir / "final_features.csv"
    
    # --- Cálculo de Risco Base ---
    if not final_features_path.exists():
        print(f"[ERROR] Arquivo de features não encontrado em {final_features_path}. Execute as etapas de processamento primeiro.")
        return None, None
    features_df = pd.read_csv(final_features_path)
    baseline_risk_df = safe_execute(calculate_risk_score, "Cálculo do score de risco base", features_df)
    if baseline_risk_df is None: return None, None

    # --- Deteção de Piscinas ---
    detected_pools = []
    if not SKIP_POOL_DETECTION:
        detected_pools = safe_execute(find_pools_in_sectors, "Deteção de piscinas com Google Maps e IA",
                                      risk_sectors_gdf=study_area_gdf, api_key=os.getenv("Maps_API_KEY"),
                                      raw_images_dir=output_dir / "google_raw_images",
                                      detected_images_dir=output_dir / "google_detected_images",
                                      confidence_threshold=CONFIDENCE_THRESHOLD)
        if detected_pools is None: detected_pools = []
    else:
        print("\n[INFO] Pulando etapa de DETEÇÃO DE PISCINAS (SKIP_POOL_DETECTION=True).")
    
    # --- Consolidação, Amplificação e Mapa Final ---
    final_risk_gdf = study_area_gdf.merge(baseline_risk_df, on='CD_SETOR', how='left')
    
    pools_df = pd.DataFrame(detected_pools)
    
    # Lógica robusta que garante a criação da coluna 'dirty_pool_count'
    if not pools_df.empty:
        pool_counts = pools_df.groupby('sector_id').size().reset_index(name='dirty_pool_count')
        pool_counts['sector_id'] = pool_counts['sector_id'].astype(np.int64)
        final_risk_gdf = final_risk_gdf.merge(pool_counts, left_on='CD_SETOR', right_on='sector_id', how='left')
        final_risk_gdf.drop(columns=['sector_id'], inplace=True, errors='ignore')
    
    if 'dirty_pool_count' not in final_risk_gdf.columns:
        final_risk_gdf['dirty_pool_count'] = 0

    final_risk_gdf['dirty_pool_count'] = final_risk_gdf['dirty_pool_count'].fillna(0)
    final_risk_gdf['risk_score'] = final_risk_gdf['risk_score'].fillna(0)
    final_risk_gdf['amplified_risk_score'] = final_risk_gdf['risk_score'] + (final_risk_gdf['dirty_pool_count'] * RISK_AMPLIFICATION_FACTOR)
    
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

    # --- Geração do Relatório e do JSON de Sumário ---
    print("\n" + "="*60)
    print("📊 RELATÓRIO FINAL DA ANÁLISE 📊")
    print("="*60)
    print(f"Setores analisados na área de estudo: {len(final_risk_gdf)}")
    print(f"Piscinas sujas detectadas: {len(detected_pools)}")
    
    risk_distribution_dict = {}
    if 'risk_level' in final_risk_gdf.columns:
        print("\nDistribuição de Risco Final por Setor:")
        risk_counts = final_risk_gdf['risk_level'].value_counts()
        risk_distribution_dict = risk_counts.to_dict()
        for level, count in risk_counts.items():
            print(f"  - Nível '{level}': {count} setores")
    
    print(f"\n🗺️  Mapa interativo final salvo em: {map_path}")
    print("\n✅ ANÁLISE COMPLETA CONCLUÍDA!")
    
    # Cria o arquivo de sumário para o frontend
    summary_path = output_dir / "summary.json"
    summary_data = {
        "total_sectors": len(final_risk_gdf),
        "dirty_pools_found": len(detected_pools),
        "risk_distribution": risk_distribution_dict,
        "map_url": str(map_path)
    }
    with open(summary_path, 'w') as f:
        json.dump(summary_data, f, indent=4)
        
    return str(map_path), str(summary_path)


# --- 3. Bloco para Testes Diretos ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Define os parâmetros de teste
    TEST_LAT = -22.818
    TEST_LON = -47.069
    TEST_SIZE = 3.0
    
    # Chama a função principal
    execute_pipeline(TEST_LAT, TEST_LON, TEST_SIZE)