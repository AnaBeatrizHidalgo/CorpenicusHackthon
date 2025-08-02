#!/usr/bin/env python3
"""
Script de debug para identificar problemas nos dados do projeto NAIA
"""
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def analyze_csv_file(file_path, file_name):
    """Analisa um arquivo CSV e identifica problemas"""
    logger.info(f"\n{'='*50}")
    logger.info(f"ANALISANDO: {file_name}")
    logger.info(f"Caminho: {file_path}")
    
    try:
        if not Path(file_path).exists():
            logger.error(f"Arquivo não encontrado: {file_path}")
            return
        
        # Carrega o arquivo
        df = pd.read_csv(file_path)
        logger.info(f"Shape: {df.shape}")
        logger.info(f"Colunas: {list(df.columns)}")
        
        # Verifica colunas duplicadas
        duplicate_cols = df.columns[df.columns.duplicated()].tolist()
        if duplicate_cols:
            logger.warning(f"Colunas duplicadas encontradas: {duplicate_cols}")
        
        # Analisa cada coluna
        for col in df.columns:
            logger.info(f"\n--- Coluna: {col} ---")
            logger.info(f"Tipo: {df[col].dtype}")
            logger.info(f"Valores únicos: {df[col].nunique()}")
            logger.info(f"Valores nulos: {df[col].isnull().sum()}")
            logger.info(f"Valores vazios (''): {(df[col] == '').sum()}")
            
            # Se é numérica, mostra estatísticas
            if df[col].dtype in ['int64', 'float64']:
                logger.info(f"Min-Max: {df[col].min()} - {df[col].max()}")
                logger.info(f"Média: {df[col].mean():.3f}")
                
                # Verifica valores infinitos
                inf_count = np.isinf(df[col]).sum()
                if inf_count > 0:
                    logger.warning(f"Valores infinitos: {inf_count}")
            
            # Mostra amostra dos valores
            sample_values = df[col].dropna().head(3).tolist()
            logger.info(f"Amostra: {sample_values}")
        
        # Verifica ID principal
        if 'CD_SETOR' in df.columns:
            logger.info(f"\n--- Análise CD_SETOR ---")
            logger.info(f"Tipo: {df['CD_SETOR'].dtype}")
            logger.info(f"Valores únicos: {df['CD_SETOR'].nunique()}")
            logger.info(f"Duplicados: {df['CD_SETOR'].duplicated().sum()}")
            logger.info(f"Amostra: {df['CD_SETOR'].head(3).tolist()}")
        
        return df
        
    except Exception as e:
        logger.error(f"Erro ao analisar {file_name}: {e}")
        return None

def analyze_geojson_file(file_path, file_name):
    """Analisa um arquivo GeoJSON"""
    logger.info(f"\n{'='*50}")
    logger.info(f"ANALISANDO GEOJSON: {file_name}")
    
    try:
        if not Path(file_path).exists():
            logger.error(f"Arquivo não encontrado: {file_path}")
            return
        
        gdf = gpd.read_file(file_path)
        logger.info(f"Shape: {gdf.shape}")
        logger.info(f"CRS: {gdf.crs}")
        logger.info(f"Colunas: {list(gdf.columns)}")
        
        # Verifica geometrias
        logger.info(f"\n--- Análise Geometrias ---")
        logger.info(f"Geometrias válidas: {gdf.geometry.is_valid.sum()}")
        logger.info(f"Geometrias inválidas: {(~gdf.geometry.is_valid).sum()}")
        logger.info(f"Geometrias nulas: {gdf.geometry.isnull().sum()}")
        
        if not gdf.geometry.isnull().all():
            bounds = gdf.total_bounds
            logger.info(f"Bounds: {bounds}")
            center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
            logger.info(f"Centro: {center}")
        
        # Verifica outras colunas importantes
        important_cols = ['CD_SETOR', 'risk_score', 'final_risk_level', 'dirty_pool_count']
        for col in important_cols:
            if col in gdf.columns:
                logger.info(f"\n--- {col} ---")
                logger.info(f"Tipo: {gdf[col].dtype}")
                logger.info(f"Nulos: {gdf[col].isnull().sum()}")
                if gdf[col].dtype in ['int64', 'float64']:
                    logger.info(f"Range: {gdf[col].min()} - {gdf[col].max()}")
                logger.info(f"Amostra: {gdf[col].head(3).tolist()}")
        
        return gdf
        
    except Exception as e:
        logger.error(f"Erro ao analisar GeoJSON {file_name}: {e}")
        return None

def main():
    """Função principal de debug"""
    logger.info("🔍 INICIANDO DEBUG DOS DADOS DO PROJETO NAIA")
    
    # Define caminhos base
    base_dir = Path(".")
    output_dir = base_dir / "output" / "analysis_-22.818_-47.069"
    
    # Lista de arquivos para analisar
    files_to_analyze = [
        ("final_features.csv", "CSV com features finais"),
        ("image_features.csv", "CSV com features de imagem"),
        ("climate_features.csv", "CSV com features climáticas"),
        ("debug_map_data.csv", "CSV de debug do mapa"),
    ]
    
    geojson_files = [
        ("area_of_interest.geojson", "Área de interesse"),
        ("final_risk_data.geojson", "Dados finais de risco"),
        ("detected_pools.geojson", "Piscinas detectadas"),
    ]
    
    # Analisa arquivos CSV
    for filename, description in files_to_analyze:
        file_path = output_dir / filename
        if not file_path.exists():
            file_path = base_dir / filename  # Tenta na raiz também
        
        logger.info(f"\n🔎 Analisando: {description}")
        df = analyze_csv_file(file_path, filename)
    
    # Analisa arquivos GeoJSON
    for filename, description in geojson_files:
        file_path = output_dir / filename
        logger.info(f"\n🗺️  Analisando: {description}")
        gdf = analyze_geojson_file(file_path, filename)
    
    # Análise específica dos problemas identificados
    logger.info(f"\n{'='*50}")
    logger.info("🔧 ANÁLISE DE PROBLEMAS ESPECÍFICOS")
    
    # Problema 1: Colunas climáticas vazias
    climate_path = output_dir / "climate_features.csv"
    if climate_path.exists():
        climate_df = pd.read_csv(climate_path)
        tp_empty = climate_df['tp_mean'].isnull().all() if 'tp_mean' in climate_df.columns else True
        t2m_empty = climate_df['t2m_mean'].isnull().all() if 't2m_mean' in climate_df.columns else True
        
        logger.warning(f"Problema identificado - Dados climáticos:")
        logger.warning(f"  tp_mean (precipitação) vazio: {tp_empty}")
        logger.warning(f"  t2m_mean (temperatura) vazio: {t2m_empty}")
        
        if tp_empty or t2m_empty:
            logger.info("💡 SOLUÇÃO: Os dados climáticos não foram baixados corretamente.")
            logger.info("   Verifique a configuração da API do Copernicus CDS.")
    
    # Problema 2: Colunas duplicadas no debug_map_data.csv
    debug_path = output_dir / "debug_map_data.csv"
    if not debug_path.exists():
        debug_path = base_dir / "debug_map_data.csv"
    
    if debug_path.exists():
        debug_df = pd.read_csv(debug_path)
        risk_score_cols = [col for col in debug_df.columns if 'risk_score' in col]
        
        if len(risk_score_cols) > 1:
            logger.warning(f"Problema identificado - Colunas duplicadas:")
            logger.warning(f"  Colunas risk_score: {risk_score_cols}")
            logger.info("💡 SOLUÇÃO: Remover colunas duplicadas antes da geração do mapa.")
    
    # Problema 3: Verificação dos tipos de dados
    final_features_path = output_dir / "final_features.csv"
    if not final_features_path.exists():
        final_features_path = base_dir / "final_features.csv"
    
    if final_features_path.exists():
        features_df = pd.read_csv(final_features_path)
        
        logger.info(f"\n🔍 Verificação de consistência dos dados:")
        logger.info(f"  CD_SETOR único: {features_df['CD_SETOR'].nunique()}")
        logger.info(f"  Setores com NDVI: {features_df['ndvi_mean'].notna().sum()}")
        logger.info(f"  Setores com dados S1: {features_df[['vv_mean', 'vh_mean']].notna().all(axis=1).sum()}")
        logger.info(f"  Setores com dados climáticos: {features_df[['tp_mean', 't2m_mean']].notna().all(axis=1).sum()}")
    
    logger.info(f"\n{'='*50}")
    logger.info("🎯 RESUMO DOS PROBLEMAS ENCONTRADOS:")
    logger.info("1. Dados climáticos (tp_mean, t2m_mean) estão vazios")
    logger.info("2. Possíveis colunas duplicadas (risk_score)")
    logger.info("3. Tipos de dados inconsistentes")
    logger.info("\n💡 Use o script run_analysis_fixed_complete.py para corrigir esses problemas!")

if __name__ == "__main__":
    main()