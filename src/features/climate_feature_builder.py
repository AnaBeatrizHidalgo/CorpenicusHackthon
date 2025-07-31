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
import warnings

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

        # Debug: Print dataset info
        logging.info(f"Dataset dimensions: {dict(climate_data.dims)}")
        logging.info(f"Dataset coordinates: {list(climate_data.coords)}")
        
        # Get climate variables
        climate_vars = list(climate_data.data_vars)
        logging.info(f"Variáveis climáticas encontradas: {climate_vars}")
        
        # Get spatial extent of climate data
        if 'latitude' in climate_data.coords:
            lat_coord = 'latitude'
            lon_coord = 'longitude'
        elif 'lat' in climate_data.coords:
            lat_coord = 'lat'
            lon_coord = 'lon'
        else:
            raise ValueError("Could not find latitude/longitude coordinates in climate data")
        
        climate_bounds = [
            float(climate_data[lon_coord].min()),
            float(climate_data[lat_coord].min()),
            float(climate_data[lon_coord].max()),
            float(climate_data[lat_coord].max())
        ]
        logging.info(f"Climate data bounds: {climate_bounds}")
        
        # Get sectors bounds
        sectors_bounds = list(sectors.total_bounds)
        logging.info(f"Sectors bounds: {sectors_bounds}")

        # 2. Iterar sobre cada setor para calcular a média
        results = []
        processed_count = 0
        empty_mask_count = 0

        for index, sector in sectors.iterrows():
            sector_id = sector['CD_SETOR'] 
            geom = [sector.geometry]
            
            try:
                # Check if sector geometry intersects with climate data bounds
                sector_bounds = sector.geometry.bounds
                if (sector_bounds[2] < climate_bounds[0] or  # sector max_lon < climate min_lon
                    sector_bounds[0] > climate_bounds[2] or  # sector min_lon > climate max_lon
                    sector_bounds[3] < climate_bounds[1] or  # sector max_lat < climate min_lat
                    sector_bounds[1] > climate_bounds[3]):   # sector min_lat > climate max_lat
                    
                    logging.warning(f"Setor {sector_id} fora dos limites dos dados climáticos")
                    sector_metrics = {'CD_SETOR': sector_id}
                    for var in climate_vars:
                        sector_metrics[f"{var}_mean"] = np.nan
                    results.append(sector_metrics)
                    continue

                # Create mask for this sector
                mask = geometry_mask(
                    geometries=geom,
                    out_shape=(len(climate_data[lat_coord]), len(climate_data[lon_coord])),
                    transform=climate_data.rio.transform(),
                    invert=True
                )
                
                # Check if mask has any True values (i.e., any pixels within the sector)
                if not np.any(mask):
                    empty_mask_count += 1
                    logging.warning(f"Setor {sector_id}: máscara vazia (sem pixels climáticos)")
                    sector_metrics = {'CD_SETOR': sector_id}
                    for var in climate_vars:
                        sector_metrics[f"{var}_mean"] = np.nan
                    results.append(sector_metrics)
                    continue

                # Calculate metrics for this sector
                sector_metrics = {'CD_SETOR': sector_id}
                
                for var in climate_vars:
                    try:
                        # Apply mask to climate data
                        masked_data = climate_data[var].where(mask)
                        
                        # Get valid (non-NaN) values
                        valid_values = masked_data.values[~np.isnan(masked_data.values)]
                        
                        if len(valid_values) == 0:
                            # No valid data for this variable in this sector
                            mean_value = np.nan
                            logging.debug(f"Setor {sector_id}, variável {var}: sem dados válidos")
                        else:
                            # Calculate mean of valid values
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", category=RuntimeWarning)
                                mean_value = float(np.mean(valid_values))
                        
                        sector_metrics[f"{var}_mean"] = mean_value
                        
                    except Exception as e:
                        logging.error(f"Erro ao processar variável {var} para setor {sector_id}: {str(e)}")
                        sector_metrics[f"{var}_mean"] = np.nan
                
                results.append(sector_metrics)
                processed_count += 1
                
                if processed_count % 10 == 0:
                    logging.info(f"Processados {processed_count}/{len(sectors)} setores...")
                    
            except Exception as e:
                logging.error(f"Erro ao processar setor {sector_id}: {str(e)}")
                # Add sector with NaN values to maintain consistency
                sector_metrics = {'CD_SETOR': sector_id}
                for var in climate_vars:
                    sector_metrics[f"{var}_mean"] = np.nan
                results.append(sector_metrics)
                continue
        
        # Create results DataFrame
        results_df = pd.DataFrame(results)
        
        # Log statistics
        logging.info(f"Processamento concluído:")
        logging.info(f"  - Total de setores: {len(sectors)}")
        logging.info(f"  - Setores processados com sucesso: {processed_count}")
        logging.info(f"  - Setores com máscara vazia: {empty_mask_count}")
        logging.info(f"  - Setores com erro: {len(sectors) - processed_count - empty_mask_count}")
        
        # Check for columns with all NaN values
        for col in results_df.columns:
            if col != 'CD_SETOR':
                nan_count = results_df[col].isna().sum()
                if nan_count == len(results_df):
                    logging.warning(f"Todas as entradas da coluna '{col}' são NaN")
                elif nan_count > 0:
                    logging.info(f"Coluna '{col}': {nan_count}/{len(results_df)} valores são NaN")
        
        # Save results
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(output_path, index=False)
        logging.info(f"Dados climáticos agregados salvos com sucesso em: {output_path}")
        
        return results_df

    except KeyError as e:
        logging.error(f"Erro de chave: A coluna {e} não foi encontrada no GeoJSON. Verifique o nome da coluna de identificação do setor.")
        raise
    except Exception as e:
        logging.error(f"Falha ao agregar dados climáticos: {e}", exc_info=True)
        raise

# Bloco de teste
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