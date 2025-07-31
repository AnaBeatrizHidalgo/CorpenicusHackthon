import logging
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd
import numpy as np
from calendar import monthrange
import traceback

# --- 1. Imports de TODOS os Módulos do Projeto ---
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


SKIP_POOL_DETECTION = True
SKIP_SENTINEL_DOWNLOAD = True


def setup_logging():
    """Configura logging com mais detalhes para debug"""
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('analysis.log')
        ]
    )
    return logging.getLogger(__name__)

def safe_execute(func, description, logger, *args, **kwargs):
    """Executa uma função com tratamento de erro"""
    try:
        logger.info(f"Iniciando: {description}")
        result = func(*args, **kwargs)
        logger.info(f"Concluído: {description}")
        return result
    except Exception as e:
        logger.error(f"Erro em {description}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def clean_dataframe_for_geojson(gdf, logger):
    """Limpa o GeoDataFrame para exportação GeoJSON"""
    logger.info("Limpando GeoDataFrame para exportação...")
    
    clean_gdf = gdf.copy()
    
    # Remove colunas duplicadas
    duplicate_cols = []
    seen_cols = set()
    for col in clean_gdf.columns:
        if col in seen_cols:
            duplicate_cols.append(col)
        else:
            seen_cols.add(col)
    
    if duplicate_cols:
        logger.warning(f"Removendo colunas duplicadas: {duplicate_cols}")
        # Remove duplicatas mantendo apenas a primeira ocorrência
        clean_gdf = clean_gdf.loc[:, ~clean_gdf.columns.duplicated()]
    
    # Converte colunas categóricas para string
    for col in clean_gdf.columns:
        if hasattr(clean_gdf[col], 'cat'):
            logger.info(f"Convertendo coluna categórica '{col}' para string")
            clean_gdf[col] = clean_gdf[col].astype(str)
        elif clean_gdf[col].dtype == 'object':
            # Converte objetos para string para evitar problemas
            try:
                clean_gdf[col] = clean_gdf[col].astype(str)
            except:
                pass
    
    # Garante que CD_SETOR seja string
    if 'CD_SETOR' in clean_gdf.columns:
        clean_gdf['CD_SETOR'] = clean_gdf['CD_SETOR'].astype(str)
    
    # Limpa valores infinitos e NaN problemáticos
    numeric_columns = clean_gdf.select_dtypes(include=[np.number]).columns
    for col in numeric_columns:
        # Substitui infinitos por NaN
        clean_gdf[col] = clean_gdf[col].replace([np.inf, -np.inf], np.nan)
        # Preenche NaN com 0 para colunas de risco
        if 'risk' in col.lower() or 'score' in col.lower():
            clean_gdf[col] = clean_gdf[col].fillna(0.5)
        elif 'count' in col.lower():
            clean_gdf[col] = clean_gdf[col].fillna(0)
    
    logger.info(f"GeoDataFrame limpo. Shape: {clean_gdf.shape}, Colunas: {list(clean_gdf.columns)}")
    return clean_gdf

def prepare_map_data(final_risk_gdf, logger):
    """Prepara os dados especificamente para o mapa"""
    logger.info("Preparando dados para o mapa...")
    
    map_gdf = final_risk_gdf.copy()
    
    # Identifica se há colunas duplicadas de risk_score
    risk_score_cols = [col for col in map_gdf.columns if 'risk_score' in col]
    logger.info(f"Colunas de risk_score encontradas: {risk_score_cols}")
    
    # Se há múltiplas colunas de risk_score, usa a última (mais processada)
    if len(risk_score_cols) > 1:
        # Remove todas exceto a última
        for col in risk_score_cols[:-1]:
            logger.info(f"Removendo coluna duplicada: {col}")
            map_gdf = map_gdf.drop(columns=[col], errors='ignore')
        
        # Renomeia a última para 'risk_score' se necessário
        final_risk_col = risk_score_cols[-1]
        if final_risk_col != 'risk_score':
            map_gdf = map_gdf.rename(columns={final_risk_col: 'risk_score'})
            logger.info(f"Renomeando {final_risk_col} para risk_score")
    
    # Garante que risk_score existe e é numérico
    if 'risk_score' not in map_gdf.columns:
        logger.warning("Coluna risk_score não encontrada, criando com valores padrão")
        map_gdf['risk_score'] = 0.5
    
    # Limpa a coluna risk_score
    map_gdf['risk_score'] = pd.to_numeric(map_gdf['risk_score'], errors='coerce').fillna(0.5)
    
    # Garante que o score está entre 0 e 1
    map_gdf['risk_score'] = map_gdf['risk_score'].clip(0, 1)
    
    # Limpa outras colunas essenciais
    if 'CD_SETOR' in map_gdf.columns:
        map_gdf['CD_SETOR'] = map_gdf['CD_SETOR'].astype(str)
    
    if 'dirty_pool_count' not in map_gdf.columns:
        map_gdf['dirty_pool_count'] = 0
    else:
        map_gdf['dirty_pool_count'] = pd.to_numeric(map_gdf['dirty_pool_count'], errors='coerce').fillna(0)
    
    # Garante que final_risk_level existe
    if 'final_risk_level' not in map_gdf.columns:
        # Cria baseado no risk_score
        map_gdf['final_risk_level'] = pd.cut(
            map_gdf['risk_score'],
            bins=[0, 0.33, 0.66, 1.0],
            labels=['Baixo', 'Médio', 'Alto'],
            include_lowest=True
        ).astype(str)
    
    logger.info(f"Dados do mapa preparados. Shape: {map_gdf.shape}")
    logger.info(f"Range do risk_score: {map_gdf['risk_score'].min():.3f} - {map_gdf['risk_score'].max():.3f}")
    
    return map_gdf

# --- 2. Bloco Principal de Execução ---
if __name__ == "__main__":
    logger = setup_logging()
    
    try:
        from dotenv import load_dotenv
        load_dotenv()

        # --- 3. PARÂMETROS DA ANÁLISE ---
        CENTER_LAT = -22.818
        CENTER_LON = -47.069
        AREA_SIZE_KM = 3.0
        NATIONAL_SHAPEFILE_PATH = Path("data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp")
        CONFIDENCE_THRESHOLD = 0.3
        RISK_AMPLIFICATION_FACTOR = 0.2

        # --- 4. SETUP DA EXECUÇÃO ---
        output_dir = paths.OUTPUT_DIR / f"analysis_{CENTER_LAT}_{CENTER_LON}"
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Resultados desta análise serão salvos em: {output_dir}")
        area_geojson_path = output_dir / "area_of_interest.geojson"
        
        study_area_gdf = safe_execute(
            create_study_area_geojson,
            "Criação da área de estudo",
            logger,
            NATIONAL_SHAPEFILE_PATH, CENTER_LAT, CENTER_LON, AREA_SIZE_KM, area_geojson_path
        )
        
        if study_area_gdf is None: 
            logger.error("Falha na criação da área de estudo. Encerrando.")
            exit(1)
            
        # Garante o tipo correto da coluna de ID desde o início
        study_area_gdf['CD_SETOR'] = study_area_gdf['CD_SETOR'].astype(np.int64)
        logger.info(f"Área de estudo criada com {len(study_area_gdf)} setores")

        # --- 5. MACRO-ANÁLISE: DOWNLOAD SENTINEL ---
        bbox = list(study_area_gdf.total_bounds)
        date_config = settings.DATA_RANGES['monitoramento_dengue']
        time_interval = (date_config['start'], date_config['end'])
        s1_raw_path = paths.RAW_SENTINEL_DIR / f"{output_dir.name}_s1.tiff"
        s2_raw_path = paths.RAW_SENTINEL_DIR / f"{output_dir.name}_s2.tiff"
        auth_config = {"client_id": settings.SH_CLIENT_ID, "client_secret": settings.SH_CLIENT_SECRET}

        if not SKIP_SENTINEL_DOWNLOAD:
            safe_execute(
                download_and_save_sentinel_data,
                "Download Sentinel-1",
                logger,
                'S1', auth_config, bbox, time_interval, s1_raw_path
            )

            safe_execute(
                download_and_save_sentinel_data,
                "Download Sentinel-2",
                logger,
                'S2', auth_config, bbox, time_interval, s2_raw_path
            )
        else:
            logger.warning("Download Sentinel PULADO manualmente.")

        # --- 6. MACRO-ANÁLISE: DOWNLOAD CLIMA ---
        year, month = date_config['start'][:4], date_config['start'][5:7]
        days = [str(d).zfill(2) for d in range(1, monthrange(int(year), int(month))[1] + 1)]
        area_cds = [bbox[3], bbox[0], bbox[1], bbox[2]]
        climate_raw_path = paths.RAW_CLIMATE_DIR / f"{output_dir.name}_era5.nc"
        
        safe_execute(
            download_era5_land_data,
            "Download dados climáticos",
            logger,
            ['total_precipitation', '2m_temperature'], year, month, days, ['00:00', '12:00'], area_cds, climate_raw_path
        )

        # --- 7. MACRO-ANÁLISE: PROCESSAMENTO E EXTRAÇÃO DE FEATURES ---
        s1_processed_dir = output_dir / "processed_images/sentinel-1"
        s2_processed_dir = output_dir / "processed_images/sentinel-2"
        
        safe_execute(
            clip_raster_by_sectors,
            "Processamento Sentinel-1",
            logger,
            s1_raw_path, area_geojson_path, s1_processed_dir
        )
        
        safe_execute(
            clip_raster_by_sectors,
            "Processamento Sentinel-2",
            logger,
            s2_raw_path, area_geojson_path, s2_processed_dir
        )
        
        climate_features_path = output_dir / "climate_features.csv"
        safe_execute(
            aggregate_climate_by_sector,
            "Agregação de features climáticas",
            logger,
            climate_raw_path, area_geojson_path, climate_features_path
        )
        
        image_features_path = output_dir / "image_features.csv"
        safe_execute(
            calculate_image_metrics,
            "Cálculo de métricas de imagem",
            logger,
            s1_processed_dir, s2_processed_dir, image_features_path
        )
        
        final_features_path = output_dir / "final_features.csv"
        safe_execute(
            merge_features,
            "Merge de features",
            logger,
            climate_features_path, image_features_path, final_features_path
        )

        # --- 8. MACRO-ANÁLISE: CÁLCULO DE RISCO BASE ---
        features_df = pd.read_csv(final_features_path)
        baseline_risk_df = safe_execute(
            calculate_risk_score,
            "Cálculo de risco base",
            logger,
            features_df
        )
        
        # --- 9. DETECÇÃO DE PISCINAS (OPCIONAL) ---
        if not SKIP_POOL_DETECTION:
            logger.info("Iniciando a microanálise de criadouros em TODOS os setores.")
            api_key = os.getenv("Maps_API_KEY")
            if not api_key:
                logger.error("API key do Google Maps não encontrada. Encerrando.")
                exit(1)

            try:
                detected_pools = find_pools_in_sectors(
                    risk_sectors_gdf=study_area_gdf, 
                    api_key=api_key,
                    raw_images_dir=output_dir / "google_raw_images",
                    detected_images_dir=output_dir / "google_detected_images",
                    confidence_threshold=CONFIDENCE_THRESHOLD
                )
                logger.info(f"Detecção de piscinas concluída. {len(detected_pools)} piscinas detectadas.")
            except Exception as e:
                logger.error(f"Erro na detecção de piscinas: {str(e)}")
                logger.warning("Continuando sem dados de piscinas...")
                detected_pools = []
        else:
            logger.warning("Detecção de piscinas PULADA manualmente.")
            detected_pools = []

        # --- 10. CONSOLIDAÇÃO E AMPLIFICAÇÃO DE RISCO ---
        logger.info("Iniciando consolidação e amplificação de risco")
        
        # Começamos com o GeoDataFrame base limpo
        final_risk_gdf = study_area_gdf.copy()
        
        # Adiciona os scores de risco base
        baseline_risk_df['CD_SETOR'] = baseline_risk_df['CD_SETOR'].astype(np.int64)
        final_risk_gdf = final_risk_gdf.merge(baseline_risk_df, on='CD_SETOR', how='left')
        logger.info("Scores de risco base adicionados")

        # Adiciona a contagem de piscinas sujas
        pools_df = pd.DataFrame(detected_pools)
        if not pools_df.empty:
            logger.info(f"Processando {len(pools_df)} piscinas detectadas.")
            pool_counts = pools_df.groupby('sector_id').size().reset_index(name='dirty_pool_count')
            pool_counts['sector_id'] = pool_counts['sector_id'].astype(np.int64)
            
            final_risk_gdf = final_risk_gdf.merge(pool_counts, left_on='CD_SETOR', right_on='sector_id', how='left')
            final_risk_gdf.drop(columns=['sector_id'], inplace=True, errors='ignore')
        else:
            logger.info("Nenhuma piscina detectada. Adicionando zeros.")
            final_risk_gdf['dirty_pool_count'] = 0

        final_risk_gdf['dirty_pool_count'] = final_risk_gdf['dirty_pool_count'].fillna(0)

        # Calcula o score amplificado
        final_risk_gdf['amplified_risk_score'] = (
            final_risk_gdf['risk_score'] + 
            (final_risk_gdf['dirty_pool_count'] * RISK_AMPLIFICATION_FACTOR)
        )
        logger.info("Score de risco amplificado calculado.")
        
        # Classificação de risco final
        try:
            final_risk_gdf['final_risk_level'] = pd.cut(
                final_risk_gdf['amplified_risk_score'], 
                bins=[0, 0.33, 0.66, 1.0, 2.0],  # Aumenta o limite superior para acomodar amplificação
                labels=['Baixo', 'Médio', 'Alto', 'Crítico'], 
                include_lowest=True, 
                right=True
            ).astype(str)
            logger.info("Classificação de risco final aplicada.")
        except Exception as e:
            logger.error(f"Erro na classificação de risco: {str(e)}")
            final_risk_gdf['final_risk_level'] = 'Médio'

        # --- 11. PREPARAÇÃO DOS DADOS PARA O MAPA ---
        logger.info("Preparando dados para o mapa...")
        
        # Prepara o GeoDataFrame principal para o mapa
        map_gdf = prepare_map_data(final_risk_gdf, logger)
        
        # Prepara dados das piscinas
        pools_gdf = None
        if not pools_df.empty:
            try:
                pools_gdf = gpd.GeoDataFrame(
                    pools_df, 
                    geometry=gpd.points_from_xy(pools_df.pool_lon, pools_df.pool_lat), 
                    crs="EPSG:4326"
                )
                pools_gdf['sector_id'] = pools_gdf['sector_id'].astype(str)
                
                # Adiciona informações de risco às piscinas
                risk_info = map_gdf[['CD_SETOR', 'final_risk_level']].copy()
                risk_info['CD_SETOR'] = risk_info['CD_SETOR'].astype(str)
                
                pools_gdf = pools_gdf.merge(
                    risk_info, 
                    left_on='sector_id', 
                    right_on='CD_SETOR', 
                    how='left'
                ).rename(columns={'final_risk_level': 'risk_level'})
                
                logger.info(f"GeoDataFrame de piscinas criado com {len(pools_gdf)} pontos")
            except Exception as e:
                logger.error(f"Erro ao criar GeoDataFrame de piscinas: {str(e)}")
                pools_gdf = None

        # --- 12. SALVAMENTO DE DADOS INTERMEDIÁRIOS ---
        logger.info("Salvando dados intermediários...")
        try:
            # Limpa os dados antes de salvar
            clean_final_gdf = clean_dataframe_for_geojson(final_risk_gdf, logger)
            clean_final_gdf.to_file(output_dir / "final_risk_data.geojson", driver='GeoJSON')
            
            if pools_gdf is not None and not pools_gdf.empty:
                clean_pools_gdf = clean_dataframe_for_geojson(pools_gdf, logger)
                clean_pools_gdf.to_file(output_dir / "detected_pools.geojson", driver='GeoJSON')
                
            logger.info("Dados intermediários salvos com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar dados intermediários: {str(e)}")
            logger.info("Continuando com a geração do mapa...")

        # --- 13. GERAÇÃO DO MAPA FINAL ---
        logger.info("Iniciando geração do mapa final...")
        map_path = output_dir / "mapa_de_risco_e_priorizacao.html"
        
        try:
            # Última verificação dos dados
            logger.info(f"Dados do mapa - Shape: {map_gdf.shape}")
            logger.info(f"Colunas essenciais presentes: CD_SETOR={('CD_SETOR' in map_gdf.columns)}, "
                       f"risk_score={('risk_score' in map_gdf.columns)}, "
                       f"geometry={('geometry' in map_gdf.columns)}")
            
            if pools_gdf is not None:
                logger.info(f"Dados das piscinas - Shape: {pools_gdf.shape}")
            
            # Gera o mapa
            safe_execute(
                create_priority_map,
                "Geração do mapa final",
                logger,
                map_gdf, pools_gdf, map_path
            )
            logger.info(f"🎉 MAPA GERADO COM SUCESSO em: {map_path}")
            
        except Exception as e:
            logger.error(f"Erro na geração do mapa: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Tenta uma versão simplificada do mapa
            logger.info("Tentando gerar versão simplificada do mapa...")
            try:
                # Cria um mapa básico apenas com os setores
                simple_map_gdf = map_gdf[['CD_SETOR', 'risk_score', 'geometry']].copy()
                simple_map_gdf = clean_dataframe_for_geojson(simple_map_gdf, logger)
                
                create_priority_map(simple_map_gdf, None, map_path)
                logger.info(f"✅ Mapa simplificado gerado em: {map_path}")
                
            except Exception as e2:
                logger.error(f"Falha também na versão simplificada: {str(e2)}")

        # --- 14. RELATÓRIO FINAL ---
        logger.info("=== RELATÓRIO FINAL ===")
        logger.info(f"Setores analisados: {len(final_risk_gdf)}")
        logger.info(f"Piscinas detectadas: {len(detected_pools)}")
        
        if 'final_risk_level' in final_risk_gdf.columns:
            logger.info("Distribuição de risco:")
            risk_counts = final_risk_gdf['final_risk_level'].value_counts()
            for level, count in risk_counts.items():
                logger.info(f"  {level}: {count} setores")
        
        if 'amplified_risk_score' in final_risk_gdf.columns:
            score_stats = final_risk_gdf['amplified_risk_score'].describe()
            logger.info(f"Estatísticas do score de risco:")
            logger.info(f"  Média: {score_stats['mean']:.3f}")
            logger.info(f"  Min-Max: {score_stats['min']:.3f} - {score_stats['max']:.3f}")
        
        logger.info(f"Arquivos de saída em: {output_dir}")
        logger.info("🎯 ANÁLISE COMPLETA CONCLUÍDA COM SUCESSO!")

    except Exception as e:
        logger.error(f"💥 Erro crítico na execução: {str(e)}")
        logger.error(f"Traceback completo: {traceback.format_exc()}")
        exit(1)