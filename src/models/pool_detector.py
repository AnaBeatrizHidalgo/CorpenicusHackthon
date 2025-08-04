# src/models/pool_detector.py
"""
Módulo para detecção de piscinas usando o modelo YOLOv8 em imagens de
alta resolução da Google Maps Static API.
"""
import logging
from pathlib import Path
import requests
import cv2
import numpy as np
import pandas as pd
import geopandas as gpd
from ultralytics import YOLO
from math import log, tan, pi, exp


# --- Carregamento do Modelo ---

def load_yolo_from_local_file(model_path: Path):
    """Carrega um modelo YOLO a partir de um arquivo .pt local."""
    if not model_path.exists():
        logging.error(f"Arquivo do modelo YOLO não encontrado em: {model_path}")
        return None
    try:
        model = YOLO(model_path)
        logging.info(f"Modelo YOLOv8 carregado com sucesso de: {model_path}")
        return model
    except Exception as e:
        logging.error(f"Falha ao carregar o modelo YOLO: {e}", exc_info=True)
        return None

# Carrega o modelo a partir do arquivo que você baixou
MODEL_PATH = Path("/home/lorhan/git/CorpenicusHackthon/models/swimming-pool-detector/model.pt") 
MODEL = load_yolo_from_local_file(MODEL_PATH)

def _approximate_pool_coords(center_lat, center_lon, zoom, img_size, pool_box): # <<< NOVO >>>
    """Aproxima as coordenadas geográficas de uma piscina dentro da imagem."""
    # Fórmulas de projeção de Mercator (usadas pelo Google Maps)
    C = (256 / (2 * pi)) * (2 ** zoom)
    
    # Converte o centro da imagem para "coordenadas de mundo"
    world_coord_x = C * (np.radians(center_lon) + pi)
    world_coord_y = C * (pi - log(tan((pi/4) + np.radians(center_lat)/2)))
    
    # Calcula a posição em pixels do centro da piscina na imagem
    px, py, pw, ph = pool_box
    
    # Calcula o deslocamento da piscina em relação ao centro da imagem
    dx = px - (img_size[0] / 2)
    dy = py - (img_size[1] / 2)
    
    # Aplica o deslocamento em "coordenadas de mundo"
    pool_world_x = world_coord_x + dx
    pool_world_y = world_coord_y + dy
    
    # Converte as coordenadas de mundo da piscina de volta para lat/lon
    pool_lon = np.degrees(pool_world_x / C - pi)
    pool_lat = np.degrees(2 * np.arctan(exp((pi - pool_world_y / C))) - pi / 2)
    
    return pool_lat, pool_lon

def is_pool_dirty_hsv(image: np.ndarray, box: list) -> bool: # <<< NOVO >>>
    """Analisa o recorte de uma piscina para verificar se a água é esverdeada."""
    x1, y1, x2, y2 = map(int, box)
    pool_crop = image[y1:y2, x1:x2]
    
    if pool_crop.size == 0:
        return False

    # Converte o recorte para o espaço de cores HSV
    hsv_crop = cv2.cvtColor(pool_crop, cv2.COLOR_BGR2HSV)

    # Define as faixas de cor para azul e verde no HSV
    # Hue(Matiz), Saturation(Saturação), Value(Valor/Brilho)
    lower_blue = np.array([100, 100, 50])
    upper_blue = np.array([130, 255, 255])
    
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])

    # Cria máscaras para contar os pixels
    blue_mask = cv2.inRange(hsv_crop, lower_blue, upper_blue)
    green_mask = cv2.inRange(hsv_crop, lower_green, upper_green)

    blue_pixels = cv2.countNonZero(blue_mask)
    green_pixels = cv2.countNonZero(green_mask)

    # Heurística: se houver mais pixels verdes do que azuis, ou uma quantidade
    # significativa de verde, considera-se "suja".
    if green_pixels > blue_pixels * 0.8 and green_pixels > 20: # O 0.8 e 20 são ajustáveis
        return True
        
    return False

def fetch_Maps_image(api_key, lat, lon, output_path, zoom=19, size="640x640"):
    base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    params = {"center": f"{lat},{lon}", "zoom": zoom, "size": size, "maptype": "satellite", "key": api_key}
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        f.write(response.content)
    logging.debug(f"Imagem para ({lat},{lon}) salva em {output_path}")

def find_pools_in_sectors(
    risk_sectors_gdf: gpd.GeoDataFrame,
    api_key: str,
    raw_images_dir: Path,
    detected_images_dir: Path,
    confidence_threshold: float = 0.25
): 
    if MODEL is None:
        logging.error("Modelo YOLO não carregado. Abortando detecção de piscinas.")
        return []
    
    raw_images_dir.mkdir(parents=True, exist_ok=True)
    detected_images_dir.mkdir(parents=True, exist_ok=True)

    dirty_pools_detections = [] 
    logging.info(f"Iniciando busca por piscinas em {len(risk_sectors_gdf)} setores de risco.")

    for index, sector in risk_sectors_gdf.iterrows():
        sector_id = sector['CD_SETOR']
        centroid = sector.geometry.centroid
        lat, lon = centroid.y, centroid.x
        raw_image_path = raw_images_dir / f"{sector_id}_raw.png"
        
        try:
            fetch_Maps_image(api_key, lat, lon, raw_image_path)
            # Carrega a imagem para análise de cor
            image_for_analysis = cv2.imread(str(raw_image_path))
            img_h, img_w, _ = image_for_analysis.shape

            results = MODEL(raw_image_path, conf=confidence_threshold, device='cpu')
            
            if len(results[0].boxes) > 0:
                found_dirty_pool = False
                # Itera sobre todas as piscinas detectadas na imagem
                for box in results[0].boxes:
                    box_coords = box.xyxy[0].tolist()
                    if is_pool_dirty_hsv(image_for_analysis, box_coords):
                        found_dirty_pool = True
                        pool_lat, pool_lon = _approximate_pool_coords(lat, lon, 19, (img_w, img_h), box.xywh[0].tolist())
                        
                        dirty_pools_detections.append({
                            "sector_id": sector_id,
                            "pool_lat": pool_lat,
                            "pool_lon": pool_lon,
                            "pool_confidence": float(box.conf[0])
                        })
                
                # Salva a imagem com as detecções APENAS se encontrou uma piscina suja
                if found_dirty_pool:
                    logging.info(f"PISCINA SUJA DETECTADA no setor {sector_id}!")
                    output_detection_path = detected_images_dir / f"{sector_id}_dirty_pool_detected.png"
                    results[0].save(filename=str(output_detection_path))
            else:
                logging.info(f"Nenhuma piscina detectada no setor {sector_id}.")
        except Exception as e:
            logging.error(f"Falha ao processar o setor {sector_id}: {e}", exc_info=True)
            continue
            
    return dirty_pools_detections
# --- Bloco de Teste (Permanece o mesmo) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.info("--- MODO DE TESTE: Executando pool_detector.py de forma isolada ---")
    try:
        from dotenv import load_dotenv
        import os
    except ImportError:
        logging.error("Para testar, instale 'python-dotenv': pip install python-dotenv")
        exit()
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("Maps_API_KEY")
    if not GOOGLE_API_KEY:
        logging.error("Chave Maps_API_KEY não encontrada no .env!")
    elif MODEL is None:
        logging.error("Teste abortado pois o modelo não foi carregado.")
    else:
        test_data = {'CD_SETOR': [1001, 1002], 'geometry': [gpd.points_from_xy([-47.069], [-22.818], crs="EPSG:4326")[0].buffer(0.001), gpd.points_from_xy([-47.065], [-22.820], crs="EPSG:4326")[0].buffer(0.001)]}
        test_gdf = gpd.GeoDataFrame(test_data, crs="EPSG:4326")
        test_raw_dir = Path("data/temp/google_raw")
        test_detected_dir = Path("data/temp/google_detected")
        try:
            detections = find_pools_in_sectors(risk_sectors_gdf=test_gdf, api_key=GOOGLE_API_KEY, raw_images_dir=test_raw_dir, detected_images_dir=test_detected_dir)
            logging.info(f"Detecção de teste concluída. Total de piscinas encontradas: {len(detections)}")
            print(detections)
            logging.info("--- TESTE STANDALONE DO POOL DETECTOR CONCLUÍDO COM SUCESSO ---")
        except Exception as e:
            logging.error(f"--- TESTE STANDALONE DO POOL DETECTOR FALHOU: {e} ---")