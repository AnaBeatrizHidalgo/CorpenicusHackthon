import os
from dotenv import load_dotenv
from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, BBox, CRS, MimeType
import matplotlib.pyplot as plt
import numpy as np

# Configuração
load_dotenv()
config = SHConfig()
config.sh_client_id = os.getenv("CLIENT_ID").strip()
config.sh_client_secret = os.getenv("CLIENT_SECRET_ID").strip()
config.sh_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
config.sh_base_url = "https://sh.dataspace.copernicus.eu"

# Área da Unicamp
bbox = BBox(bbox=[-47.085, -22.835, -47.045, -22.795], crs=CRS.WGS84)

# Evalscript mais simples focado em VV apenas
evalscript_simple = """
//VERSION=3
function setup() {
    return {
        input: ["VV"],
        output: { 
            bands: 1,
            sampleType: "FLOAT32"
        }
    };
}

function evaluatePixel(sample) {
    return [sample.VV];
}
"""

print("🛰️ Baixando imagem Sentinel-1 simples (apenas VV)...")

request = SentinelHubRequest(
    evalscript=evalscript_simple,
    input_data=[
        SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL1_IW.define_from(
                name="s1iw", 
                service_url="https://sh.dataspace.copernicus.eu"
            ),
            time_interval=("2024-07-01", "2024-07-31")
        )
    ],
    responses=[
        SentinelHubRequest.output_response("default", MimeType.TIFF)
    ],
    bbox=bbox,
    size=(512, 512),
    config=config
)

try:
    response = request.get_data()
    
    if response and len(response) > 0:
        # Dados em formato TIFF/array numpy
        img_data = response[0]
        
        print(f"Shape: {img_data.shape}")
        print(f"Tipo: {img_data.dtype}")
        print(f"Min/Max: {img_data.min():.2f}/{img_data.max():.2f}")
        print(f"Valores únicos: {len(np.unique(img_data))}")
        
        # Se for 3D, pegar apenas a primeira banda
        if len(img_data.shape) == 3:
            img_data = img_data[:,:,0]
        
        # Criar visualizações diferentes
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. Dados brutos
        im1 = axes[0,0].imshow(img_data, cmap='gray')
        axes[0,0].set_title('Dados Brutos (dB)')
        axes[0,0].axis('off')
        plt.colorbar(im1, ax=axes[0,0])
        
        # 2. Stretch linear
        vmin, vmax = np.percentile(img_data[img_data != 0], [1, 99])
        im2 = axes[0,1].imshow(img_data, cmap='gray', vmin=vmin, vmax=vmax)
        axes[0,1].set_title(f'Stretch Linear (1%-99%: {vmin:.1f} a {vmax:.1f} dB)')
        axes[0,1].axis('off')
        plt.colorbar(im2, ax=axes[0,1])
        
        # 3. Conversão para linear e log
        img_linear = np.power(10, img_data / 10)
        img_linear[img_linear <= 0] = np.nan
        im3 = axes[1,0].imshow(img_linear, cmap='viridis')
        axes[1,0].set_title('Valores Lineares')
        axes[1,0].axis('off')
        plt.colorbar(im3, ax=axes[1,0])
        
        # 4. Melhor visualização com contrast stretching
        img_display = img_data.copy()
        img_display = np.clip(img_display, -25, -5)  # Clip para range típico
        img_display = (img_display + 25) / 20 * 255  # Normalizar para 0-255
        im4 = axes[1,1].imshow(img_display, cmap='plasma')
        axes[1,1].set_title('Otimizado para Visualização')
        axes[1,1].axis('off')
        plt.colorbar(im4, ax=axes[1,1])
        
        plt.tight_layout()
        plt.suptitle('Sentinel-1 VV - Unicamp - Julho 2024\nDiferentes Visualizações', fontsize=16, y=0.98)
        
        # Salvar
        plt.savefig('s1_unicamp_multiplas_visualizacoes.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print("✅ Imagens geradas com sucesso!")
        print("📁 Arquivo salvo: s1_unicamp_multiplas_visualizacoes.png")
        
    else:
        print("❌ Nenhum dado retornado")
        
except Exception as e:
    print(f"❌ Erro: {e}")

# Script adicional para salvar dados brutos
print("\n💾 Salvando dados brutos para análise...")
try:
    if 'img_data' in locals():
        np.save('sentinel1_unicamp_raw.npy', img_data)
        print("✅ Dados salvos em: sentinel1_unicamp_raw.npy")
        print("   Use: np.load('sentinel1_unicamp_raw.npy') para carregá-los")
except:
    print("❌ Erro ao salvar dados brutos")