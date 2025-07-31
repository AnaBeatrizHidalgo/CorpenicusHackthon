# src/utils/geoprocessing.py
"""
Módulo de utilidades para processamento de dados geoespaciais.
"""
import logging
import geopandas as gpd
from shapely.geometry import box
from pathlib import Path

def create_study_area_geojson(
    national_shapefile_path: Path,
    center_lat: float,
    center_lon: float,
    size_km: float,
    output_geojson_path: Path
) -> gpd.GeoDataFrame | None:
    """
    Cria um GeoJSON de uma área de estudo a partir de um shapefile nacional.

    Args:
        national_shapefile_path (Path): Caminho para o shapefile com todos os setores do Brasil.
        center_lat (float): Latitude do centro da área de estudo.
        center_lon (float): Longitude do centro da área de estudo.
        size_km (float): Tamanho da aresta da caixa (bbox) da área de estudo em quilômetros.
        output_geojson_path (Path): Caminho para salvar o GeoJSON da área recortada.

    Returns:
        gpd.GeoDataFrame | None: O GeoDataFrame da área de estudo ou None se falhar.
    """
    if not national_shapefile_path.exists():
        logging.error(f"Shapefile nacional não encontrado em: {national_shapefile_path}")
        return None

    logging.info(f"Criando área de estudo de {size_km}x{size_km} km centrada em ({center_lat}, {center_lon}).")

    # Converte tamanho em km para graus (aproximação)
    # 1 grau de latitude ≈ 111.32 km
    # 1 grau de longitude ≈ 111.32 * cos(latitude) km
    import numpy as np
    lat_degree_km = 111.32
    lon_degree_km = 111.32 * np.cos(np.radians(center_lat))
    
    half_size_lat_deg = (size_km / 2) / lat_degree_km
    half_size_lon_deg = (size_km / 2) / lon_degree_km

    # Calcula o bounding box
    min_lon = center_lon - half_size_lon_deg
    max_lon = center_lon + half_size_lon_deg
    min_lat = center_lat - half_size_lat_deg
    max_lat = center_lat + half_size_lat_deg
    
    study_bbox = (min_lon, min_lat, max_lon, max_lat)
    logging.info(f"Bounding Box da área de estudo: {study_bbox}")

    # Usa o filtro 'bbox' do geopandas para ler APENAS os setores
    # que cruzam nossa área de interesse. Isso é MUITO eficiente.
    try:
        logging.info("Lendo e recortando o shapefile nacional (isso pode levar um momento)...")
        study_gdf = gpd.read_file(national_shapefile_path, bbox=study_bbox)
        
        if study_gdf.empty:
            logging.warning("Nenhum setor censitário encontrado na área de estudo definida.")
            return None

        # Salva o arquivo recortado para uso no resto do pipeline
        output_geojson_path.parent.mkdir(parents=True, exist_ok=True)
        study_gdf.to_file(output_geojson_path, driver='GeoJSON')
        
        logging.info(f"{len(study_gdf)} setores censitários encontrados e salvos em {output_geojson_path}")
        return study_gdf

    except Exception as e:
        logging.error(f"Falha ao recortar o shapefile nacional: {e}", exc_info=True)
        return None