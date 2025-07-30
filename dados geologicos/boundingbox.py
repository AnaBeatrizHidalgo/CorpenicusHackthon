import geopandas as gpd
from shapely.geometry import Polygon

# Definir a bounding box
coords = [(-46.75, -23.55), (-46.75, -23.45), (-46.65, -23.45), (-46.65, -23.55), (-46.75, -23.55)]
polygon = Polygon(coords)
gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[polygon])
gdf.to_file("area_prova_bbox.geojson", driver="GeoJSON")
print("Bounding box salva em area_prova_bbox.geojson")