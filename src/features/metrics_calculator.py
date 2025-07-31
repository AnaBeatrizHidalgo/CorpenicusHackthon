# src/features/metrics_calculator.py
"""
Módulo para calcular métricas a partir das imagens recortadas e unir todas as
fontes de features em um único arquivo.
"""
import logging
from pathlib import Path
import rasterio
import numpy as np
import pandas as pd
from tqdm import tqdm

def calculate_image_metrics(
    s1_images_dir: Path,
    s2_images_dir: Path,
    output_path: Path
):
    """
    Calcula métricas (NDVI, VV, VH) para cada setor a partir das imagens recortadas.

    Args:
        s1_images_dir (Path): Diretório com as imagens Sentinel-1 recortadas.
        s2_images_dir (Path): Diretório com as imagens Sentinel-2 recortadas.
        output_path (Path): Caminho para salvar o CSV com as métricas de imagem.
    """
    logging.info("Iniciando cálculo de métricas a partir das imagens de satélite.")
    
    # Encontra todos os arquivos de imagem recortados
    s1_files = list(s1_images_dir.glob("*_sector_*.tiff"))
    s2_files = list(s2_images_dir.glob("*_sector_*.tiff"))
    
    if not s1_files and not s2_files:
        logging.warning("Nenhuma imagem recortada encontrada para processar.")
        return

    all_metrics = []

    # Processa Sentinel-2 (NDVI)
    logging.info(f"Processando {len(s2_files)} imagens de Sentinel-2 para cálculo de NDVI.")
    for f in tqdm(s2_files, desc="Calculando NDVI"):
        try:
            sector_id = int(f.stem.split('_sector_')[-1])
            with rasterio.open(f) as src:
                # S2: [B04 (Red), B03 (Green), B02 (Blue), B08 (NIR)]
                # O evalscript já ordenou para [Red, Green, Blue, NIR]
                red = src.read(1).astype(float)
                nir = src.read(4).astype(float)
                
                # Evita divisão por zero
                np.seterr(divide='ignore', invalid='ignore')
                ndvi = np.where((nir + red) > 0, (nir - red) / (nir + red), 0)
                
                # Remove valores infinitos ou nulos antes de calcular a média
                ndvi_mean = np.nanmean(ndvi[np.isfinite(ndvi)])

                all_metrics.append({'CD_SETOR': sector_id, 'ndvi_mean': ndvi_mean})
        except Exception as e:
            logging.error(f"Erro ao processar o arquivo {f.name}: {e}")
            continue

    # Processa Sentinel-1 (VV, VH)
    logging.info(f"Processando {len(s1_files)} imagens de Sentinel-1 para backscatter.")
    for f in tqdm(s1_files, desc="Calculando Backscatter"):
        try:
            sector_id = int(f.stem.split('_sector_')[-1])
            with rasterio.open(f) as src:
                vv = src.read(1).astype(float)
                vh = src.read(2).astype(float)
                
                # Calcula a média, ignorando valores nulos (geralmente NoData)
                vv_mean = np.nanmean(vv[vv != src.nodata])
                vh_mean = np.nanmean(vh[vh != src.nodata])

                # Adiciona ou atualiza o dicionário na lista
                found = False
                for item in all_metrics:
                    if item['CD_SETOR'] == sector_id:
                        item.update({'vv_mean': vv_mean, 'vh_mean': vh_mean})
                        found = True
                        break
                if not found:
                    all_metrics.append({'CD_SETOR': sector_id, 'vv_mean': vv_mean, 'vh_mean': vh_mean})
        except Exception as e:
            logging.error(f"Erro ao processar o arquivo {f.name}: {e}")
            continue
    
    # Salva o resultado em um CSV
    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(output_path, index=False)
    logging.info(f"Métricas de imagem salvas com sucesso em: {output_path}")
    return metrics_df


def merge_features(
    climate_features_path: Path,
    image_features_path: Path,
    output_path: Path
):
    """
    Une as features climáticas e de imagem em um único arquivo.

    Args:
        climate_features_path (Path): Caminho para o CSV de features climáticas.
        image_features_path (Path): Caminho para o CSV de features de imagem.
        output_path (Path): Caminho para salvar o CSV final com todas as features.
    """
    logging.info("Unindo features climáticas e de imagem.")
    try:
        climate_df = pd.read_csv(climate_features_path)
        image_df = pd.read_csv(image_features_path)

        # Garante que a coluna de junção seja do mesmo tipo
        climate_df['CD_SETOR'] = climate_df['CD_SETOR'].astype(int)
        image_df['CD_SETOR'] = image_df['CD_SETOR'].astype(int)

        # Une os dois DataFrames
        final_df = pd.merge(climate_df, image_df, on='CD_SETOR', how='left')
        
        final_df.to_csv(output_path, index=False)
        logging.info(f"Arquivo de features final salvo com sucesso em: {output_path}")
    except Exception as e:
        logging.error(f"Falha ao unir os arquivos de features: {e}", exc_info=True)
        raise