# src/utils/geoprocessing.py
"""
Módulo de utilidades para processamento de dados geoespaciais.
"""
import geopandas as gpd
from shapely.geometry import box
from pathlib import Path
import numpy as np


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
        print(f"❌ ERRO: Shapefile nacional não encontrado em: {national_shapefile_path}")
        return None

    print(f"🗺️ Criando área de estudo de {size_km}x{size_km} km centrada em ({center_lat}, {center_lon}).")

    # CORREÇÃO: Cálculo mais preciso da conversão km -> graus
    # 1 grau de latitude ≈ 111.32 km (constante)
    # 1 grau de longitude ≈ 111.32 * cos(latitude) km (varia com latitude)
    lat_degree_km = 111.32
    lon_degree_km = 111.32 * np.cos(np.radians(center_lat))
    
    half_size_lat_deg = (size_km / 2) / lat_degree_km
    half_size_lon_deg = (size_km / 2) / lon_degree_km

    # CORREÇÃO: Cálculo correto do bounding box
    min_lon = center_lon - half_size_lon_deg
    max_lon = center_lon + half_size_lon_deg
    min_lat = center_lat - half_size_lat_deg
    max_lat = center_lat + half_size_lat_deg
    
    # VALIDAÇÃO CRÍTICA: Verificar se o bbox está correto
    if min_lat >= max_lat or min_lon >= max_lon:
        print(f"❌ ERRO CRÍTICO: Bounding box inválido!")
        print(f"   min_lat ({min_lat}) >= max_lat ({max_lat})")
        print(f"   min_lon ({min_lon}) >= max_lon ({max_lon})")
        return None
    
    study_bbox = (min_lon, min_lat, max_lon, max_lat)
    print(f"📍 Bounding Box calculado: [{min_lon:.6f}, {min_lat:.6f}, {max_lon:.6f}, {max_lat:.6f}]")
    
    # CORREÇÃO: Verificar tamanhos reais em km
    actual_width_km = (max_lon - min_lon) * lon_degree_km
    actual_height_km = (max_lat - min_lat) * lat_degree_km
    print(f"📏 Dimensões reais: {actual_width_km:.2f} km (largura) x {actual_height_km:.2f} km (altura)")

    try:
        print("📂 Lendo e recortando o shapefile nacional (isso pode levar um momento)...")
        
        # CORREÇÃO: Usar bbox tupla ao invés de lista
        study_gdf = gpd.read_file(national_shapefile_path, bbox=study_bbox)
        
        if study_gdf.empty:
            print("⚠️ AVISO: Nenhum setor censitário encontrado na área de estudo definida.")
            print(f"   Verifique se as coordenadas ({center_lat}, {center_lon}) estão corretas.")
            print(f"   Bbox usado: {study_bbox}")
            return None

        # CORREÇÃO: Garantir que as colunas necessárias existem
        if 'CD_SETOR' not in study_gdf.columns:
            print("❌ ERRO: Coluna 'CD_SETOR' não encontrada no shapefile.")
            print(f"   Colunas disponíveis: {list(study_gdf.columns)}")
            return None

        # CORREÇÃO: Converter CD_SETOR para string para evitar problemas de tipo
        study_gdf['CD_SETOR'] = study_gdf['CD_SETOR'].astype(str)
        
        # Garantir que o GeoDataFrame está no CRS correto
        if study_gdf.crs != 'EPSG:4326':
            print(f"🔄 Convertendo CRS de {study_gdf.crs} para EPSG:4326")
            study_gdf = study_gdf.to_crs('EPSG:4326')

        # Salva o arquivo recortado para uso no resto do pipeline
        output_geojson_path.parent.mkdir(parents=True, exist_ok=True)
        study_gdf.to_file(output_geojson_path, driver='GeoJSON')
        
        print(f"✅ {len(study_gdf)} setores censitários encontrados e salvos em {output_geojson_path}")
        
        # INFORMAÇÃO ADICIONAL: Mostrar bounds reais dos setores encontrados
        real_bounds = study_gdf.total_bounds
        print(f"📊 Bounds reais dos setores: [{real_bounds[0]:.6f}, {real_bounds[1]:.6f}, {real_bounds[2]:.6f}, {real_bounds[3]:.6f}]")
        
        return study_gdf

    except Exception as e:
        print(f"❌ ERRO ao recortar o shapefile nacional: {str(e)}")
        print(f"   Bbox tentado: {study_bbox}")
        print(f"   Shapefile: {national_shapefile_path}")
        import traceback
        traceback.print_exc()
        return None