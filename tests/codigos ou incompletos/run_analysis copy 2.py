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

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_execute(func, description, *args, **kwargs):
    """Executa uma função com tratamento de erro e logging detalhado."""
    logger.info(f"Iniciando: {description}...")
    try:
        result = func(*args, **kwargs)
        logger.info(f"Etapa '{description}' concluída com sucesso.")
        return result
    except Exception as e:
        logger.error(f"Falha na etapa '{description}': {str(e)}")
        logger.error(traceback.format_exc())
        return None

def execute_pipeline(center_lat, center_lon, area_size_km):
    """
    Executa o pipeline completo de análise de risco de ponta a ponta para uma área definida.
    
    Args:
        center_lat (float): Latitude do centro da área
        center_lon (float): Longitude do centro da área  
        area_size_km (float): Tamanho da área em km
        
    Returns:
        tuple: (caminho_do_mapa, caminho_do_sumario) ou (None, None) em caso de erro
    """
    
    # --- Parâmetros de Configuração ---
    NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")
    CONFIDENCE_THRESHOLD = 0.3
    RISK_AMPLIFICATION_FACTOR = 0.2
    SKIP_DOWNLOADS = False  # Para acelerar desenvolvimento
    SKIP_POOL_DETECTION = False

    logger.info("="*60)
    logger.info(f"🚀 INICIANDO ANÁLISE PARA LAT={center_lat}, LON={center_lon} 🚀")
    logger.info("="*60)
    
    try:
        # --- Setup e Criação de Diretórios ---
        output_dir = paths.OUTPUT_DIR / f"analysis_{center_lat}_{center_lon}"
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Resultados serão salvos em: {output_dir}")
        
        # --- Recorte da Área de Estudo ---
        area_geojson_path = output_dir / "area_of_interest.geojson"
        study_area_gdf = safe_execute(
            create_study_area_geojson, 
            "Recorte da área de estudo",
            national_shapefile_path=NATIONAL_SHAPEFILE_PATH, 
            center_lat=center_lat,
            center_lon=center_lon, 
            size_km=area_size_km, 
            output_geojson_path=area_geojson_path
        )
        
        if study_area_gdf is None or study_area_gdf.empty:
            raise Exception("Falha ao criar área de estudo - possivelmente não há setores censitários na região especificada")
            
        study_area_gdf['CD_SETOR'] = study_area_gdf['CD_SETOR'].astype(np.int64)
        logger.info(f"Área de estudo criada com {len(study_area_gdf)} setores censitários")

        # --- Pipeline de Dados Satellite e Climáticos ---
        features_df = None
        final_features_path = output_dir / "final_features.csv"
        
        if not SKIP_DOWNLOADS:
            # Download e processamento de dados Sentinel
            logger.info("Iniciando download de dados Sentinel...")
            
            # Sentinel-1 (SAR)
            s1_path = safe_execute(
                download_and_save_sentinel_data,
                "Download Sentinel-1",
                bbox=[center_lon - 0.05, center_lat - 0.05, center_lon + 0.05, center_lat + 0.05],
                start_date="2024-07-01",
                end_date="2024-07-30",
                satellite="sentinel-1",
                output_path=paths.RAW_DATA_DIR / "sentinel" / f"analysis_{center_lat}_{center_lon}_s1.tiff"
            )
            
            # Sentinel-2 (Óptico)
            s2_path = safe_execute(
                download_and_save_sentinel_data,
                "Download Sentinel-2", 
                bbox=[center_lon - 0.05, center_lat - 0.05, center_lon + 0.05, center_lat + 0.05],
                start_date="2024-07-01",
                end_date="2024-07-30",
                satellite="sentinel-2",
                output_path=paths.RAW_DATA_DIR / "sentinel" / f"analysis_{center_lat}_{center_lon}_s2.tiff"
            )
            
            # Download dados climáticos ERA5
            climate_path = safe_execute(
                download_era5_land_data,
                "Download dados climáticos ERA5",
                bbox=[center_lon - 0.1, center_lat - 0.1, center_lon + 0.1, center_lat + 0.1],
                date_range=("2024-07-01", "2024-07-30"),
                output_path=paths.RAW_DATA_DIR / "climate" / f"analysis_{center_lat}_{center_lon}_era5.nc"
            )
            
            # Processamento de imagens satellite
            if s1_path and s2_path:
                s1_clipped = safe_execute(
                    clip_raster_by_sectors,
                    "Recorte Sentinel-1 por setores",
                    raster_path=s1_path,
                    sectors_gdf=study_area_gdf,
                    output_dir=output_dir / "processed_images" / "sentinel-1"
                )
                
                s2_clipped = safe_execute(
                    clip_raster_by_sectors,
                    "Recorte Sentinel-2 por setores", 
                    raster_path=s2_path,
                    sectors_gdf=study_area_gdf,
                    output_dir=output_dir / "processed_images" / "sentinel-2"
                )
                
                # Cálculo de métricas de imagem
                image_features = safe_execute(
                    calculate_image_metrics,
                    "Cálculo de métricas de imagem",
                    s1_clipped_dir=output_dir / "processed_images" / "sentinel-1",
                    s2_clipped_dir=output_dir / "processed_images" / "sentinel-2",
                    sectors_gdf=study_area_gdf
                )
                
                if image_features is not None and not image_features.empty:
                    image_features.to_csv(output_dir / "image_features.csv", index=False)
            
            # Processamento de dados climáticos
            if climate_path:
                climate_features = safe_execute(
                    aggregate_climate_by_sector,
                    "Agregação de dados climáticos por setor",
                    climate_nc_path=climate_path,
                    sectors_gdf=study_area_gdf
                )
                
                if climate_features is not None and not climate_features.empty:
                    climate_features.to_csv(output_dir / "climate_features.csv", index=False)
            
            # Merge de todas as features
            features_df = safe_execute(
                merge_features,
                "Consolidação de features",
                sectors_gdf=study_area_gdf,
                image_features_path=output_dir / "image_features.csv",
                climate_features_path=output_dir / "climate_features.csv"
            )
            
            if features_df is not None and not features_df.empty:
                features_df.to_csv(final_features_path, index=False)
                logger.info(f"Features finais salvas com {len(features_df)} registros")
        
        # --- Carregamento ou Criação de Features Mock ---
        if not final_features_path.exists() or SKIP_DOWNLOADS:
            logger.warning("Criando features simuladas para desenvolvimento...")
            # Cria features básicas simuladas para desenvolvimento
            features_df = create_mock_features(study_area_gdf)
            features_df.to_csv(final_features_path, index=False)
        else:
            features_df = pd.read_csv(final_features_path)
        
        if features_df is None or features_df.empty:
            raise Exception("Não foi possível carregar ou criar features para análise")

        # --- Cálculo de Risco Base ---
        baseline_risk_df = safe_execute(
            calculate_risk_score, 
            "Cálculo do score de risco base", 
            features_df
        )
        
        if baseline_risk_df is None or baseline_risk_df.empty:
            raise Exception("Falha no cálculo do score de risco")

        # --- Detecção de Piscinas (se habilitado) ---
        detected_pools = []
        if not SKIP_POOL_DETECTION and os.getenv("MAPS_API_KEY"):
            logger.info("Iniciando detecção de piscinas...")
            
            # Cria diretórios para imagens
            raw_images_dir = output_dir / "google_raw_images"
            detected_images_dir = output_dir / "google_detected_images"
            raw_images_dir.mkdir(exist_ok=True)
            detected_images_dir.mkdir(exist_ok=True)
            
            detected_pools = safe_execute(
                find_pools_in_sectors,
                "Detecção de piscinas com Google Maps e IA",
                risk_sectors_gdf=study_area_gdf,
                api_key=os.getenv("MAPS_API_KEY"),
                raw_images_dir=raw_images_dir,
                detected_images_dir=detected_images_dir,
                confidence_threshold=CONFIDENCE_THRESHOLD
            )
            
            if detected_pools is None:
                detected_pools = []
                logger.warning("Detecção de piscinas falhou, continuando sem essa informação")
        else:
            logger.info("Pulando detecção de piscinas (desabilitada ou sem API key)")

        # --- Consolidação Final e Amplificação de Risco ---
        final_risk_gdf = study_area_gdf.merge(baseline_risk_df, on='CD_SETOR', how='left')
        
        # Processamento de piscinas detectadas
        pools_df = pd.DataFrame(detected_pools)
        
        # Adiciona contagem de piscinas sujas por setor
        if not pools_df.empty and 'sector_id' in pools_df.columns:
            pool_counts = pools_df.groupby('sector_id').size().reset_index(name='dirty_pool_count')
            pool_counts['sector_id'] = pool_counts['sector_id'].astype(np.int64)
            final_risk_gdf = final_risk_gdf.merge(
                pool_counts, 
                left_on='CD_SETOR', 
                right_on='sector_id', 
                how='left'
            )
            final_risk_gdf.drop(columns=['sector_id'], inplace=True, errors='ignore')
        
        # Garante que a coluna dirty_pool_count existe
        if 'dirty_pool_count' not in final_risk_gdf.columns:
            final_risk_gdf['dirty_pool_count'] = 0
            
        final_risk_gdf['dirty_pool_count'] = final_risk_gdf['dirty_pool_count'].fillna(0)
        final_risk_gdf['risk_score'] = final_risk_gdf['risk_score'].fillna(0)
        
        # Aplica amplificação de risco baseada em piscinas
        final_risk_gdf['amplified_risk_score'] = (
            final_risk_gdf['risk_score'] + 
            (final_risk_gdf['dirty_pool_count'] * RISK_AMPLIFICATION_FACTOR)
        )
        
        # Classifica níveis de risco
        conditions = [
            final_risk_gdf['amplified_risk_score'] > 0.75,
            final_risk_gdf['amplified_risk_score'] > 0.50
        ]
        choices = ['Alto', 'Médio']
        final_risk_gdf['risk_level'] = np.select(conditions, choices, default='Baixo')

        # Cria GeoDataFrame das piscinas se existirem
        pools_gdf = None
        if not pools_df.empty and 'pool_lat' in pools_df.columns and 'pool_lon' in pools_df.columns:
            pools_gdf = gpd.GeoDataFrame(
                pools_df, 
                geometry=gpd.points_from_xy(pools_df.pool_lon, pools_df.pool_lat), 
                crs="EPSG:4326"
            )
            if 'sector_id' in pools_gdf.columns:
                pools_gdf['sector_id'] = pools_gdf['sector_id'].astype(np.int64)
                pools_gdf = pools_gdf.merge(
                    final_risk_gdf[['CD_SETOR', 'risk_level']], 
                    left_on='sector_id', 
                    right_on='CD_SETOR', 
                    how='left'
                )

        # Salva dados intermediários
        final_risk_gdf.to_file(output_dir / "final_risk_data.geojson", driver="GeoJSON")
        
        if pools_gdf is not None and not pools_gdf.empty:
            pools_gdf.to_file(output_dir / "detected_pools.geojson", driver="GeoJSON")
            pools_df.to_csv(output_dir / "detected_pools.csv", index=False)

        # --- Geração do Mapa Interativo Final ---
        map_path = output_dir / "mapa_de_risco_e_priorizacao.html"
        map_created = safe_execute(
            create_priority_map,
            "Geração do mapa interativo final",
            sectors_risk_gdf=final_risk_gdf,
            dirty_pools_gdf=pools_gdf,
            output_html_path=map_path
        )
        
        if not map_created or not map_path.exists():
            raise Exception("Falha na geração do mapa final")

        # --- Geração do Relatório e Sumário ---
        logger.info("="*60)
        logger.info("📊 RELATÓRIO FINAL DA ANÁLISE")
        logger.info("="*60)
        logger.info(f"Setores analisados: {len(final_risk_gdf)}")
        logger.info(f"Piscinas sujas detectadas: {len(detected_pools)}")
        
        # Distribuição de risco
        risk_distribution_dict = {}
        if 'risk_level' in final_risk_gdf.columns:
            risk_counts = final_risk_gdf['risk_level'].value_counts()
            risk_distribution_dict = risk_counts.to_dict()
            logger.info("Distribuição de Risco:")
            for level, count in risk_counts.items():
                logger.info(f"  - {level}: {count} setores")
        
        # Calcula métricas adicionais para o sumário
        avg_ndvi = final_risk_gdf.get('ndvi_mean', pd.Series([0])).mean()
        avg_temp = final_risk_gdf.get('temperature_mean', pd.Series([25])).mean()  # Default 25°C
        total_precip = final_risk_gdf.get('precipitation_sum', pd.Series([100])).sum()  # Default 100mm
        
        # Cria sumário para o frontend
        summary_data = {
            "total_sectors": int(len(final_risk_gdf)),
            "dirty_pools_found": int(len(detected_pools)),
            "risk_distribution": {k: int(v) for k, v in risk_distribution_dict.items()},
            "avg_ndvi": round(float(avg_ndvi), 3) if pd.notna(avg_ndvi) else None,
            "avg_temp_celsius": round(float(avg_temp), 1) if pd.notna(avg_temp) else None,
            "total_precip_mm": round(float(total_precip), 1) if pd.notna(total_precip) else None,
            "analysis_area": {
                "center_lat": center_lat,
                "center_lon": center_lon,
                "size_km": area_size_km
            },
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        summary_path = output_dir / "summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Mapa interativo salvo em: {map_path}")
        logger.info(f"Sumário salvo em: {summary_path}")
        logger.info("✅ ANÁLISE COMPLETA CONCLUÍDA!")
        
        return str(map_path), str(summary_path)
        
    except Exception as e:
        logger.error(f"Erro crítico no pipeline: {str(e)}")
        logger.error(traceback.format_exc())
        return None, None

def create_mock_features(sectors_gdf):
    """Cria features simuladas para desenvolvimento"""
    logger.info("Gerando features simuladas...")
    
    np.random.seed(42)  # Para resultados reproduzíveis
    n_sectors = len(sectors_gdf)
    
    mock_features = pd.DataFrame({
        'CD_SETOR': sectors_gdf['CD_SETOR'].values,
        
        # Features de imagem simuladas
        'ndvi_mean': np.random.normal(0.3, 0.15, n_sectors).clip(0, 1),
        'ndvi_std': np.random.normal(0.1, 0.05, n_sectors).clip(0, 0.5),
        'vh_mean': np.random.normal(-15, 5, n_sectors),
        'vv_mean': np.random.normal(-10, 5, n_sectors),
        'water_bodies_area': np.random.exponential(0.1, n_sectors),
        
        # Features climáticas simuladas  
        'temperature_mean': np.random.normal(25, 3, n_sectors),
        'temperature_max': np.random.normal(30, 4, n_sectors),
        'humidity_mean': np.random.normal(70, 10, n_sectors).clip(30, 100),
        'precipitation_sum': np.random.exponential(50, n_sectors),
        'wind_speed_mean': np.random.normal(3, 1, n_sectors).clip(0, 10)
    })
    
    logger.info(f"Features simuladas criadas para {n_sectors} setores")
    return mock_features

# --- Bloco para Testes Diretos ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Parâmetros de teste
    TEST_LAT = -22.818
    TEST_LON = -47.069
    TEST_SIZE = 3.0
    
    logger.info("Executando teste do pipeline...")
    result = execute_pipeline(TEST_LAT, TEST_LON, TEST_SIZE)
    
    if result[0] and result[1]:
        logger.info("✅ Teste concluído com sucesso!")
        logger.info(f"Mapa: {result[0]}")
        logger.info(f"Sumário: {result[1]}")
    else:
        logger.error("❌ Teste falhou!")