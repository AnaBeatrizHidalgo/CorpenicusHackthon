# src/features/metrics_calculator.py
"""
Módulo para calcular métricas a partir das imagens recortadas e unir todas as
fontes de features em um único arquivo.
"""
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
    
    Returns:
        pd.DataFrame: DataFrame com as métricas calculadas.
    """
    print("🛰️ Iniciando cálculo de métricas a partir das imagens de satélite.")
    
    # Encontra todos os arquivos de imagem recortados
    s1_files = list(s1_images_dir.glob("*_sector_*.tiff"))
    s2_files = list(s2_images_dir.glob("*_sector_*.tiff"))
    
    print(f"📁 Encontrados {len(s1_files)} arquivos Sentinel-1")
    print(f"📁 Encontrados {len(s2_files)} arquivos Sentinel-2")
    
    if not s1_files and not s2_files:
        print("⚠️ Nenhuma imagem recortada encontrada para processar.")
        return pd.DataFrame()

    all_metrics = []

    # Processa Sentinel-2 (NDVI)
    if s2_files:
        print(f"🌱 Processando {len(s2_files)} imagens de Sentinel-2 para cálculo de NDVI.")
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
                print(f"❌ Erro ao processar o arquivo {f.name}: {e}")
                continue

    # Processa Sentinel-1 (VV, VH)
    if s1_files:
        print(f"📡 Processando {len(s1_files)} imagens de Sentinel-1 para backscatter.")
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
                print(f"❌ Erro ao processar o arquivo {f.name}: {e}")
                continue
    
    # Cria o DataFrame com todas as métricas
    if all_metrics:
        metrics_df = pd.DataFrame(all_metrics)
        
        # Garante que todos os setores tenham todas as colunas
        expected_columns = ['CD_SETOR', 'ndvi_mean', 'vv_mean', 'vh_mean']
        for col in expected_columns:
            if col not in metrics_df.columns:
                metrics_df[col] = np.nan
        
        # Reordena as colunas
        metrics_df = metrics_df[expected_columns]
        
        # Salva o resultado em um CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_df.to_csv(output_path, index=False)
        print(f"✅ Métricas de imagem salvas com sucesso em: {output_path}")
        print(f"📊 Total de setores processados: {len(metrics_df)}")
        
        return metrics_df
    else:
        print("⚠️ Nenhuma métrica foi calculada.")
        return pd.DataFrame()


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
    
    Returns:
        pd.DataFrame: DataFrame com todas as features unidas.
    """
    print("🔗 Unindo features climáticas e de imagem.")
    
    try:
        # Verifica se os arquivos existem
        if not climate_features_path.exists():
            print(f"❌ Arquivo de features climáticas não encontrado: {climate_features_path}")
            raise FileNotFoundError(f"Arquivo não encontrado: {climate_features_path}")
        
        if not image_features_path.exists():
            print(f"❌ Arquivo de features de imagem não encontrado: {image_features_path}")
            raise FileNotFoundError(f"Arquivo não encontrado: {image_features_path}")
        
        # Carrega os arquivos
        print(f"📂 Carregando features climáticas de: {climate_features_path}")
        climate_df = pd.read_csv(climate_features_path)
        print(f"   📊 Shape: {climate_df.shape}")
        print(f"   🔗 Colunas: {list(climate_df.columns)}")
        
        print(f"📂 Carregando features de imagem de: {image_features_path}")
        image_df = pd.read_csv(image_features_path)
        print(f"   📊 Shape: {image_df.shape}")
        print(f"   🔗 Colunas: {list(image_df.columns)}")

        # Verifica se a coluna CD_SETOR existe em ambos
        if 'CD_SETOR' not in climate_df.columns:
            raise ValueError("Coluna 'CD_SETOR' não encontrada no arquivo de features climáticas")
        
        if 'CD_SETOR' not in image_df.columns:
            raise ValueError("Coluna 'CD_SETOR' não encontrada no arquivo de features de imagem")

        # Garante que a coluna de junção seja do mesmo tipo
        climate_df['CD_SETOR'] = climate_df['CD_SETOR'].astype(int)
        image_df['CD_SETOR'] = image_df['CD_SETOR'].astype(int)
        
        print(f"🔄 Realizando merge dos DataFrames...")
        print(f"   🌡️ Setores climáticos: {len(climate_df)}")
        print(f"   🛰️ Setores de imagem: {len(image_df)}")

        # Une os dois DataFrames
        final_df = pd.merge(climate_df, image_df, on='CD_SETOR', how='left')
        
        print(f"✅ Merge realizado com sucesso!")
        print(f"   📊 Shape final: {final_df.shape}")
        print(f"   🔗 Colunas finais: {list(final_df.columns)}")
        
        # Verifica se há valores NaN após o merge
        nan_counts = final_df.isnull().sum()
        if nan_counts.sum() > 0:
            print(f"⚠️ Atenção: Valores NaN encontrados após o merge:")
            for col, count in nan_counts.items():
                if count > 0:
                    print(f"   {col}: {count} valores NaN")
        
        # Salva o arquivo final
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_df.to_csv(output_path, index=False)
        print(f"💾 Arquivo de features final salvo com sucesso em: {output_path}")
        
        # CORREÇÃO CRÍTICA: Retornar o DataFrame final
        return final_df
        
    except Exception as e:
        print(f"❌ Falha ao unir os arquivos de features: {e}")
        import traceback
        traceback.print_exc()
        raise