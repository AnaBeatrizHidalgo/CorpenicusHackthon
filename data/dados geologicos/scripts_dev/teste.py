import geopandas as gpd
import requests
from shapely.geometry import box, Polygon

# 1. Definir a bounding box (Campinas, Barão Geraldo, próximo à Unicamp)
bbox = box(-47.07, -22.91, -46.97, -22.81)
gdf_bbox = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[bbox])
gdf_bbox.to_file("area_prova_bbox.geojson", driver="GeoJSON")
print("Bounding box salva em area_prova_bbox.geojson")

# 2. Baixar setores censitários do IBGE (Censo 2022)
# Substitua pelo caminho do shapefile baixado de https://downloads.ibge.gov.br/
# Exemplo: ftp://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/SP/SP_Setores_2022.zip
try:
    setores = gpd.read_file("/home/lorhan/git/CorpenicusHackthon/dados geologicos/Dados IBGE/SP_Municipios_2024.shp")  # Atualize o caminho
    setores_campinas = setores[setores.geometry.intersects(bbox)]
    if len(setores_campinas) == 0:
        print("Nenhum setor encontrado. Verifique o shapefile ou bounding box.")
    else:
        setores_campinas.to_file("area_prova.geojson", driver="GeoJSON")
        print(f"Setores salvos em area_prova.geojson ({len(setores_campinas)} setores)")
except FileNotFoundError:
    print("Shapefile não encontrado. Baixe de https://downloads.ibge.gov.br/")

# 3. (Opcional) Baixar footprints de casas via Overpass API
overpass_url = "http://overpass-api.de/api/interpreter"
query = """
[out:json][timeout:25];
(
  way["building"](-22.91,-47.07,-22.81,-46.97);
  relation["building"](-22.91,-47.07,-22.81,-46.97);
);
out body;
>;
out skel qt;
"""
try:
    response = requests.post(overpass_url, data={'data': query})
    response.raise_for_status()
    data = response.json()
    features = []
    for element in data['elements']:
        if 'geometry' in element and element['type'] == 'way':
            coords = [(n['lon'], n['lat']) for n in element['geometry']['coordinates'][0]]
            features.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [coords]}})
    if features:
        gdf_casas = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        gdf_casas.to_file("casas.geojson", driver="GeoJSON")
        print(f"Footprints salvos em casas.geojson ({len(gdf_casas)} edifícios)")
    else:
        print("Nenhum edifício encontrado no OSM para a área.")
except requests.RequestException as e:
    print(f"Erro na Overpass API: {e}. Prosseguir com setores censitários.")