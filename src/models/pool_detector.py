import ee
import numpy as np
import pandas as pd
import cv2
import rasterio
import requests
import io
from tensorflow import keras
import folium
from folium import plugins
from datetime import datetime, timedelta
from pathlib import Path

# Autenticar e inicializar Google Earth Engine
ee.Authenticate()
ee.Initialize()

# Definir área de estudo (Barão Geraldo, Campinas)
aoi = ee.Geometry.Polygon([
    [[-47.087, -22.825], [-47.087, -22.815], [-47.077, -22.815], [-47.077, -22.825], [-47.087, -22.825]]
])

def get_climatic_data(start_date, end_date):
    era5 = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').filterDate(start_date, end_date).filterBounds(aoi)
    precipitation = era5.select('total_precipitation_sum').mean().reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=1000).get('total_precipitation_sum')
    return {'precipitation': precipitation.getInfo()}

def download_sentinel_image(date_range_days=30):
    end_date = datetime(2025, 7, 30)
    start_date = end_date - timedelta(days=date_range_days)
    
    # Coleta de imagem Sentinel-2 com bandas RGB (B4, B3, B2) e NIR (B8)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR').filterDate(start_date, end_date).filterBounds(aoi).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).sort('CLOUDY_PIXEL_PERCENTAGE').first()
    if s2 is None:
        raise ValueError("Nenhuma imagem Sentinel-2 disponível com baixa cobertura de nuvens.")
    
    # Exportar imagem RGB + NIR
    image = s2.select(['B4', 'B3', 'B2', 'B8']).multiply(0.0001)  # Normalizar valores
    url = image.getDownloadURL({'scale': 10, 'region': aoi, 'format': 'NPY'})
    response = requests.get(url)
    satellite_image = np.load(io.BytesIO(response.content))
    if satellite_image.shape[1] != 4:  # [height, width, bands]
        raise ValueError("Imagem esperada com 4 bandas (R, G, B, NIR).")
    print(f"Imagem Sentinel-2 carregada: {satellite_image.shape}")
    return satellite_image.transpose(1, 2, 0)  # [bands, height, width] -> [height, width, bands]

class NAIAPoolDetector:
    def __init__(self):
        self.study_area = {
            'name': 'Barão Geraldo, Campinas',
            'bbox': [-47.1, -22.85, -47.05, -22.8],
            'center': [-47.075, -22.825]
        }
        self.tile_size = 512
        self.satellite_image = None
        self.precipitation = None
        self.thresholds = {
            'ndwi_min': 0.2,
            'area_min': 50,
            'area_max': 5000,
            'circularity_min': 0.3,
            'dirty_threshold': 0.6
        }
    
    def download_sentinel_image(self, date_range_days=30):
        self.satellite_image = download_sentinel_image(date_range_days)
        return self.satellite_image
    
    def calculate_water_indices(self):
        red = self.satellite_image[:,:,0]
        green = self.satellite_image[:,:,1]
        blue = self.satellite_image[:,:,2]
        nir = self.satellite_image[:,:,3]
        
        self.ndwi = np.divide(green - nir, green + nir, out=np.zeros_like(green), where=(green + nir) != 0)
        self.ndvi = np.divide(nir - red, nir + red, out=np.zeros_like(red), where=(nir + red) != 0)
        self.turbidity_index = green / (blue + 0.001)
        print("Índices espectrais calculados")
    
    def detect_water_bodies(self):
        water_mask = self.ndwi > self.thresholds['ndwi_min']
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        water_mask = cv2.morphologyEx(water_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
        water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.water_contours = contours
        print(f"Encontrados {len(contours)} candidatos a corpo d'água")
        return water_mask, contours
    
    def classify_pools(self, contours):
        pools = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if area < self.thresholds['area_min'] or area > self.thresholds['area_max']:
                continue
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
            else:
                continue
            if circularity < self.thresholds['circularity_min']:
                continue
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                continue
            mask = np.zeros(self.ndwi.shape, dtype=np.uint8)
            cv2.fillPoly(mask, [contour], 1)
            mask = mask.astype(bool)
            features = self.extract_pool_features(mask, cx, cy)
            cleanliness_score = self.classify_cleanliness(features)
            is_dirty = cleanliness_score > self.thresholds['dirty_threshold']
            pool_data = {
                'id': f'pool_{i}',
                'centroid': (cx, cy),
                'area': area,
                'circularity': circularity,
                'contour': contour,
                'features': features,
                'cleanliness_score': cleanliness_score,
                'is_dirty': is_dirty,
                'risk_level': 'high' if is_dirty else 'low'
            }
            pools.append(pool_data)
        self.detected_pools = pools
        print(f"Detectadas {len(pools)} piscinas")
        print(f"Piscinas suspeitas (sujas): {sum(1 for p in pools if p['is_dirty'])}")
        return pools
    
    def extract_pool_features(self, mask, cx, cy):
        red_mean = np.mean(self.satellite_image[:,:,0][mask])
        green_mean = np.mean(self.satellite_image[:,:,1][mask])
        blue_mean = np.mean(self.satellite_image[:,:,2][mask])
        nir_mean = np.mean(self.satellite_image[:,:,3][mask])
        ndwi_mean = np.mean(self.ndwi[mask])
        turbidity_mean = np.mean(self.turbidity_index[mask])
        buffer_mask = self.create_buffer_mask(cx, cy, 50)
        vegetation_around = np.mean(self.ndvi[buffer_mask])
        spectral_std = np.std([red_mean, green_mean, blue_mean])
        return {
            'red_mean': red_mean,
            'green_mean': green_mean,
            'blue_mean': blue_mean,
            'nir_mean': nir_mean,
            'ndwi_mean': ndwi_mean,
            'turbidity': turbidity_mean,
            'vegetation_around': vegetation_around,
            'spectral_variability': spectral_std
        }
    
    def create_buffer_mask(self, cx, cy, buffer_size):
        Y, X = np.ogrid[:self.ndwi.shape[0], :self.ndwi.shape[1]]
        mask = (X - cx)**2 + (Y - cy)**2 <= buffer_size**2
        return mask
    
    def classify_cleanliness(self, features):
        score = 0
        green_ratio = features['green_mean'] / (features['blue_mean'] + 0.001)
        if green_ratio > 1.2:
            score += 0.3
        if features['turbidity'] > 1.5:
            score += 0.25
        if features['vegetation_around'] > 0.3:
            score += 0.2
        if features['spectral_variability'] > 0.1:
            score += 0.15
        if features['ndwi_mean'] < 0.4:
            score += 0.1
        # Adicionar influência da precipitação
        if self.precipitation and self.precipitation > 50:  # mm
            score += 0.15
        return min(score, 1.0)
    
    def pixel_to_coordinates(self, px, py):
        bbox = self.study_area['bbox']
        height, width = self.satellite_image.shape[:2]
        lon = bbox[0] + (px / width) * (bbox[2] - bbox[0])
        lat = bbox[3] - (py / height) * (bbox[3] - bbox[1])
        return lat, lon
    
    def create_risk_map(self):
        m = folium.Map(location=self.study_area['center'][::-1], zoom_start=14, tiles='OpenStreetMap')
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        clean_pools = 0
        dirty_pools = 0
        for pool in self.detected_pools:
            cx, cy = pool['centroid']
            lat, lon = self.pixel_to_coordinates(cx, cy)
            if pool['is_dirty']:
                color = 'red'
                icon = 'exclamation-triangle'
                dirty_pools += 1
            else:
                color = 'green'
                icon = 'tint'
                clean_pools += 1
            popup_text = f"<b>Piscina {pool['id']}</b><br><b>Status:</b> {'🚨 SUSPEITA' if pool['is_dirty'] else '✅ Normal'}<br><b>Score de Risco:</b> {pool['cleanliness_score']:.2f}"
            folium.Marker([lat, lon], popup=folium.Popup(popup_text, max_width=300), tooltip=f"Piscina {pool['id']}", icon=folium.Icon(color=color, icon=icon, prefix='fa')).add_to(m)
        stats_html = f"<div style='position: fixed; top: 10px; left: 50px; width: 200px; height: 80px; background-color: white; border:2px solid grey; z-index:9999; font-size:14px; padding: 10px'><b>NAIÁ - Detecções:</b><br>🟢 Piscinas normais: {clean_pools}<br>🔴 Piscinas suspeitas: {dirty_pools}</div>"
        m.get_root().html.add_child(folium.Element(stats_html))
        folium.LayerControl().add_to(m)
        self.risk_map = m
        return m
    
    def run_detection_pipeline(self):
        print("=== NAIÁ - Iniciando detecção de piscinas ===")
        self.download_sentinel_image()
        self.precipitation = get_climatic_data(datetime(2025, 7, 25), datetime(2025, 7, 30))['precipitation']
        self.calculate_water_indices()
        water_mask, contours = self.detect_water_bodies()
        pools = self.classify_pools(contours)
        risk_map = self.create_risk_map()
        print("=== Detecção concluída! ===")
        return pools, risk_map
    
    def save_results(self, output_dir="naia_results"):
        Path(output_dir).mkdir(exist_ok=True)
        pools_df = pd.DataFrame([{'pool_id': pool['id'], 'lat': self.pixel_to_coordinates(*pool['centroid'])[0], 'lon': self.pixel_to_coordinates(*pool['centroid'])[1], 'area': pool['area'], 'circularity': pool['circularity'], 'cleanliness_score': pool['cleanliness_score'], 'is_dirty': pool['is_dirty'], 'risk_level': pool['risk_level'], **pool['features']} for pool in self.detected_pools])
        pools_df.to_csv(f"{output_dir}/detected_pools.csv", index=False)
        self.risk_map.save(f"{output_dir}/risk_map.html")
        stats = {'total_pools': len(self.detected_pools), 'clean_pools': sum(1 for p in self.detected_pools if not p['is_dirty']), 'dirty_pools': sum(1 for p in self.detected_pools if p['is_dirty']), 'high_risk_percentage': sum(1 for p in self.detected_pools if p['is_dirty']) / len(self.detected_pools) * 100 if self.detected_pools else 0}
        with open(f"{output_dir}/statistics.json", 'w') as f:
            import json
            json.dump(stats, f, indent=2)
        print(f"Resultados salvos em: {output_dir}/")
        return pools_df, stats

if __name__ == "__main__":
    naia = NAIAPoolDetector()
    pools, risk_map = naia.run_detection_pipeline()
    naia.save_results()