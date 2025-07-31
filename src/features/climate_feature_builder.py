# src/features/climate_feature_builder.py
"""
Módulo para processar dados climáticos brutos e criar features por setor censitário.

Lê os arquivos NetCDF do ERA5 e um arquivo GeoJSON dos setores para calcular
a média das variáveis climáticas (ex: temperatura, precipitação) para cada setor.
"""
import logging
import geopandas as gpd
import pandas as pd

import xarray as xr
from rasterio.features import geometry_mask
import numpy as np
from pathlib import Path

def aggregate_climate_by_sector(
    netcdf_path: Path,
    geodata_path: Path,
    output_path: Path
):
    """
    Agrega dados climáticos de um NetCDF para cada polígono de um GeoDataFrame.

    Args:
        netcdf_path (Path): Caminho para o arquivo NetCDF de dados climáticos (ex: ERA5).
        geodata_path (Path): Caminho para o arquivo GeoJSON/Shapefile dos setores.
        output_path (Path): Caminho para salvar o arquivo CSV com os dados agregados.
    """
    logging.info("Iniciando agregação de dados climáticos por setor censitário.")
    
    try:
        # 1. Carregar os dados
        logging.info(f"Lendo dados climáticos de: {netcdf_path}")
        climate_data = xr.open_dataset(netcdf_path)
        
        logging.info(f"Lendo dados geográficos de: {geodata_path}")
        sectors = gpd.read_file(geodata_path)
        
        # Garante que os dados geográficos usem a mesma projeção dos dados climáticos (WGS84)
        sectors = sectors.to_crs(epsg=4326)

        # 2. Iterar sobre cada setor para calcular a média
        results = []
        # Pega o nome das variáveis climáticas do dataset (ex: 't2m', 'tp')
        climate_vars = list(climate_data.data_vars)
        logging.info(f"Variáveis climáticas encontradas: {climate_vars}")

        for index, sector in sectors.iterrows():
            # <<< AQUI ESTÁ A CORREÇÃO >>>
            # Trocando 'CD_CENSIT' por 'CD_SETOR' para corresponder ao seu GeoJSON.
            sector_id = sector['CD_SETOR'] 
            
            geom = [sector.geometry] 

            mask = geometry_mask(
                geometries=geom,
                out_shape=(len(climate_data.latitude), len(climate_data.longitude)),
                transform=climate_data.rio.transform(),
                invert=True
            )

            # O ID no dicionário também foi atualizado para manter a consistência.
            sector_metrics = {'CD_SETOR': sector_id}
            for var in climate_vars:
                masked_data = climate_data[var].where(mask)
                mean_value = float(np.nanmean(masked_data.values))
                sector_metrics[f"{var}_mean"] = mean_value
            
            results.append(sector_metrics)
        
        results_df = pd.DataFrame(results)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(output_path, index=False)
        logging.info(f"Dados climáticos agregados salvos com sucesso em: {output_path}")

    except KeyError as e:
        logging.error(f"Erro de chave: A coluna {e} não foi encontrada no GeoJSON. Verifique o nome da coluna de identificação do setor.")
        raise
    except Exception as e:
        logging.error(f"Falha ao agregar dados climáticos: {e}", exc_info=True)
        raise

# Bloco de teste (permanece o mesmo)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.info("--- MODO DE TESTE: Executando climate_feature_builder.py de forma isolada ---")

    try:
        from config import settings
        from src.utils import paths
    except ModuleNotFoundError:
        logging.error("Execute este script a partir da raiz do projeto: python -m src.features.climate_feature_builder")
        exit()

    raw_climate_file = paths.RAW_CLIMATE_DIR / "era5_test_2024-07-01.nc"
    raw_geodata_file = paths.RAW_GEODATA_DIR / "setores_barao.geojson"
    processed_output_file = paths.PROCESSED_DIR / "climate_features_test.csv"

    if not raw_climate_file.exists() or not raw_geodata_file.exists():
        logging.error(f"Arquivos de entrada para o teste não encontrados: {raw_climate_file}, {raw_geodata_file}")
    else:
        try:
            aggregate_climate_by_sector(
                netcdf_path=raw_climate_file,
                geodata_path=raw_geodata_file,
                output_path=processed_output_file
            )
            logging.info("--- TESTE STANDALONE DO FEATURE BUILDER CONCLUÍDO COM SUCESSO ---")
        except Exception as e:
            logging.error(f"--- TESTE STANDALONE DO FEATURE BUILDER FALHOU: {e} ---")
