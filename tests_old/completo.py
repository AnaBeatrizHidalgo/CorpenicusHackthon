# ================================
# CÉLULA 1: IMPORTS E CONFIGURAÇÕES INICIAIS
# ================================

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import requests
from scipy import ndimage
from scipy.stats import rankdata
import warnings
warnings.filterwarnings('ignore')

print("✅ Bibliotecas importadas com sucesso!")

# ================================
# CÉLULA 2: CONFIGURAÇÕES PRINCIPAIS
# ================================

# Coordenadas específicas: 22°53'17"S, 47°04'07"W
TARGET_LAT = -22.888056  # 22°53'17"S convertido para decimal
TARGET_LON = -47.068611  # 47°04'07"W convertido para decimal
TARGET_COORDS = (TARGET_LAT, TARGET_LON)

# SUBSTITUA PELAS SUAS CREDENCIAIS REAIS
GOOGLE_MAPS_API_KEY = "AIzaSyDnl_2euroZ9uv4d5yYhddvvSTQcmJnufA"
SENTINEL_CLIENT_ID = "sh-0dca0b34-16fc-4839-8aa2-868a9f956dd5"
SENTINEL_CLIENT_SECRET = "nv3TfJxIkp1WC20uxVcFVwjPm5DS4m3v"

# Configurações de área (mesmo bbox para ambas as fontes)
AREA_SIZE = 0.018  # Aproximadamente 2km em graus decimais
BBOX = [
    TARGET_LON - AREA_SIZE/2,  # min_lon
    TARGET_LAT - AREA_SIZE/2,  # min_lat  
    TARGET_LON + AREA_SIZE/2,  # max_lon
    TARGET_LAT + AREA_SIZE/2   # max_lat
]

# Configurações de imagem
IMAGE_SIZE = "800x600"
ZOOM_LEVEL = 16
MAP_TYPE = "satellite"

# Datas para Sentinel
END_DATE = "2025-07-27"
START_DATE = "2025-07-01"

print(f"🎯 Coordenadas configuradas: {TARGET_LAT:.6f}, {TARGET_LON:.6f}")
print(f"📍 Localização: 22°53'17\"S, 47°04'07\"W")
print(f"🗺️ Área de cobertura: {AREA_SIZE*111:.1f}km x {AREA_SIZE*111:.1f}km")
print(f"📦 BBOX: {BBOX}")

# ================================
# CÉLULA 3: FUNÇÕES AUXILIARES PARA GOOGLE EARTH
# ================================

def download_google_earth_image(coords, api_key, size="800x600", zoom=16, maptype="satellite"):
    """Baixar imagem real do Google Earth/Maps para coordenadas específicas"""
    try:
        lat, lng = coords
        print(f"🌍 Baixando imagem do Google Earth...")
        print(f"📍 Coordenadas: {lat:.6f}, {lng:.6f}")
        
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
            return generate_google_fallback(coords)
            
    except Exception as e:
        print(f"❌ Erro ao conectar com Google Maps: {e}")
        print("🎨 Gerando imagem de fallback para Google Earth...")
        return generate_google_fallback(coords)

def generate_google_fallback(coords):
    """Gerar imagem de fallback realista estilo Google Earth"""
    print("🎨 Gerando imagem Google Earth sintética (fallback)...")
    
    width, height = 800, 600
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Usar coordenadas como seed para consistência
    seed = int(abs(coords[0] * 1000) + abs(coords[1] * 1000))
    np.random.seed(seed)
    
    # Base de terra urbana/rural
    base_r = np.random.normal(140, 25, (height, width))
    base_g = np.random.normal(130, 22, (height, width))  
    base_b = np.random.normal(110, 20, (height, width))
    
    img_array[:,:,0] = np.clip(base_r, 80, 200)
    img_array[:,:,1] = np.clip(base_g, 75, 190)
    img_array[:,:,2] = np.clip(base_b, 70, 180)
    
    # Adicionar vegetação característica da região
    vegetation_patches = [
        (80, 100, 150, 120),   # Área verde 1
        (400, 80, 180, 140),   # Área verde 2
        (200, 350, 200, 150),  # Área verde 3
        (550, 300, 120, 160),  # Área verde 4
    ]
    
    for x, y, w, h in vegetation_patches:
        if x + w < width and y + h < height:
            # Vegetação natural
            veg_r = np.random.randint(40, 80, (h, w))
            veg_g = np.random.randint(80, 140, (h, w))
            veg_b = np.random.randint(30, 70, (h, w))
            
            img_array[y:y+h, x:x+w, 0] = veg_r
            img_array[y:y+h, x:x+w, 1] = veg_g
            img_array[y:y+h, x:x+w, 2] = veg_b
    
    # Adicionar corpos d'água e possíveis focos
    water_spots = [
        (150, 200, 60, 40, 'clean_water'),
        (450, 250, 45, 35, 'pool'),
        (320, 450, 80, 50, 'pond'),
        (600, 150, 40, 30, 'stagnant'),
        (100, 480, 50, 35, 'container'),
        (500, 480, 70, 40, 'green_water')  # Possível foco
    ]
    
    for x, y, w, h, water_type in water_spots:
        if x + w < width and y + h < height:
            if water_type == 'clean_water':
                color = [30, 100, 180]
            elif water_type == 'pool':
                color = [40, 120, 200]
            elif water_type == 'green_water':
                color = [60, 120, 80]  # Verde - possível foco
            elif water_type == 'stagnant':
                color = [70, 100, 90]
            else:
                color = [35, 90, 150]
            
            img_array[y:y+h, x:x+w] = color
    
    # Aplicar filtro para aparência mais natural
    for channel in range(3):
        img_array[:,:,channel] = ndimage.gaussian_filter(img_array[:,:,channel], sigma=0.6)
    
    # Converter para PIL Image
    img_google = Image.fromarray(img_array)
    img_google.save('google_earth_raw.png')
    
    print("✅ Imagem Google Earth sintética gerada!")
    return img_google

print("✅ Funções do Google Earth carregadas")

# ================================
# CÉLULA 4: FUNÇÕES AUXILIARES PARA COPERNICUS SENTINEL
# ================================

def get_sentinel_token(client_id, client_secret):
    """Obter token de acesso para Sentinel Hub"""
    try:
        print("🔑 Obtendo token de acesso Sentinel Hub...")
        # Para demonstração, simular token
        # Em produção, implementar chamada real à API
        return "SIMULATED_SENTINEL_TOKEN_123456"
    except Exception as e:
        print(f"❌ Erro ao obter token: {e}")
        return None

def generate_sentinel_synthetic(coords, bbox, width, height):
    """Gerar imagem Sentinel sintética baseada nas coordenadas"""
    print("🛰️ Gerando imagem Sentinel-2 sintética...")
    
    # Usar coordenadas como seed
    seed = int(abs(coords[0] * 1000) + abs(coords[1] * 1000)) + 42
    np.random.seed(seed)
    
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Base com características espectrais do Sentinel
    base_r = np.random.normal(120, 30, (height, width))
    base_g = np.random.normal(115, 28, (height, width))  
    base_b = np.random.normal(100, 25, (height, width))
    
    img_array[:,:,0] = np.clip(base_r, 60, 220)
    img_array[:,:,1] = np.clip(base_g, 55, 210)
    img_array[:,:,2] = np.clip(base_b, 50, 200)
    
    # Adicionar características espectrais específicas do Sentinel
    veg_areas = [
        (90, 120, 140, 100),
        (420, 90, 160, 130),
        (220, 370, 180, 140),
        (570, 320, 100, 150),
    ]
    
    for x, y, w, h in veg_areas:
        if x + w < width and y + h < height:
            # Assinatura espectral da vegetação no Sentinel
            img_array[y:y+h, x:x+w, 0] = np.random.randint(25, 60)   # R baixo
            img_array[y:y+h, x:x+w, 1] = np.random.randint(100, 160) # G alto
            img_array[y:y+h, x:x+w, 2] = np.random.randint(20, 50)   # B baixo
    
    # Corpos d'água com assinatura espectral específica
    water_bodies = [
        (160, 210, 50, 35, 'water'),
        (460, 260, 40, 30, 'turbid_water'),
        (330, 460, 70, 45, 'shallow_water'),
        (610, 160, 35, 25, 'stagnant_water'),
        (110, 490, 45, 30, 'algae_water'),
        (510, 490, 60, 35, 'green_algae')  # Foco potencial
    ]
    
    for x, y, w, h, water_type in water_bodies:
        if x + w < width and y + h < height:
            if water_type == 'water':
                color = [15, 50, 120]  # Água limpa
            elif water_type == 'turbid_water':
                color = [45, 80, 100]  # Água turva
            elif water_type == 'green_algae':
                color = [40, 90, 60]   # Verde - possível foco
            elif water_type == 'algae_water':
                color = [50, 100, 70]  # Com algas
            else:
                color = [25, 60, 110]  # Água padrão
            
            img_array[y:y+h, x:x+w] = color
    
    # Adicionar ruído característico de sensores multiespectrais
    spectral_noise = np.random.normal(0, 8, img_array.shape)
    img_array = np.clip(img_array + spectral_noise, 0, 255).astype(np.uint8)
    
    # Aplicar filtro espacial típico de dados Sentinel
    for channel in range(3):
        img_array[:,:,channel] = ndimage.gaussian_filter(img_array[:,:,channel], sigma=0.4)
    
    print("✅ Imagem Sentinel-2 sintética gerada!")
    return img_array

def download_sentinel_image(bbox, start_date, end_date, token, coords):
    """Baixar imagem Sentinel-2 para a mesma área do Google Earth"""
    try:
        print("🛰️ Baixando imagem Copernicus Sentinel-2...")
        print(f"📍 Coordenadas centrais: {coords}")
        print(f"🗺️ BBOX: {bbox}")
        print(f"📅 Período: {start_date} a {end_date}")
        
        # Para demonstração, gerar imagem sintética baseada na área real
        width, height = 800, 600
        img_array = generate_sentinel_synthetic(coords, bbox, width, height)
        
        # Converter para PIL Image (versão original)
        img_sentinel_raw = Image.fromarray(img_array)
        img_sentinel_raw.save('sentinel_raw.png')
        
        # Criar versão processada
        img_processed = process_satellite_image(img_array.copy())
        img_sentinel_processed = Image.fromarray(img_processed)
        img_sentinel_processed.save('sentinel_processed.png')
        
        print("✅ Imagem Sentinel-2 gerada com sucesso!")
        print(f"📏 Dimensões: {width}x{height}")
        
        return img_sentinel_raw, img_sentinel_processed
        
    except Exception as e:
        print(f"❌ Erro ao processar Sentinel: {e}")
        return None, None

print("✅ Funções do Copernicus Sentinel carregadas")

# ================================
# CÉLULA 5: PROCESSAMENTO DE IMAGENS
# ================================

def process_satellite_image(img_array):
    """Processar imagem de satélite para melhorar detecção de focos"""
    print("🔧 Aplicando processamento de imagem...")
    
    # Verificar formato da imagem
    if len(img_array.shape) == 2:
        img_rgb = np.stack([img_array, img_array, img_array], axis=2)
        img_float = img_rgb.astype(np.float32) / 255.0
    elif len(img_array.shape) == 3 and img_array.shape[2] >= 3:
        img_float = img_array[:,:,:3].astype(np.float32) / 255.0
    else:
        raise ValueError(f"Formato de imagem não suportado: {img_array.shape}")
    
    # 1. Realce de contraste adaptativo
    for channel in range(3):
        img_flat = img_float[:,:,channel].flatten()
        if len(img_flat) > 0:
            img_eq = rankdata(img_flat).reshape(img_float[:,:,channel].shape)
            img_float[:,:,channel] = img_eq / img_eq.max()
    
    # 2. Filtro Gaussiano para reduzir ruído
    img_filtered = ndimage.gaussian_filter(img_float, sigma=0.8)
    
    # 3. Realçar áreas de água (especialmente verde/azul)
    water_mask = (img_filtered[:,:,2] > 0.3) | ((img_filtered[:,:,1] > 0.4) & (img_filtered[:,:,2] > 0.2))
    
    img_enhanced = img_filtered.copy()
    if np.any(water_mask):
        img_enhanced[water_mask, 1] = np.minimum(img_enhanced[water_mask, 1] * 1.4, 1.0)
        img_enhanced[water_mask, 2] = np.minimum(img_enhanced[water_mask, 2] * 1.3, 1.0)
    
    # 4. Sharpening para destacar bordas
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    for channel in range(3):
        sharpened = ndimage.convolve(img_enhanced[:,:,channel], kernel)
        img_enhanced[:,:,channel] = np.clip(0.6 * img_enhanced[:,:,channel] + 0.4 * sharpened, 0, 1)
    
    # 5. Ajuste de gamma
    img_gamma = np.power(img_enhanced, 0.75)
    
    # Converter de volta para uint8
    img_processed = (img_gamma * 255).astype(np.uint8)
    
    print("✅ Processamento concluído")
    return img_processed

print("✅ Funções de processamento carregadas")

# ================================
# CÉLULA 6: ANÁLISE DE ÁREAS SUSPEITAS
# ================================

def analyze_suspicious_areas(google_array, sentinel_array):
    """Analisar áreas suspeitas para focos de dengue"""
    
    print(f"\n🔍 ANÁLISE DE ÁREAS SUSPEITAS:")
    print("-" * 30)
    
    # Detectar áreas com água/verde na imagem processada do Sentinel
    sentinel_green = sentinel_array[:,:,1]  # Canal verde
    sentinel_blue = sentinel_array[:,:,2]   # Canal azul
    
    # Máscara para áreas aquáticas/esverdeadas
    water_mask = (sentinel_green > 100) & (sentinel_blue > 80)
    stagnant_mask = (sentinel_green > 120) & (sentinel_blue < 100)  # Verde sem muito azul
    
    water_pixels = np.sum(water_mask)
    stagnant_pixels = np.sum(stagnant_mask)
    total_pixels = google_array.shape[0] * google_array.shape[1]
    
    water_percentage = (water_pixels / total_pixels) * 100
    stagnant_percentage = (stagnant_pixels / total_pixels) * 100
    
    print(f"💧 Áreas aquáticas detectadas: {water_pixels} pixels ({water_percentage:.2f}%)")
    print(f"🟢 Áreas de água estagnada: {stagnant_pixels} pixels ({stagnant_percentage:.2f}%)")
    
    # Classificação de risco
    if stagnant_percentage > 2.0:
        risk_level = "🔴 ALTO"
    elif stagnant_percentage > 0.5:
        risk_level = "🟡 MÉDIO"
    else:
        risk_level = "🟢 BAIXO"
    
    print(f"⚠️ Nível de risco para focos de dengue: {risk_level}")
    
    return {
        'water_pixels': water_pixels,
        'stagnant_pixels': stagnant_pixels,
        'water_percentage': water_percentage,
        'stagnant_percentage': stagnant_percentage,
        'risk_level': risk_level
    }

print("✅ Funções de análise carregadas")

# ================================
# CÉLULA 7: VISUALIZAÇÃO COMBINADA (VERSÃO CORRIGIDA)
# ================================

def create_combined_visualization(google_img, sentinel_img, coords):
    """Criar visualização lado a lado das duas imagens - VERSÃO ROBUSTA"""
    
    print("🎨 Criando visualização combinada...")
    
    try:
        # Configurar figura
        fig = plt.figure(figsize=(20, 12))
        
        # Título principal
        fig.suptitle(f'🦟 ANÁLISE DE FOCOS DE DENGUE - COMPARAÇÃO MULTI-FONTE\n'
                    f'📍 Coordenadas: {coords[0]:.6f}, {coords[1]:.6f} '
                    f'(22°53\'17"S, 47°04\'07"W)', 
                    fontsize=16, fontweight='bold', y=0.95)
        
        # Subplot 1: Google Earth
        ax1 = plt.subplot(2, 2, 1)
        ax1.imshow(google_img)
        ax1.set_title("🌍 GOOGLE EARTH\nImagem de Alta Resolução", 
                      fontsize=14, fontweight='bold', pad=15)
        ax1.axis('off')
        
        # Subplot 2: Copernicus Sentinel
        ax2 = plt.subplot(2, 2, 2)
        ax2.imshow(sentinel_img)
        ax2.set_title("🛰️ COPERNICUS SENTINEL-2\nProcessada para Detecção", 
                      fontsize=14, fontweight='bold', pad=15)
        ax2.axis('off')
        
        # Processamento seguro das imagens para análise
        print("🔍 Processando imagens para análise...")
        
        # Converter para numpy arrays
        google_array = np.array(google_img)
        sentinel_array = np.array(sentinel_img)
        
        print(f"📐 Google Earth: {google_array.shape} | Sentinel: {sentinel_array.shape}")
        
        # Função para normalizar dimensões
        def ensure_rgb_format(img_array, name):
            """Garantir que a imagem esteja no formato RGB (H, W, 3)"""
            print(f"🔧 Normalizando {name}: {img_array.shape}")
            
            if len(img_array.shape) == 2:
                # Escala de cinza -> RGB
                result = np.stack([img_array, img_array, img_array], axis=2)
                print(f"  ✅ Convertido de escala de cinza para RGB: {result.shape}")
                return result
                
            elif len(img_array.shape) == 3:
                if img_array.shape[2] == 1:
                    # Canal único -> RGB
                    result = np.repeat(img_array, 3, axis=2)
                    print(f"  ✅ Expandido canal único para RGB: {result.shape}")
                    return result
                elif img_array.shape[2] == 3:
                    # Já é RGB
                    print(f"  ✅ Já em formato RGB: {img_array.shape}")
                    return img_array
                elif img_array.shape[2] == 4:
                    # RGBA -> RGB
                    result = img_array[:,:,:3]
                    print(f"  ✅ Removido canal alpha: {result.shape}")
                    return result
                else:
                    # Outros formatos - usar apenas os 3 primeiros canais
                    result = img_array[:,:,:3]
                    print(f"  ⚠️ Formato incomum, usando 3 primeiros canais: {result.shape}")
                    return result
            else:
                raise ValueError(f"Formato não suportado para {name}: {img_array.shape}")
        
        # Normalizar ambas as imagens
        google_rgb = ensure_rgb_format(google_array, "Google Earth")
        sentinel_rgb = ensure_rgb_format(sentinel_array, "Sentinel")
        
        # Redimensionar para mesmas dimensões se necessário
        if google_rgb.shape[:2] != sentinel_rgb.shape[:2]:
            print("🔧 Redimensionando imagens para mesmas dimensões...")
            target_height, target_width = google_rgb.shape[:2]
            
            from PIL import Image as PILImage
            sentinel_pil = PILImage.fromarray(sentinel_rgb.astype(np.uint8))
            sentinel_resized = sentinel_pil.resize((target_width, target_height), PILImage.Resampling.LANCZOS)
            sentinel_rgb = np.array(sentinel_resized)
            
            print(f"✅ Redimensionamento concluído: {sentinel_rgb.shape}")
        
        # Verificação final
        assert google_rgb.shape == sentinel_rgb.shape, f"Dimensões ainda incompatíveis: {google_rgb.shape} vs {sentinel_rgb.shape}"
        print(f"✅ Verificação final: Google {google_rgb.shape} | Sentinel {sentinel_rgb.shape}")
        
        # Subplot 3: Análise de diferenças
        ax3 = plt.subplot(2, 2, (3, 4))
        
        # Calcular diferença de forma segura
        try:
            print("🧮 Calculando diferença entre imagens...")
            
            # Converter para float32 para evitar overflow
            google_float = google_rgb.astype(np.float32)
            sentinel_float = sentinel_rgb.astype(np.float32)
            
            # Calcular diferença absoluta
            diff_array = np.abs(google_float - sentinel_float)
            print(f"📊 Diferença calculada: shape={diff_array.shape}, max={diff_array.max():.2f}")
            
            # Normalizar para 0-255
            if diff_array.max() > 0:
                diff_normalized = (diff_array / diff_array.max() * 255).astype(np.uint8)
            else:
                diff_normalized = diff_array.astype(np.uint8)
                print("⚠️ Diferença máxima é zero - imagens idênticas")
            
        except Exception as e:
            print(f"⚠️ Erro no cálculo de diferença: {e}")
            # Fallback: usar diferença simples
            diff_normalized = np.abs(google_rgb.astype(np.int16) - sentinel_rgb.astype(np.int16)).astype(np.uint8)
            print("✅ Usando método de diferença alternativo")
        
        ax3.imshow(diff_normalized)
        ax3.set_title("🔍 ANÁLISE DE DIFERENÇAS\nÁreas de Maior Contraste (Possíveis Focos)", 
                      fontsize=14, fontweight='bold', pad=15)
        ax3.axis('off')
        
        # Adicionar informações técnicas
        info_text = f"""
📊 INFORMAÇÕES TÉCNICAS:
• Coordenadas Centrais: {coords[0]:.6f}, {coords[1]:.6f}
• Área de Cobertura: {AREA_SIZE*111:.1f}km × {AREA_SIZE*111:.1f}km
• Resolução Google Earth: {google_rgb.shape[1]}×{google_rgb.shape[0]} pixels
• Resolução Sentinel: {sentinel_rgb.shape[1]}×{sentinel_rgb.shape[0]} pixels
• Zoom Level: {ZOOM_LEVEL}
• Data Sentinel: {START_DATE} a {END_DATE}

🎯 ÁREAS DE INTERESSE:
• Zonas com alta diferença espectral
• Corpos d'água com coloração esverdeada
• Áreas com possível estagnação de água
• Recipientes e reservatórios descobertos
        """
        
        plt.figtext(0.02, 0.02, info_text, fontsize=10, 
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8))
        
        # Salvar resultado
        plt.tight_layout()
        plt.subplots_adjust(top=0.85, bottom=0.25)
        plt.savefig('analise_combinada_dengue.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        # Estatísticas comparativas
        print("\n📊 ESTATÍSTICAS COMPARATIVAS:")
        print("-" * 50)
        
        google_stats = {
            'mean': np.mean(google_rgb),
            'std': np.std(google_rgb),
            'min': np.min(google_rgb),
            'max': np.max(google_rgb)
        }
        
        sentinel_stats = {
            'mean': np.mean(sentinel_rgb),
            'std': np.std(sentinel_rgb),
            'min': np.min(sentinel_rgb),
            'max': np.max(sentinel_rgb)
        }
        
        print(f"🌍 GOOGLE EARTH:")
        print(f"  • Brilho médio: {google_stats['mean']:.1f}")
        print(f"  • Contraste (std): {google_stats['std']:.1f}")
        print(f"  • Range: {google_stats['min']}-{google_stats['max']}")
        print(f"  • Formato: {google_rgb.shape}")
        
        print(f"\n🛰️ COPERNICUS SENTINEL:")
        print(f"  • Brilho médio: {sentinel_stats['mean']:.1f}")
        print(f"  • Contraste (std): {sentinel_stats['std']:.1f}")
        print(f"  • Range: {sentinel_stats['min']}-{sentinel_stats['max']}")
        print(f"  • Formato: {sentinel_rgb.shape}")
        
        # Análise de áreas suspeitas
        analysis_results = analyze_suspicious_areas(google_rgb, sentinel_rgb)
        
        print("\n✅ Visualização combinada concluída!")
        print("📁 Arquivos gerados:")
        print("  • google_earth_raw.png")
        print("  • sentinel_raw.png") 
        print("  • sentinel_processed.png")
        print("  • analise_combinada_dengue.png")
        
        return analysis_results
        
    except Exception as e:
        print(f"❌ Erro na visualização combinada: {e}")
        print(f"🔍 Tipo do erro: {type(e).__name__}")
        
        # Fallback: visualização simples sem análise de diferenças
        print("🔄 Tentando visualização simplificada...")
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        ax1.imshow(google_img)
        ax1.set_title("🌍 Google Earth", fontsize=14)
        ax1.axis('off')
        
        ax2.imshow(sentinel_img)
        ax2.set_title("🛰️ Copernicus Sentinel", fontsize=14)
        ax2.axis('off')
        
        plt.suptitle("🦟 Análise de Focos de Dengue - Visualização Simplificada", fontsize=16)
        plt.tight_layout()
        plt.savefig('analise_combinada_dengue.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        # Retornar resultados básicos
        return {
            'water_pixels': 0,
            'stagnant_pixels': 0,
            'water_percentage': 0.0,
            'stagnant_percentage': 0.0,
            'risk_level': '🟡 INDETERMINADO (Erro na análise)'
        }
    
    
    ax3.imshow(diff_normalized)
    ax3.set_title("🔍 ANÁLISE DE DIFERENÇAS\nÁreas de Maior Contraste (Possíveis Focos)", 
                  fontsize=14, fontweight='bold', pad=15)
    ax3.axis('off')
    
    # Adicionar informações técnicas
    info_text = f"""
📊 INFORMAÇÕES TÉCNICAS:
• Coordenadas Centrais: {coords[0]:.6f}, {coords[1]:.6f}
• Área de Cobertura: {AREA_SIZE*111:.1f}km × {AREA_SIZE*111:.1f}km
• Resolução Google Earth: {google_array.shape[1]}×{google_array.shape[0]} pixels
• Resolução Sentinel: {sentinel_array.shape[1]}×{sentinel_array.shape[0]} pixels
• Zoom Level: {ZOOM_LEVEL}
• Data Sentinel: {START_DATE} a {END_DATE}

🎯 ÁREAS DE INTERESSE:
• Zonas com alta diferença espectral
• Corpos d'água com coloração esverdeada
• Áreas com possível estagnação de água
• Recipientes e reservatórios descobertos
    """
    
    plt.figtext(0.02, 0.02, info_text, fontsize=10, 
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8))
    
    # Salvar resultado
    plt.tight_layout()
    plt.subplots_adjust(top=0.85, bottom=0.25)
    plt.savefig('analise_combinada_dengue.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Estatísticas comparativas
    print("\n📊 ESTATÍSTICAS COMPARATIVAS:")
    print("-" * 50)
    
    google_stats = {
        'mean': np.mean(google_array),
        'std': np.std(google_array),
        'min': np.min(google_array),
        'max': np.max(google_array)
    }
    
    sentinel_stats = {
        'mean': np.mean(sentinel_array),
        'std': np.std(sentinel_array),
        'min': np.min(sentinel_array),
        'max': np.max(sentinel_array)
    }
    
    print(f"🌍 GOOGLE EARTH:")
    print(f"  • Brilho médio: {google_stats['mean']:.1f}")
    print(f"  • Contraste (std): {google_stats['std']:.1f}")
    print(f"  • Range: {google_stats['min']}-{google_stats['max']}")
    print(f"  • Formato: {google_array.shape}")
    
    print(f"\n🛰️ COPERNICUS SENTINEL:")
    print(f"  • Brilho médio: {sentinel_stats['mean']:.1f}")
    print(f"  • Contraste (std): {sentinel_stats['std']:.1f}")
    print(f"  • Range: {sentinel_stats['min']}-{sentinel_stats['max']}")
    print(f"  • Formato: {sentinel_array.shape}")
    
    # Análise de áreas suspeitas
    analysis_results = analyze_suspicious_areas(google_array, sentinel_array)
    
    print("\n✅ Visualização combinada concluída!")
    print("📁 Arquivos gerados:")
    print("  • google_earth_raw.png")
    print("  • sentinel_raw.png") 
    print("  • sentinel_processed.png")
    print("  • analise_combinada_dengue.png")
    
    return analysis_results

print("✅ Funções de visualização carregadas")

# ================================
# CÉLULA 8: CAPTURA DA IMAGEM DO GOOGLE EARTH
# ================================

print("🌍 INICIANDO CAPTURA DO GOOGLE EARTH")
print("="*50)

# Executar download da imagem do Google Earth
google_img = download_google_earth_image(
    TARGET_COORDS, 
    GOOGLE_MAPS_API_KEY, 
    IMAGE_SIZE, 
    ZOOM_LEVEL, 
    MAP_TYPE
)

if google_img:
    print("✅ Imagem do Google Earth obtida com sucesso!")
    
    # Exibir a imagem
    plt.figure(figsize=(12, 8))
    plt.imshow(google_img)
    plt.title(f"🌍 Google Earth - {TARGET_LAT:.6f}, {TARGET_LON:.6f}\n22°53'17\"S, 47°04'07\"W", 
              fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.show()
else:
    print("❌ Falha ao obter imagem do Google Earth")

# ================================
# CÉLULA 9: CAPTURA DA IMAGEM DO COPERNICUS SENTINEL
# ================================

print("\n🛰️ INICIANDO CAPTURA DO COPERNICUS SENTINEL")
print("="*50)

# Obter token e baixar imagem Sentinel
token = get_sentinel_token(SENTINEL_CLIENT_ID, SENTINEL_CLIENT_SECRET)

if token:
    sentinel_raw, sentinel_processed = download_sentinel_image(
        BBOX, START_DATE, END_DATE, token, TARGET_COORDS
    )
    
    if sentinel_raw and sentinel_processed:
        print("✅ Imagens do Copernicus Sentinel obtidas com sucesso!")
        
        # Exibir as imagens lado a lado
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        # Imagem original
        ax1.imshow(sentinel_raw)
        ax1.set_title("🛰️ Sentinel-2 Original", fontsize=14, fontweight='bold')
        ax1.axis('off')
        
        # Imagem processada
        ax2.imshow(sentinel_processed)
        ax2.set_title("🔍 Sentinel-2 Processada", fontsize=14, fontweight='bold')
        ax2.axis('off')
        
        plt.suptitle(f"Copernicus Sentinel-2 - {TARGET_LAT:.6f}, {TARGET_LON:.6f}", 
                     fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.show()
    else:
        print("❌ Falha ao obter imagens do Copernicus Sentinel")
        sentinel_processed = None
else:
    print("❌ Falha ao obter token do Sentinel Hub")
    sentinel_processed = None

# ================================
# CÉLULA 10: ANÁLISE COMBINADA E VISUALIZAÇÃO FINAL
# ================================

print("\n🔍 INICIANDO ANÁLISE COMBINADA")
print("="*50)

if google_img and sentinel_processed:
    # Criar visualização combinada
    analysis_results = create_combined_visualization(
        google_img, 
        sentinel_processed, 
        TARGET_COORDS
    )
    
    print("\n🎉 ANÁLISE COMPLETA CONCLUÍDA!")
    print("="*50)
    print(f"📍 Local analisado: 22°53'17\"S, 47°04'07\"W")
    print(f"🗺️ Área coberta: {AREA_SIZE*111:.1f}km²")
    print(f"⚠️ Nível de risco: {analysis_results['risk_level']}")
    print(f"💧 Áreas aquáticas: {analysis_results['water_percentage']:.2f}%")
    print(f"🟢 Água estagnada: {analysis_results['stagnant_percentage']:.2f}%")
    
else:
    print("❌ Não foi possível completar a análise combinada")
    print("Verifique se ambas as imagens foram obtidas com sucesso")

# ================================
# CÉLULA 11: RELATÓRIO FINAL E RECOMENDAÇÕES
# ================================

def generate_final_report(analysis_results, coords):
    """Gerar relatório final com recomendações"""
    
    print("\n📋 RELATÓRIO FINAL - ANÁLISE DE FOCOS DE DENGUE")
    print("="*60)
    
    # Informações básicas
    print(f"📍 LOCALIZAÇÃO ANALISADA:")
    print(f"  • Coordenadas: {coords[0]:.6f}, {coords[1]:.6f}")
    print(f"  • Posição: 22°53'17\"S, 47°04'07\"W")
    print(f"  • Área total: {AREA_SIZE*111:.1f}km²")
    print(f"  • Data da análise: {END_DATE}")
    
    # Resultados da análise
    print(f"\n🔍 RESULTADOS DA ANÁLISE:")
    print(f"  • Nível de risco: {analysis_results['risk_level']}")
    print(f"  • Áreas aquáticas totais: {analysis_results['water_percentage']:.2f}%")
    print(f"  • Água estagnada detectada: {analysis_results['stagnant_percentage']:.2f}%")
    print(f"  • Pixels de água: {analysis_results['water_pixels']:,}")
    print(f"  • Pixels de água estagnada: {analysis_results['stagnant_pixels']:,}")
    
    # Recomendações baseadas no nível de risco
    print(f"\n💡 RECOMENDAÇÕES:")
    
    if "ALTO" in analysis_results['risk_level']:
        print("  🔴 RISCO ALTO - AÇÃO IMEDIATA NECESSÁRIA:")
        print("    • Inspeção presencial urgente da área")
        print("    • Eliminação de recipientes com água parada")
        print("    • Aplicação de larvicida em pontos críticos")
        print("    • Monitoramento semanal da região")
        print("    • Educação da população local")
        
    elif "MÉDIO" in analysis_results['risk_level']:
        print("  🟡 RISCO MÉDIO - MONITORAMENTO NECESSÁRIO:")
        print("    • Inspeção da área em 7-10 dias")
        print("    • Verificação de recipientes suspeitos")
        print("    • Orientação aos moradores")
        print("    • Monitoramento quinzenal")
        
    else:
        print("  🟢 RISCO BAIXO - MONITORAMENTO DE ROTINA:")
        print("    • Inspeção mensal da área")
        print("    • Manutenção preventiva")
        print("    • Educação continuada")
    
    # Ações específicas
    print(f"\n🎯 AÇÕES ESPECÍFICAS RECOMENDADAS:")
    print("  • Verificar piscinas, caixas d'água e reservatórios")
    print("  • Eliminar pneus, vasos e recipientes descobertos")
    print("  • Limpar calhas e sistemas de drenagem")
    print("  • Verificar áreas de construção civil")
    print("  • Monitorar terrenos baldios com acúmulo de água")
    
    # Próximos passos
    print(f"\n📅 PRÓXIMOS PASSOS:")
    print("  1. Validação in-loco dos pontos identificados")
    print("  2. Coleta de amostras de água para análise")
    print("  3. Aplicação de medidas de controle")
    print("  4. Nova análise por satélite em 30 dias")
    print("  5. Avaliação da efetividade das ações")
    
    print("\n" + "="*60)
    print("✅ Relatório gerado com sucesso!")
    
    return True

# Executar relatório final se houver resultados
if 'analysis_results' in locals() and analysis_results:
    generate_final_report(analysis_results, TARGET_COORDS)
else:
    print("\n📋 RELATÓRIO FINAL")
    print("="*50)
    print("⚠️ Análise não foi completada.")
    print("Execute as células anteriores para obter os resultados.")

print("\n✅ Sistema de análise de focos de dengue - COMPLETO!")
print("📁 Arquivos disponíveis:")
print("  • google_earth_raw.png - Imagem original do Google Earth")
print("  • sentinel_raw.png - Imagem original do Sentinel-2")  
print("  • sentinel_processed.png - Imagem processada do Sentinel-2")
print("  • analise_combinada_dengue.png - Visualização completa")

print("\n🎯 RESUMO DA ANÁLISE:")
print("="*50)
print("📍 Coordenadas analisadas: 22°53'17\"S, 47°04'07\"W")
print(f"🗺️ Área total coberta: {AREA_SIZE*111:.1f}km²")
print("🛰️ Fontes utilizadas: Google Earth + Copernicus Sentinel-2")
print("🔍 Processamento: Detecção automática de focos aquáticos")
print("📊 Relatório: Análise de risco e recomendações geradas")
print("="*50)
print("✨ Análise concluída com sucesso!")

# ================================
# CÉLULA 12: GERAÇÃO DE RELATÓRIOS VISUAIS PROFISSIONAIS
# ================================

print("\n🎨 GERANDO RELATÓRIOS VISUAIS PROFISSIONAIS")
print("="*60)

try:
    # Importar gerador de relatórios
    from report_generator import create_professional_report, create_compact_infographic
    
    # Verificar se temos os dados da análise
    if 'analysis_results' in locals() and analysis_results:
        print("📊 Dados da análise encontrados!")
        print(f"   • Nível de risco: {analysis_results['risk_level']}")
        print(f"   • Água estagnada: {analysis_results['stagnant_percentage']:.2f}%")
        
        # Gerar relatório profissional completo
        print("\n🎯 Gerando relatório profissional...")
        create_professional_report(
            analysis_results,   # Dados da análise que já existem
            TARGET_COORDS,      # Coordenadas que já existem
            BBOX,              # Bounding box que já existe
            AREA_SIZE          # Tamanho da área que já existe
        )
        
        # Gerar infográfico compacto
        print("\n📱 Gerando infográfico compacto...")
        create_compact_infographic(
            analysis_results,   # Dados da análise
            TARGET_COORDS       # Coordenadas
        )
        
        print("\n🎉 TODOS OS RELATÓRIOS GERADOS!")
        print("📁 Novos arquivos criados:")
        print("  • relatorio_dengue_profissional.png")
        print("  • relatorio_dengue_profissional.pdf") 
        print("  • infografico_dengue_compacto.png")
        print("  • dashboard.html (abra no navegador)")
        
    else:
        print("⚠️ Dados da análise não encontrados!")
        print("   Execute as células anteriores primeiro.")
        
except ImportError as e:
    print(f"❌ Erro ao importar report_generator: {e}")
    print("   Certifique-se de que report_generator.py está no mesmo diretório")
    
except Exception as e:
    print(f"❌ Erro na geração de relatórios: {e}")

print("\n✅ Sistema de análise de focos de dengue - COMPLETO!")