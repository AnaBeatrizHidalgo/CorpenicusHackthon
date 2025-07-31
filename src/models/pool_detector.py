# src/models/pool_detector.py
"""
Módulo para detecção de piscinas usando o modelo YOLOv8 em imagens de
alta resolução da Google Maps Static API.
"""
import logging
from pathlib import Path
import requests
import cv2
import pandas as pd
import geopandas as gpd
from ultralytics import YOLO

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


# --- Funções de Detecção (Permanecem as mesmas) ---

def fetch_Maps_image(api_key, lat, lon, output_path, zoom=19, size="640x640"):
    # ... (código sem alterações)
    base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    params = {"center": f"{lat},{lon}", "zoom": zoom, "size": size, "maptype": "satellite", "key": api_key}
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        f.write(response.content)
    logging.debug(f"Imagem para ({lat}, {lon}) salva em {output_path}")

def find_pools_in_sectors(
    risk_sectors_gdf: gpd.GeoDataFrame,
    api_key: str,
    raw_images_dir: Path,
    detected_images_dir: Path,
    confidence_threshold: float = 0.25
):
    # ... (código sem alterações)
    if MODEL is None:
        logging.error("Modelo YOLO não carregado. Abortando detecção de piscinas.")
        return []
    
    raw_images_dir.mkdir(parents=True, exist_ok=True)
    detected_images_dir.mkdir(parents=True, exist_ok=True)
    all_detections = []
    logging.info(f"Iniciando busca por piscinas em {len(risk_sectors_gdf)} setores de risco.")

    for index, sector in risk_sectors_gdf.iterrows():
        sector_id = sector['CD_SETOR']
        centroid = sector.geometry.centroid
        lat, lon = centroid.y, centroid.x
        raw_image_path = raw_images_dir / f"{sector_id}_raw.png"
        
        try:
            fetch_Maps_image(api_key, lat, lon, raw_image_path)
            results = MODEL(raw_image_path, conf=confidence_threshold, device='cpu')
            
            if len(results[0].boxes) > 0:
                logging.info(f"Detectadas {len(results[0].boxes)} piscinas no setor {sector_id}.")
                output_detection_path = detected_images_dir / f"{sector_id}_detected.png"
                results[0].save(filename=str(output_detection_path))
                
                for box in results[0].boxes:
                    coords = box.xywhn[0]
                    all_detections.append({
                        "sector_id": sector_id, "center_lat": lat, "center_lon": lon,
                        "pool_confidence": float(box.conf[0]), "pool_center_x_norm": float(coords[0]),
                        "pool_center_y_norm": float(coords[1]), "detection_image_path": str(output_detection_path)
                    })
            else:
                logging.info(f"Nenhuma piscina detectada no setor {sector_id}.")
        except Exception as e:
            logging.error(f"Falha ao processar o setor {sector_id}: {e}", exc_info=True)
            continue
            
    return all_detections

# --- Bloco de Teste (Permanece o mesmo) ---
if __name__ == '__main__':
    # ... (código sem alterações)
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