# run_analysis.py - VERSÃO CORRIGIDA COM PRESERVAÇÃO DO RISK SCORE
import json
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd
import numpy as np
from calendar import monthrange
import traceback
import rasterio

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
            print(f"⚠️ Etapa '{description}' não produziu resultados.")
            return None
        print(f"✅ [PIPELINE-SUCCESS] Etapa '{description}' concluída.")
        return result
    except Exception as e:
        print(f"❌ [PIPELINE-ERROR] Falha crítica na etapa '{description}': {str(e)}")
        traceback.print_exc()
        raise e

def _calculate_climate_download_area(study_area_gdf, min_size_km=60):
    """
    Calcula uma área MUITO MAIOR para download de dados climáticos.
    Garante cobertura completa expandindo significativamente a área.
    """
    bounds = study_area_gdf.total_bounds  # [min_lon, min_lat, max_lon, max_lat]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    # Calcular tamanho atual da área
    lat_degree_km = 111.32
    lon_degree_km = 111.32 * np.cos(np.radians(center_lat))
    
    current_width_km = (bounds[2] - bounds[0]) * lon_degree_km
    current_height_km = (bounds[3] - bounds[1]) * lat_degree_km
    current_size_km = max(current_width_km, current_height_km)
    
    print(f"📏 Área atual dos setores: {current_size_km:.2f} km")
    print(f"📡 Tamanho mínimo para ERA5-Land: {min_size_km} km")
    
    # SEMPRE expandir para área maior, independente do tamanho atual
    safety_margin = 1.5  # 50% de margem extra
    expanded_size_km = max(min_size_km, current_size_km * 2) * safety_margin
    
    print(f"🔧 Expandindo área de {current_size_km:.2f} km para {expanded_size_km:.2f} km (com margem de segurança de 50%)")
    
    # Calcular nova área expandida
    half_size_lat_deg = (expanded_size_km / 2) / lat_degree_km
    half_size_lon_deg = (expanded_size_km / 2) / lon_degree_km
    
    expanded_bounds = [
        center_lon - half_size_lon_deg,  # min_lon
        center_lat - half_size_lat_deg,  # min_lat
        center_lon + half_size_lon_deg,  # max_lon
        center_lat + half_size_lat_deg   # max_lat
    ]
    
    # Validação final
    final_width_km = (expanded_bounds[2] - expanded_bounds[0]) * lon_degree_km
    final_height_km = (expanded_bounds[3] - expanded_bounds[1]) * lat_degree_km
    
    print(f"📦 Área final expandida: {expanded_bounds}")
    print(f"📐 Dimensões finais: {final_width_km:.2f} km x {final_height_km:.2f} km")
    print(f"✅ Garantia de cobertura total para todos os setores")
    
    return expanded_bounds

# --- 2. Main Pipeline Function ---
def execute_pipeline(center_lat, center_lon, area_size_km, job_id):
    """Executes the complete end-to-end risk analysis pipeline."""
    # --- Parameters ---
    NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")
    CONFIDENCE_THRESHOLD = 0.3
    RISK_AMPLIFICATION_FACTOR = 0.2
    SKIP_DOWNLOADS_AND_PROCESSING = False
    SKIP_POOL_DETECTION = False

    output_dir = paths.OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"🗂️ [PIPELINE-SETUP] Resultados para {job_id} serão salvos em: {output_dir}")
    
    area_geojson_path = output_dir / "area_of_interest.geojson"
    study_area_gdf = safe_execute(create_study_area_geojson, "Recorte da área de estudo",
                                  national_shapefile_path=NATIONAL_SHAPEFILE_PATH, center_lat=center_lat, 
                                  center_lon=center_lon, size_km=area_size_km, output_geojson_path=area_geojson_path)
    if study_area_gdf is None:
        print("❌ Falha na criação da área de estudo. Encerrando pipeline.")
        return None
    
    study_area_gdf['CD_SETOR'] = pd.to_numeric(study_area_gdf['CD_SETOR'], errors='coerce').astype(np.int64)

    final_features_path = output_dir / "final_features.csv"
    
    if SKIP_DOWNLOADS_AND_PROCESSING and not final_features_path.exists():
        print(f"\n🔍 [PIPELINE-AUTODETECT] Primeira execução detectada!")
        print(f"❌ Arquivo necessário não encontrado: {final_features_path}")
        print(f"⚡ Forçando execução completa do pipeline...")
        SKIP_DOWNLOADS_AND_PROCESSING = False

    # --- Conditional Data Processing Pipeline ---
    if not SKIP_DOWNLOADS_AND_PROCESSING:
        print("\n🚀 [PIPELINE] Executando pipeline COMPLETO de download e processamento de dados.")
        
        print("\n📊 === CALCULANDO ÁREAS PARA DOWNLOAD ===")
        
        # Área para Sentinel (pode usar área original)
        sentinel_bbox = list(study_area_gdf.total_bounds)
        print(f"🛰️ Área Sentinel: {sentinel_bbox}")
        
        # Área para clima (MUITO expandida para garantir cobertura total)
        climate_bbox = _calculate_climate_download_area(study_area_gdf, min_size_km=60)
        print(f"🌡️ Área Clima: {climate_bbox}")
        
        area_cds = [climate_bbox[3], climate_bbox[0], climate_bbox[1], climate_bbox[2]]  # [max_lat, min_lon, min_lat, max_lon]
        print(f"📡 Área CDS (N,O,S,L): {area_cds}")
        
        # Validação final da área CDS
        if area_cds[0] <= area_cds[2]:  # Norte <= Sul
            print(f"❌ ERRO: Área CDS inválida - Norte ({area_cds[0]}) <= Sul ({area_cds[2]})")
            return None
        if area_cds[1] >= area_cds[3]:  # Oeste >= Leste
            print(f"❌ ERRO: Área CDS inválida - Oeste ({area_cds[1]}) >= Leste ({area_cds[3]})")
            return None

        # Verificação adicional: área deve cobrir completamente os setores
        sectors_bounds = study_area_gdf.total_bounds
        print(f"🏘️ Bounds dos setores: {sectors_bounds}")
        print(f"🌍 Bounds do clima: {climate_bbox}")
        
        # Verificar se a área climática cobre todos os setores
        if (climate_bbox[0] > sectors_bounds[0] or  # clima min_lon > setores min_lon
            climate_bbox[1] > sectors_bounds[1] or  # clima min_lat > setores min_lat
            climate_bbox[2] < sectors_bounds[2] or  # clima max_lon < setores max_lon
            climate_bbox[3] < sectors_bounds[3]):   # clima max_lat < setores max_lat
            print("⚠️ AVISO: Área climática pode não cobrir todos os setores completamente")
        else:
            print("✅ Área climática cobre completamente todos os setores")

        # --- Data Downloads ---
        date_config = settings.DATA_RANGES['monitoramento_dengue']
        time_interval = (date_config['start'], date_config['end'])
        s1_raw_path = paths.RAW_SENTINEL_DIR / f"{job_id}_s1.tiff"
        s2_raw_path = paths.RAW_SENTINEL_DIR / f"{job_id}_s2.tiff"
        climate_raw_path = paths.RAW_CLIMATE_DIR / f"{job_id}_era5.nc"
        auth_config = {"client_id": settings.SH_CLIENT_ID, "client_secret": settings.SH_CLIENT_SECRET}
        
        # Download Sentinel-1
        s1_result = safe_execute(download_and_save_sentinel_data, "Download de dados Sentinel-1", 
                                'S1', auth_config, sentinel_bbox, time_interval, s1_raw_path, job_id=job_id)
        if s1_result is None or not s1_raw_path.exists():
            print(f"❌ Falha no download do Sentinel-1. Arquivo {s1_raw_path} não encontrado. Encerrando pipeline.")
            return None
        # Validar arquivo TIFF
        try:
            with rasterio.open(s1_raw_path) as src:
                print(f"✅ Arquivo {s1_raw_path} válido com {src.count} bandas.")
        except Exception as e:
            print(f"❌ Arquivo {s1_raw_path} corrompido ou inválido: {str(e)}")
            return None
        
        # Download Sentinel-2
        s2_result = safe_execute(download_and_save_sentinel_data, "Download de dados Sentinel-2", 
                                'S2', auth_config, sentinel_bbox, time_interval, s2_raw_path, job_id=job_id)
        if s2_result is None or not s2_raw_path.exists():
            print(f"❌ Falha no download do Sentinel-2. Arquivo {s2_raw_path} não encontrado. Encerrando pipeline.")
            return None
        # Validar arquivo TIFF
        try:
            with rasterio.open(s2_raw_path) as src:
                print(f"✅ Arquivo {s2_raw_path} válido com {src.count} bandas.")
        except Exception as e:
            print(f"❌ Arquivo {s2_raw_path} corrompido ou inválido: {str(e)}")
            return None
        
        # Download ERA5-Land (com área MUITO expandida)
        year, month = date_config['start'][:4], date_config['start'][5:7]
        days = [str(d).zfill(2) for d in range(1, monthrange(int(year), int(month))[1] + 1)]
        safe_execute(download_era5_land_data, "Download de dados climáticos ERA5", 
                    ['total_precipitation', '2m_temperature'], year, month, days, ['00:00', '12:00'], area_cds, climate_raw_path)
    
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
        
        print(f"✅ [PIPELINE-SUCCESS] Pipeline de processamento concluído! Arquivo criado: {final_features_path}")
        
    else:
        print(f"\n⚡ [PIPELINE] Pulando downloads e processamento. Usando arquivo de features existente: {final_features_path}")
        
        # Verificação final de segurança
        if not final_features_path.exists():
            error_msg = f"ERRO CRÍTICO: Arquivo de features ainda não existe após o processamento: {final_features_path}"
            print(f"❌ [PIPELINE-ERROR] {error_msg}")
            raise FileNotFoundError(error_msg)

    # --- Verificação de integridade do arquivo ---
    try:
        features_df = pd.read_csv(final_features_path)
        if features_df.empty:
            raise ValueError("Arquivo de features está vazio")
        print(f"✅ [PIPELINE-INFO] Arquivo de features carregado com sucesso. Shape: {features_df.shape}")
        print(f"📊 [PIPELINE-INFO] Colunas disponíveis: {list(features_df.columns)}")
    except Exception as e:
        error_msg = f"Erro ao carregar arquivo de features {final_features_path}: {str(e)}"
        print(f"❌ [PIPELINE-ERROR] {error_msg}")
        raise Exception(error_msg)

    # --- Baseline Risk Calculation ---
    print("\n🎯 === CALCULANDO SCORES DE RISCO ===")
    baseline_risk_df = safe_execute(calculate_risk_score, "Cálculo do score de risco base", features_df)
    if baseline_risk_df is None:
        print("❌ Falha no cálculo do score de risco. Encerrando pipeline.")
        return None
    
    # Debug dos valores de risco calculados
    if 'risk_score' in baseline_risk_df.columns:
        risk_stats = baseline_risk_df['risk_score'].describe()
        print(f"📊 [PIPELINE-DEBUG] Estatísticas do risk_score:")
        print(f"   Min: {risk_stats['min']:.4f}")
        print(f"   Max: {risk_stats['max']:.4f}")
        print(f"   Média: {risk_stats['mean']:.4f}")
        print(f"   Mediana: {risk_stats['50%']:.4f}")
    
    if 'final_risk_level' in baseline_risk_df.columns:
        risk_distribution = baseline_risk_df['final_risk_level'].value_counts()
        print(f"📊 [PIPELINE-DEBUG] Distribuição de níveis de risco:")
        for level, count in risk_distribution.items():
            percentage = (count / len(baseline_risk_df)) * 100
            print(f"   {level}: {count} setores ({percentage:.1f}%)")

    # --- Pool Detection ---
    detected_pools = []
    if not SKIP_POOL_DETECTION:
        detected_pools = safe_execute(find_pools_in_sectors, "Deteção de piscinas com Google Maps e IA",
                                      risk_sectors_gdf=study_area_gdf, api_key=os.getenv("Maps_API_KEY"),
                                      raw_images_dir=output_dir / "google_raw_images",
                                      detected_images_dir=output_dir / "google_detected_images",
                                      confidence_threshold=CONFIDENCE_THRESHOLD)
        if detected_pools is None:
            detected_pools = []
    else:
        print("\n⏭️ [PIPELINE] Pulando etapa de DETECÇÃO DE PISCINAS (SKIP_POOL_DETECTION=True).")
    
    print("\n🔗 === CONSOLIDANDO DADOS PARA O MAPA ===")
    
    # Merge dos dados de risco com os setores geográficos
    final_risk_gdf = study_area_gdf.merge(baseline_risk_df, on='CD_SETOR', how='left')
    print(f"📊 [PIPELINE-DEBUG] Merge realizado. Shape final: {final_risk_gdf.shape}")
    
    # Processa dados das piscinas
    pools_df = pd.DataFrame(detected_pools)
    
    if not pools_df.empty:
        pool_counts = pools_df.groupby('sector_id').size().reset_index(name='dirty_pool_count')
        pool_counts['sector_id'] = pool_counts['sector_id'].astype(np.int64)
        final_risk_gdf = final_risk_gdf.merge(pool_counts, left_on='CD_SETOR', right_on='sector_id', how='left')
        print(f"✅ [PIPELINE-INFO] Piscinas processadas e adicionadas ao GeoDataFrame")
    
    # Garante que dirty_pool_count existe
    if 'dirty_pool_count' not in final_risk_gdf.columns:
        final_risk_gdf['dirty_pool_count'] = 0
    final_risk_gdf['dirty_pool_count'] = final_risk_gdf['dirty_pool_count'].fillna(0)
    
    if 'risk_score' not in final_risk_gdf.columns:
        print("⚠️ [PIPELINE-WARNING] Coluna risk_score não encontrada no GeoDataFrame final")
        final_risk_gdf['risk_score'] = 0.5  # Valor padrão
    
    final_risk_gdf['risk_score'] = final_risk_gdf['risk_score'].fillna(0.5)
    
    # Cria amplified_risk_score (pode ser usado para priorização)
    final_risk_gdf['amplified_risk_score'] = (
        final_risk_gdf['risk_score'] + 
        (final_risk_gdf['dirty_pool_count'] * RISK_AMPLIFICATION_FACTOR)
    ).clip(0, 1)
    
    # Isso mantém a porcentagem de risco "pura" baseada apenas nos fatores ambientais
    conditions = [
        final_risk_gdf['risk_score'] > 0.75, 
        final_risk_gdf['risk_score'] > 0.50
    ]
    choices = ['Alto', 'Médio']
    final_risk_gdf['risk_level'] = np.select(conditions, choices, default='Baixo')
    
    if 'final_risk_level' not in final_risk_gdf.columns:
        final_risk_gdf['final_risk_level'] = final_risk_gdf['risk_level']
    
    # Debug final dos dados
    print(f"🎯 [PIPELINE-FINAL-DEBUG] Dados finais preparados:")
    print(f"   Total de setores: {len(final_risk_gdf)}")
    print(f"   Range risk_score: {final_risk_gdf['risk_score'].min():.3f} - {final_risk_gdf['risk_score'].max():.3f}")
    print(f"   Média risk_score: {final_risk_gdf['risk_score'].mean():.3f}")
    
    if 'final_risk_level' in final_risk_gdf.columns:
        final_distribution = final_risk_gdf['final_risk_level'].value_counts()
        print(f"   Distribuição final:")
        for level, count in final_distribution.items():
            print(f"      {level}: {count} setores")

    # Prepara dados das piscinas para o mapa
    pools_gdf = None
    if not pools_df.empty:
        pools_gdf = gpd.GeoDataFrame(pools_df, geometry=gpd.points_from_xy(pools_df.pool_lon, pools_df.pool_lat), crs="EPSG:4326")
        pools_gdf = pools_gdf.merge(final_risk_gdf[['CD_SETOR', 'final_risk_level']], left_on='sector_id', right_on='CD_SETOR', how='left')

    # --- Geração do Mapa com Porcentagem de Risco ---
    print("\n🗺️ === GERANDO MAPA INTERATIVO ===")
    map_path = output_dir / "mapa_de_risco_e_priorizacao.html"
    map_success = safe_execute(create_priority_map, "Geração do mapa interativo final",
                 sectors_risk_gdf=final_risk_gdf, dirty_pools_gdf=pools_gdf, output_html_path=map_path)
    
    if not map_success:
        print("⚠️ [PIPELINE-WARNING] Falha na geração do mapa, mas continuando...")

    # --- Summary Generation for Frontend ---
    print("\n📋 === GERANDO RESUMO FINAL ===")
    summary_path = output_dir / "summary.json"
    
    # Calcula estatísticas para o resumo
    avg_ndvi = final_risk_gdf['ndvi_mean'].mean() if 'ndvi_mean' in final_risk_gdf.columns else np.nan
    avg_temp_k = final_risk_gdf['t2m_mean'].mean() if 't2m_mean' in final_risk_gdf.columns else np.nan
    avg_precip_m = final_risk_gdf['tp_mean'].mean() if 'tp_mean' in final_risk_gdf.columns else np.nan
    
    risk_distribution = {}
    if 'final_risk_level' in final_risk_gdf.columns:
        risk_distribution = final_risk_gdf['final_risk_level'].value_counts().to_dict()
    
    # Calcula estatísticas de risco
    avg_risk_percentage = final_risk_gdf['risk_score'].mean() * 100 if 'risk_score' in final_risk_gdf.columns else 0
    max_risk_percentage = final_risk_gdf['risk_score'].max() * 100 if 'risk_score' in final_risk_gdf.columns else 0
    
    summary_data = {
        "map_url": str(Path(map_path).relative_to(Path.cwd())).replace('\\', '/'),
        "summary_url": str(Path(summary_path).relative_to(Path.cwd())).replace('\\', '/'),
        "total_sectors": int(len(final_risk_gdf)),
        "dirty_pools_found": int(len(detected_pools)),
        "risk_distribution": {k: int(v) for k, v in risk_distribution.items()},
        "avg_risk_percentage": f"{avg_risk_percentage:.1f}%",
        "max_risk_percentage": f"{max_risk_percentage:.1f}%", 
        "avg_ndvi": f"{avg_ndvi:.3f}" if pd.notna(avg_ndvi) else "N/D",
        "avg_temp_celsius": f"{avg_temp_k:.1f}" if pd.notna(avg_temp_k) else "N/D",
        "total_precip_mm": f"{avg_precip_m * 1000 * 30:.1f}" if pd.notna(avg_precip_m) else "N/D",
        # Informações adicionais para debug
        "risk_score_stats": {
            "min": float(final_risk_gdf['risk_score'].min()) if 'risk_score' in final_risk_gdf.columns else 0,
            "max": float(final_risk_gdf['risk_score'].max()) if 'risk_score' in final_risk_gdf.columns else 0,
            "mean": float(final_risk_gdf['risk_score'].mean()) if 'risk_score' in final_risk_gdf.columns else 0
        }
    }
    
    # Salva o resumo
    with open(summary_path, 'w') as f:
        json.dump(summary_data, f, indent=4)
    
    print(f"🎉 [PIPELINE-FINAL] Pipeline concluído com sucesso!")
    print(f"📊 [PIPELINE-FINAL] Resumo: {len(final_risk_gdf)} setores, {len(detected_pools)} piscinas detectadas")
    print(f"🎯 [PIPELINE-FINAL] Risco médio: {avg_risk_percentage:.1f}% (máximo: {max_risk_percentage:.1f}%)")
    print(f"🗺️ [PIPELINE-FINAL] Mapa salvo em: {map_path}")
    
    # Salva dados finais para debug (opcional)
    debug_data_path = output_dir / "debug_map_data.csv"
    try:
        # Salva apenas colunas essenciais para debug
        debug_columns = ['CD_SETOR', 'risk_score', 'final_risk_level', 'dirty_pool_count']
        available_columns = [col for col in debug_columns if col in final_risk_gdf.columns]
        
        debug_df = final_risk_gdf[available_columns].copy()
        debug_df.to_csv(debug_data_path, index=False)
        print(f"🔍 [PIPELINE-DEBUG] Dados de debug salvos em: {debug_data_path}")
        
    except Exception as e:
        print(f"⚠️ [PIPELINE-WARNING] Erro ao salvar dados de debug: {e}")
        
    return summary_data