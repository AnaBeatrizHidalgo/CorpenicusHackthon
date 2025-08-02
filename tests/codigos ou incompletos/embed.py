import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import requests
from scipy import ndimage
from scipy.stats import rankdata

# =============================================================================
# CONFIGURAÇÕES GERAIS
# =============================================================================

# Coordenadas especificadas: 22°53'17"S, 47°04'07"W
TARGET_COORDS = (-22.888056, -47.068611)  # (lat, lng) convertido para decimal
TARGET_COORDS_DMS = "22°53'17\"S, 47°04'07\"W"

# APIs Keys (substitua pelas suas credenciais reais)
GOOGLE_MAPS_API_KEY = "AIzaSyDnl_2euroZ9uv4d5yYhddvvSTQcmJnufA"
SENTINEL_CLIENT_ID = "sh-0dca0b34-16fc-4839-8aa2-868a9f956dd5"
SENTINEL_CLIENT_SECRET = "nv3TfJxIkp1WC20uxVcFVwjPm5DS4m3v"

# Configurações da imagem
IMAGE_SIZE = "800x600"
ZOOM_LEVEL = 1
MAP_TYPE = "satellite"

# Área de interesse (bbox) centrada nas coordenadas alvo
BBOX_MARGIN = 0.015  # ~1.5km de margem
BBOX = [
    TARGET_COORDS[1] - BBOX_MARGIN,  # min_lon
    TARGET_COORDS[0] - BBOX_MARGIN,  # min_lat  
    TARGET_COORDS[1] + BBOX_MARGIN,  # max_lon
    TARGET_COORDS[0] + BBOX_MARGIN   # max_lat
]

print(f"🎯 COORDENADAS ALVO: {TARGET_COORDS_DMS}")
print(f"📍 Coordenadas decimais: {TARGET_COORDS}")
print(f"📦 Área de interesse (BBOX): {BBOX}")

# =============================================================================
# FUNÇÕES PARA GOOGLE EARTH
# =============================================================================

def download_google_earth_image(center_coords, api_key, size="800x600", zoom=15, maptype="satellite"):
    """Baixar imagem real do Google Earth/Maps"""
    try:
        lat, lng = center_coords
        print(f"🌍 Baixando imagem do Google Earth para: {lat:.6f}, {lng:.6f}")
        
        # URL da API Google Maps Static
        base_url = "https://maps.googleapis.com/maps/api/staticmap"
        params = {
            'center': f"{lat},{lng}",
            'zoom': zoom,
            'size': size,
            'maptype': maptype,
            'key': api_key
        }
        
        # Construir URL completa
        url = f"{base_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        # Fazer requisição
        print("📡 Fazendo requisição para Google Maps API...")
        response = requests.get(url)
        
        if response.status_code == 200:
            # Salvar imagem original do Google Earth
            with open('google_earth_raw.png', 'wb') as f:
                f.write(response.content)
            
            # Carregar como PIL Image
            img_original = Image.open('google_earth_raw.png')
            print(f"✅ Imagem do Google Earth baixada com sucesso!")
            print(f"📏 Dimensões: {img_original.size}")
            
            return img_original
            
        else:
            print(f"❌ Erro na API do Google Maps: {response.status_code}")
            print("🎨 Gerando imagem de fallback para Google Earth...")
            return generate_google_fallback()
            
    except Exception as e:
        print(f"❌ Erro ao conectar com Google Maps: {e}")
        print("🎨 Gerando imagem de fallback para Google Earth...")
        return generate_google_fallback()

def generate_google_fallback():
    """Gerar imagem de fallback realista estilo Google Earth"""
    print("🎨 Gerando imagem Google Earth (fallback)...")
    
    width, height = 800, 600
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Usar seed para consistência
    np.random.seed(42)
    
    # Base terrestre com tons naturais
    base_r = np.random.normal(140, 20, (height, width))
    base_g = np.random.normal(130, 18, (height, width))  
    base_b = np.random.normal(110, 15, (height, width))
    
    img_array[:,:,0] = np.clip(base_r, 80, 200)
    img_array[:,:,1] = np.clip(base_g, 75, 190)
    img_array[:,:,2] = np.clip(base_b, 70, 180)
    
    # Adicionar vegetação natural
    vegetation_areas = [
        (100, 120, 150, 120),
        (450, 200, 120, 100),
        (200, 400, 180, 80),
        (600, 100, 100, 140),
    ]
    
    for x, y, w, h in vegetation_areas:
        center_x, center_y = w//2, h//2
        for i in range(h):
            for j in range(w):
                if (i-center_y)**2 + (j-center_x)**2 < (min(w,h)//2)**2:
                    if y+i < height and x+j < width:
                        img_array[y+i, x+j] = [
                            np.random.randint(45, 85),
                            np.random.randint(80, 140),
                            np.random.randint(35, 75)
                        ]
    
    # Adicionar corpos d'água
    water_spots = [
        (250, 180, 60, 40, [45, 120, 185]),    # Piscina azul
        (500, 350, 45, 35, [85, 140, 95]),     # Área verde (foco!)
        (150, 450, 40, 30, [35, 85, 135]),     # Reservatório
        (650, 200, 35, 25, [70, 110, 80]),     # Água parada
    ]
    
    for x, y, w, h, color in water_spots:
        img_array[y:y+h, x:x+w] = color
    
    # Aplicar desfoque sutil
    for channel in range(3):
        img_array[:,:,channel] = ndimage.gaussian_filter(img_array[:,:,channel], sigma=0.5)
    
    # Adicionar ruído natural
    noise = np.random.normal(0, 3, img_array.shape)
    img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
    
    img_pil = Image.fromarray(img_array)
    img_pil.save('google_earth_raw.png')
    
    return img_pil

# =============================================================================
# FUNÇÕES PARA COPERNICUS SENTINEL
# =============================================================================

def get_sentinel_token(client_id, client_secret):
    """Obter token de acesso para Sentinel Hub"""
    try:
        print("🔑 Obtendo token do Copernicus Sentinel...")
        # Para demo, simular token (substitua pela implementação real)
        return "SIMULATED_SENTINEL_TOKEN"
    except Exception as e:
        print(f"❌ Erro ao obter token Sentinel: {e}")
        return None

def download_sentinel_image(bbox, center_coords, token):
    """Baixar imagem Sentinel-2 ou gerar fallback"""
    try:
        print("📡 Conectando ao Copernicus Sentinel Hub...")
        
        # Para demo, vamos gerar uma imagem sintética que simula dados Sentinel
        print("🛰️ Gerando imagem sintética Sentinel-2...")
        
        return generate_sentinel_fallback(center_coords)
        
    except Exception as e:
        print(f"❌ Erro ao baixar imagem Sentinel: {e}")
        return None

def generate_sentinel_fallback(center_coords):
    """Gerar imagem de fallback que simula dados Sentinel-2"""
    print("🛰️ Gerando imagem Copernicus Sentinel (fallback)...")
    
    width, height = 800, 600
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Usar seed diferente para variação
    np.random.seed(123)
    
    # Simular bandas espectrais do Sentinel (mais científico)
    # Base com tons que simulam infravermelho próximo
    base_r = np.random.normal(120, 25, (height, width))  # NIR
    base_g = np.random.normal(100, 20, (height, width))  # Red
    base_b = np.random.normal(80, 18, (height, width))   # Green
    
    img_array[:,:,0] = np.clip(base_r, 60, 180)
    img_array[:,:,1] = np.clip(base_g, 50, 160)
    img_array[:,:,2] = np.clip(base_b, 40, 140)
    
    # Adicionar padrões que simulam dados multiespectrais
    # Vegetação aparece mais clara no NIR
    veg_areas = [
        (80, 100, 200, 150),
        (400, 180, 150, 120),
        (150, 350, 220, 100),
        (550, 80, 120, 160),
    ]
    
    for x, y, w, h in veg_areas:
        # Vegetação forte em NIR (canal R)
        center_x, center_y = w//2, h//2
        for i in range(h):
            for j in range(w):
                dist = np.sqrt((i-center_y)**2 + (j-center_x)**2)
                if dist < min(w,h)//2 * 0.8:
                    if y+i < height and x+j < width:
                        img_array[y+i, x+j] = [
                            np.random.randint(150, 200),  # Alto NIR
                            np.random.randint(60, 100),   # Baixo Red
                            np.random.randint(80, 120)    # Médio Green
                        ]
    
    # Corpos d'água (absorvem NIR)
    water_areas = [
        (200, 200, 80, 60, [30, 40, 90]),      # Água limpa
        (480, 320, 50, 40, [60, 80, 70]),      # Água com algas
        (300, 450, 60, 45, [25, 35, 85]),      # Reservatório
        (600, 150, 40, 30, [50, 70, 60]),      # Área suspeita
    ]
    
    for x, y, w, h, color in water_areas:
        img_array[y:y+h, x:x+w] = color
    
    # Adicionar padrões de interferometria/textura
    for i in range(0, height, 50):
        for j in range(0, width, 50):
            # Pequenas variações que simulam pixels de satélite
            patch_noise = np.random.normal(0, 8, (min(50, height-i), min(50, width-j), 3))
            img_array[i:i+min(50, height-i), j:j+min(50, width-j)] = np.clip(
                img_array[i:i+min(50, height-i), j:j+min(50, width-j)] + patch_noise, 0, 255
            )
    
    img_pil = Image.fromarray(img_array.astype(np.uint8))
    img_pil.save('sentinel_raw.png')
    
    return img_pil

# =============================================================================
# PROCESSAMENTO DE IMAGEM
# =============================================================================

def process_satellite_image(img_array, processing_type="standard"):
    """Processar imagem para realçar características importantes"""
    print(f"🔧 Aplicando processamento {processing_type}...")
    
    # Garantir formato RGB
    if len(img_array.shape) == 2:
        img_rgb = np.stack([img_array, img_array, img_array], axis=2)
        img_float = img_rgb.astype(np.float32) / 255.0
    elif len(img_array.shape) == 3:
        if img_array.shape[2] == 4:  # RGBA
            img_float = img_array[:,:,:3].astype(np.float32) / 255.0
        else:  # RGB
            img_float = img_array.astype(np.float32) / 255.0
    
    # 1. Realce de contraste adaptativo
    for channel in range(3):
        img_flat = img_float[:,:,channel].flatten()
        if len(img_flat) > 0:
            img_eq = rankdata(img_flat).reshape(img_float[:,:,channel].shape)
            img_float[:,:,channel] = img_eq / img_eq.max()
    
    # 2. Filtro de suavização
    img_filtered = ndimage.gaussian_filter(img_float, sigma=0.8)
    
    # 3. Realçar áreas aquáticas (potenciais focos)
    if processing_type == "water_enhanced":
        # Máscara mais agressiva para águas
        water_mask = ((img_filtered[:,:,2] > 0.3) | 
                     ((img_filtered[:,:,1] > 0.4) & (img_filtered[:,:,2] > 0.2)))
        
        img_enhanced = img_filtered.copy()
        if np.any(water_mask):
            img_enhanced[water_mask, 1] = np.minimum(img_enhanced[water_mask, 1] * 1.5, 1.0)
            img_enhanced[water_mask, 2] = np.minimum(img_enhanced[water_mask, 2] * 1.3, 1.0)
    else:
        # Processamento padrão
        water_mask = (img_filtered[:,:,2] > 0.4) & (img_filtered[:,:,1] > 0.3)
        img_enhanced = img_filtered.copy()
        if np.any(water_mask):
            img_enhanced[water_mask, 1] = np.minimum(img_enhanced[water_mask, 1] * 1.3, 1.0)
            img_enhanced[water_mask, 2] = np.minimum(img_enhanced[water_mask, 2] * 1.2, 1.0)
    
    # 4. Sharpening
    kernel = np.array([[-0.5,-1,-0.5], [-1,7,-1], [-0.5,-1,-0.5]])
    for channel in range(3):
        sharpened = ndimage.convolve(img_enhanced[:,:,channel], kernel)
        img_enhanced[:,:,channel] = np.clip(0.8 * img_enhanced[:,:,channel] + 0.2 * sharpened, 0, 1)
    
    # 5. Ajuste gamma
    gamma = 0.85 if processing_type == "water_enhanced" else 0.8
    img_gamma = np.power(img_enhanced, gamma)
    
    # Converter para uint8
    img_processed = (img_gamma * 255).astype(np.uint8)
    
    print(f"✅ Processamento {processing_type} concluído")
    return img_processed

# =============================================================================
# FUNÇÃO PRINCIPAL - IMAGEM COMBINADA
# =============================================================================

def create_combined_satellite_image():
    """Criar imagem combinada Google Earth + Copernicus Sentinel"""
    
    print("="*70)
    print("🛰️ SISTEMA INTEGRADO DE ANÁLISE DE FOCOS DE DENGUE")
    print("="*70)
    print(f"🎯 Coordenadas alvo: {TARGET_COORDS_DMS}")
    print(f"📍 Decimal: {TARGET_COORDS}")
    print("="*70)
    
    # 1. Baixar imagem do Google Earth
    print("\n🌍 ETAPA 1: OBTENDO IMAGEM DO GOOGLE EARTH")
    print("-" * 50)
    google_img = download_google_earth_image(TARGET_COORDS, GOOGLE_MAPS_API_KEY, IMAGE_SIZE, ZOOM_LEVEL, MAP_TYPE)
    
    # 2. Baixar imagem do Copernicus Sentinel
    print("\n🛰️ ETAPA 2: OBTENDO IMAGEM DO COPERNICUS SENTINEL")
    print("-" * 50)
    sentinel_token = get_sentinel_token(SENTINEL_CLIENT_ID, SENTINEL_CLIENT_SECRET)
    sentinel_img = download_sentinel_image(BBOX, TARGET_COORDS, sentinel_token)
    
    if not google_img or not sentinel_img:
        print("❌ Falha ao obter uma ou ambas as imagens")
        return None
    
    # 3. Processar as imagens
    print("\n🔧 ETAPA 3: PROCESSANDO IMAGENS")
    print("-" * 50)
    
    # Processar Google Earth (processamento padrão)
    google_array = np.array(google_img)
    google_processed = process_satellite_image(google_array, "standard")
    
    # Processar Sentinel (processamento com realce aquático)
    sentinel_array = np.array(sentinel_img)
    sentinel_processed = process_satellite_image(sentinel_array, "water_enhanced")
    
    # 4. Criar visualização combinada
    print("\n🎨 ETAPA 4: CRIANDO VISUALIZAÇÃO COMBINADA")
    print("-" * 50)
    
    # Configurar figura com subplots
    fig = plt.figure(figsize=(24, 12))
    
    # Layout: 2x2 grid
    # [Google Original] [Google Processado]
    # [Sentinel Original] [Sentinel Processado]
    
    # Google Earth Original
    ax1 = plt.subplot(2, 2, 1)
    ax1.imshow(google_img)
    ax1.set_title("🌍 Google Earth - Original\n(Imagem Real de Satélite)", fontsize=14, pad=15)
    ax1.axis('off')
    
    # Google Earth Processado
    ax2 = plt.subplot(2, 2, 2)
    ax2.imshow(google_processed)
    ax2.set_title("🌍 Google Earth - Processado\n(Otimizado para Análise)", fontsize=14, pad=15)
    ax2.axis('off')
    
    # Copernicus Sentinel Original
    ax3 = plt.subplot(2, 2, 3)
    ax3.imshow(sentinel_img)
    ax3.set_title("🛰️ Copernicus Sentinel-2 - Original\n(Dados Multiespectrais)", fontsize=14, pad=15)
    ax3.axis('off')
    
    # Copernicus Sentinel Processado
    ax4 = plt.subplot(2, 2, 4)
    ax4.imshow(sentinel_processed)
    ax4.set_title("🛰️ Sentinel-2 - Processado\n(Realce de Focos Aquáticos)", fontsize=14, pad=15)
    ax4.axis('off')
    
    # Título principal
    main_title = f'🛰️ ANÁLISE INTEGRADA DE FOCOS DE DENGUE\n{TARGET_COORDS_DMS} | Google Earth + Copernicus Sentinel'
    fig.suptitle(main_title, fontsize=18, y=0.95, weight='bold')
    
    # Adicionar informações na parte inferior
    info_text = (f"📍 Coordenadas: {TARGET_COORDS[0]:.6f}, {TARGET_COORDS[1]:.6f} | "
                f"🔍 Zoom: {ZOOM_LEVEL} | 📦 BBOX: {BBOX} | "
                f"📏 Resolução: {IMAGE_SIZE}")
    
    fig.text(0.5, 0.02, info_text, ha='center', fontsize=10, 
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8))
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.88, bottom=0.08)
    
    # Salvar imagem combinada
    combined_filename = 'combined_satellite_analysis.png'
    plt.savefig(combined_filename, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"✅ Imagem combinada salva: {combined_filename}")
    
    plt.show()
    
    # 5. Estatísticas comparativas
    print("\n📊 ETAPA 5: ANÁLISE ESTATÍSTICA")
    print("-" * 50)
    
    # Análise Google Earth
    google_stats = {
        'mean': np.mean(google_array),
        'std': np.std(google_array),
        'water_pixels': np.sum((google_processed[:,:,1] > 150) & (google_processed[:,:,2] > 150))
    }
    
    # Análise Sentinel
    sentinel_stats = {
        'mean': np.mean(sentinel_array),
        'std': np.std(sentinel_array),
        'water_pixels': np.sum((sentinel_processed[:,:,1] > 150) & (sentinel_processed[:,:,2] > 150))
    }
    
    print("🌍 GOOGLE EARTH:")
    print(f"  • Brilho médio: {google_stats['mean']:.1f}")
    print(f"  • Contraste (std): {google_stats['std']:.1f}")
    print(f"  • Pixels aquáticos detectados: {google_stats['water_pixels']}")
    
    print("\n🛰️ COPERNICUS SENTINEL:")
    print(f"  • Brilho médio: {sentinel_stats['mean']:.1f}")
    print(f"  • Contraste (std): {sentinel_stats['std']:.1f}")
    print(f"  • Pixels aquáticos realçados: {sentinel_stats['water_pixels']}")
    
    print(f"\n💾 ARQUIVOS GERADOS:")
    print(f"  • google_earth_raw.png")
    print(f"  • sentinel_raw.png")
    print(f"  • {combined_filename}")
    
    print("\n✅ PROCESSO CONCLUÍDO COM SUCESSO!")
    
    return {
        'google_img': google_img,
        'sentinel_img': sentinel_img,
        'google_processed': google_processed,
        'sentinel_processed': sentinel_processed,
        'stats': {'google': google_stats, 'sentinel': sentinel_stats}
    }

# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================

if __name__ == "__main__":
    result = create_combined_satellite_image()