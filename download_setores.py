import geopandas as gpd
from shapely.geometry import box
import folium
import os

# Definir a bounding box (Unicamp, Barão Geraldo, ~20 km²)
bbox = box(-47.10, -22.85, -47.03, -22.78)
gdf_bbox = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[bbox])
os.makedirs("data", exist_ok=True)
gdf_bbox.to_file("data/area_prova_bbox.geojson", driver="GeoJSON")
print("Bounding box salva em data/area_prova_bbox.geojson")

# Caminho do shapefile
shapefile_path = "/home/lorhan/git/CorpenicusHackthon/dados geologicos/Dados IBGE/BR_setores_CD2022.shp"

# Verificar se o shapefile existe
if not os.path.exists(shapefile_path):
    print(f"Erro: Shapefile {shapefile_path} não encontrado.")
    print("Baixe de https://www.ibge.gov.br/geociencias/downloads-geociencias.html?caminho=organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/shp/BR")
    exit()

# Carregar e filtrar setores censitários
try:
    setores = gpd.read_file(shapefile_path, encoding="latin-1")
    print(f"Shapefile carregado: {len(setores)} setores totais")
    print("Colunas disponíveis:", list(setores.columns))

    # Converter para SIRGAS 2000 (EPSG:4674)
    setores = setores.to_crs(epsg=4674)
    gdf_bbox = gdf_bbox.to_crs(epsg=4674)

    # Filtrar por Campinas (código 3509502)
    setores_campinas = setores[setores['CD_MUN'] == '3509502']
    print(f"Total de setores em Campinas: {len(setores_campinas)}")

    # Verificar distritos
    print("Distritos disponíveis:", setores_campinas['NM_DIST'].unique())

    # Filtrar por Barão Geraldo, bounding box, urbana e área <= 1 km²
    setores_barao = setores_campinas[
        (setores_campinas['NM_DIST'].str.contains('Bar.o Geraldo', case=False, na=False, regex=True)) &
        (setores_campinas.geometry.intersects(gdf_bbox.geometry[0])) &
        (setores_campinas['SITUACAO'] == 'Urbana') &
        (setores_campinas['AREA_KM2'] <= 1.0)
    ]

    if len(setores_barao) == 0:
        print("Nenhum setor encontrado em Barão Geraldo (urbano, <= 1 km²).")
        print("1. Salvando setores de Campinas para inspeção...")
        setores_campinas = setores_campinas.to_crs(epsg=4326)
        setores_campinas.to_file("data/campinas_all.geojson", driver="GeoJSON")
        print("2. Setores de Campinas salvos em data/campinas_all.geojson")

        # Visualizar setores de Campinas
        m = setores_campinas.explore(
            column="CD_SETOR", tooltip=["CD_SETOR", "NM_DIST", "SITUACAO", "AREA_KM2"],
            style_kwds={"fillOpacity": 0.5}
        )
        gdf_bbox.to_crs(epsg=4326).explore(m=m, color="red", style_kwds={"fillOpacity": 0.2})
        m.save("data/campinas_all_map.html")
        print("3. Mapa interativo salvo em data/campinas_all_map.html")
        print("4. Tente ajustar a bounding box, por exemplo: [-47.11, -22.86, -47.02, -22.77]")
    else:
        setores_barao = setores_barao.to_crs(epsg=4326)
        setores_barao.to_file("data/area_prova_barao.geojson", driver="GeoJSON")
        print(f"Setores salvos em data/area_prova_barao.geojson ({len(setores_barao)} setores)")

        # Visualizar setores encontrados
        m = setores_barao.explore(
            column="CD_SETOR", tooltip=["CD_SETOR", "NM_DIST", "SITUACAO", "AREA_KM2"],
            style_kwds={"fillOpacity": 0.5}
        )
        gdf_bbox.explore(m=m, color="red", style_kwds={"fillOpacity": 0.2})
        m.save("data/area_prova_barao_map.html")
        print("Mapa interativo salvo em data/area_prova_barao_map.html")
except Exception as e:
    print(f"Erro ao processar shapefile: {e}")