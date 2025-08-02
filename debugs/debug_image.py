# src/debug_image.py
"""
Script de debug para verificar a detecção de piscinas e salvamento de imagens.
Executa o processo de detecção para um único setor e imprime informações detalhadas.
"""
from pathlib import Path
import requests
import cv2
import numpy as np
import geopandas as gpd
from ultralytics import YOLO
from math import log, tan, pi, exp
import os
from dotenv import load_dotenv
from src.config.settings import STUDY_AREA
from src.utils.paths import BASE_DIR, OUTPUT_DIR

# Função para carregar o modelo YOLO
def load_yolo_from_local_file(model_path: Path):
    print(f"[INFO] Carregando modelo YOLO de: {model_path}")
    if not model_path.exists():
        print(f"[ERROR] Arquivo do modelo YOLO não encontrado em: {model_path}")
        return None
    try:
        model = YOLO(model_path)
        print(f"[INFO] Modelo YOLOv8 carregado com sucesso")
        return model
    except Exception as e:
        print(f"[ERROR] Falha ao carregar o modelo YOLO: {e}")
        return None

# Função para aproximar coordenadas da piscina
def _approximate_pool_coords(center_lat, center_lon, zoom, img_size, pool_box):
    print(f"[INFO] Calculando coordenadas aproximadas da piscina para centro ({center_lat}, {center_lon})")
    C = (256 / (2 * pi)) * (2 ** zoom)
    world_coord_x = C * (np.radians(center_lon) + pi)
    world_coord_y = C * (pi - log(tan((pi/4) + np.radians(center_lat)/2)))
    px, py, pw, ph = pool_box
    dx = px - (img_size[0] / 2)
    dy = py - (img_size[1] / 2)
    pool_world_x = world_coord_x + dx
    pool_world_y = world_coord_y + dy
    pool_lon = np.degrees(pool_world_x / C - pi)
    pool_lat = np.degrees(2 * np.arctan(exp((pi - pool_world_y / C))) - pi / 2)
    print(f"[INFO] Coordenadas calculadas: ({pool_lat:.4f}, {pool_lon:.4f})")
    return pool_lat, pool_lon

# Função para verificar se a piscina é suja (baseada em HSV)
def is_pool_dirty_hsv(image: np.ndarray, box: list, green_threshold=0.5, min_green_pixels=10) -> bool:
    print(f"[INFO] Verificando se a piscina é suja (box: {box})")
    x1, y1, x2, y2 = map(int, box)
    pool_crop = image[y1:y2, x1:x2]
    
    if pool_crop.size == 0:
        print(f"[WARNING] Recorte da piscina está vazio para box {box}")
        return False

    hsv_crop = cv2.cvtColor(pool_crop, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([100, 100, 50])
    upper_blue = np.array([130, 255, 255])
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])
    blue_mask = cv2.inRange(hsv_crop, lower_blue, upper_blue)
    green_mask = cv2.inRange(hsv_crop, lower_green, upper_green)
    blue_pixels = cv2.countNonZero(blue_mask)
    green_pixels = cv2.countNonZero(green_mask)
    print(f"[INFO] Pixels azuis: {blue_pixels}, Pixels verdes: {green_pixels}")
    
    # Relaxa o critério para considerar mais piscinas como sujas
    if green_pixels > blue_pixels * green_threshold and green_pixels > min_green_pixels:
        print(f"[INFO] Piscina considerada suja (green_pixels > {green_threshold} * blue_pixels e green_pixels > {min_green_pixels})")
        return True
    print(f"[INFO] Piscina não considerada suja")
    return False

# Função para buscar imagem do Google Maps
def fetch_maps_image(api_key, lat, lon, output_path, zoom=19, size="640x640"):
    print(f"[INFO] Baixando imagem do Google Maps para ({lat}, {lon})")
    base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    params = {"center": f"{lat},{lon}", "zoom": zoom, "size": size, "maptype": "satellite", "key": api_key}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"[INFO] Imagem salva em: {output_path}")
        if output_path.exists():
            print(f"[INFO] Confirmado: Arquivo {output_path} existe")
        else:
            print(f"[ERROR] Arquivo {output_path} não foi encontrado após salvar")
        return True
    except Exception as e:
        print(f"[ERROR] Falha ao baixar imagem do Google Maps: {e}")
        return False

# Função principal de debug
def debug_pool_detection(sector_id, lat, lon, api_key, model_path, raw_images_dir, detected_images_dir, confidence_threshold=0.25, green_threshold=0.5, min_green_pixels=10):
    print(f"[INFO] Iniciando debug para setor {sector_id} em ({lat}, {lon})")
    
    # Carrega o modelo YOLO
    model = load_yolo_from_local_file(model_path)
    if model is None:
        print(f"[ERROR] Abortando debug devido a falha no carregamento do modelo")
        return
    
    # Define caminhos
    raw_image_path = raw_images_dir / f"{sector_id}_raw.png"
    output_detection_path = detected_images_dir / f"{sector_id}_dirty_pool_detected.png"
    image_relative_path = f"output/{output_detection_path.parent.name}/{output_detection_path.name}"
    
    # Baixa a imagem do Google Maps
    if not raw_image_path.exists():
        if not fetch_maps_image(api_key, lat, lon, raw_image_path):
            print(f"[ERROR] Abortando debug devido a falha no download da imagem")
            return
    else:
        print(f"[INFO] Imagem bruta já existe em: {raw_image_path}")
    
    # Verifica se a imagem foi carregada corretamente
    print(f"[INFO] Carregando imagem para análise: {raw_image_path}")
    image_for_analysis = cv2.imread(str(raw_image_path))
    if image_for_analysis is None:
        print(f"[ERROR] Falha ao carregar imagem {raw_image_path}")
        return
    img_h, img_w, _ = image_for_analysis.shape
    print(f"[INFO] Dimensões da imagem: {img_w}x{img_h}")

    # Executa a detecção com YOLO
    print(f"[INFO] Executando YOLO em {raw_image_path} com confiança mínima {confidence_threshold}")
    results = model(raw_image_path, conf=confidence_threshold, device='cpu')
    
    # Verifica detecções
    num_boxes = len(results[0].boxes)
    print(f"[INFO] Total de caixas detectadas: {num_boxes}")
    
    detections = []
    if num_boxes > 0:
        found_dirty_pool = False
        for i, box in enumerate(results[0].boxes):
            box_coords = box.xyxy[0].tolist()
            confidence = float(box.conf[0])
            print(f"[INFO] Caixa {i+1}: Coordenadas={box_coords}, Confiança={confidence:.3f}")
            
            # Verifica se a piscina é suja
            if is_pool_dirty_hsv(image_for_analysis, box_coords, green_threshold, min_green_pixels):
                found_dirty_pool = True
                pool_lat, pool_lon = _approximate_pool_coords(lat, lon, 19, (img_w, img_h), box.xywh[0].tolist())
                print(f"[INFO] Piscina suja detectada! Coordenadas: ({pool_lat:.4f}, {pool_lon:.4f})")
                
                detections.append({
                    "sector_id": sector_id,
                    "pool_lat": pool_lat,
                    "pool_lon": pool_lon,
                    "pool_confidence": confidence,
                    "detection_image_path": image_relative_path
                })
        
        # Salva a imagem com detecções apenas se uma piscina suja for encontrada
        if found_dirty_pool:
            try:
                results[0].save(filename=str(output_detection_path))
                print(f"[INFO] Imagem de detecção salva em: {output_detection_path}")
                if output_detection_path.exists():
                    print(f"[INFO] Confirmado: Arquivo {output_detection_path} existe")
                    print(f"[INFO] Caminho relativo para Flask: {image_relative_path}")
                else:
                    print(f"[ERROR] Arquivo {output_detection_path} não foi encontrado após salvar")
            except Exception as e:
                print(f"[ERROR] Falha ao salvar imagem de detecção: {e}")
        else:
            print(f"[WARNING] Nenhuma piscina suja detectada no setor {sector_id}")
    else:
        print(f"[WARNING] Nenhuma piscina detectada no setor {sector_id}")
    
    # Resumo
    print(f"[INFO] Resumo: {len(detections)} piscinas sujas detectadas")
    for detection in detections:
        print(f"[INFO] Detecção: {detection}")

# Bloco de teste
if __name__ == "__main__":
    print("[INFO] --- MODO DE TESTE: Executando debug_image.py ---")
    try:
        load_dotenv(dotenv_path=BASE_DIR / '.env')
        GOOGLE_API_KEY = os.getenv("Maps_API_KEY")
        if not GOOGLE_API_KEY:
            print("[ERROR] Chave Maps_API_KEY não encontrada no .env!")
            exit()
        
        # Configurações de teste
        MODEL_PATH = BASE_DIR / "models/swimming-pool-detector/model.pt"
        JOB_ID = "analysis_-22.818_-47.069_1754007820"
        RAW_IMAGES_DIR = OUTPUT_DIR / JOB_ID / "google_raw_images"
        DETECTED_IMAGES_DIR = OUTPUT_DIR / JOB_ID / "google_detected_images"
        
        # Testar dois setores: um com detecção conhecida e um sem detecção
        test_sectors = [
            {"sector_id": "350950210000102", "lat": -22.818, "lon": -47.069},  # Setor com piscina detectada
            {"sector_id": "350950210000194", "lat": -22.818, "lon": -47.069}   # Setor sem detecção
        ]
        
        for sector in test_sectors:
            print(f"\n[INFO] Testando setor {sector['sector_id']}")
            debug_pool_detection(
                sector_id=sector["sector_id"],
                lat=sector["lat"],
                lon=sector["lon"],
                api_key=GOOGLE_API_KEY,
                model_path=MODEL_PATH,
                raw_images_dir=RAW_IMAGES_DIR,
                detected_images_dir=DETECTED_IMAGES_DIR,
                confidence_threshold=0.25,
                green_threshold=0.5,  # Relaxado de 0.8 para 0.5
                min_green_pixels=10   # Relaxado de 20 para 10
            )
        
        print("[INFO] --- TESTE CONCLUÍDO ---")
    except Exception as e:
        print(f"[ERROR] Falha no modo de teste: {e}")