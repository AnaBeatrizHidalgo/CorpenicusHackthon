import os
from dotenv import load_dotenv
from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, BBox, CRS, MimeType
import matplotlib.pyplot as plt
import numpy as np

# Carregar variáveis do .env
load_dotenv()
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET_ID")

if not client_id or not client_secret:
    raise ValueError("Credenciais CLIENT_ID ou CLIENT_SECRET_ID não encontradas no .env")

# Configurar Sentinel Hub CORRETAMENTE para Copernicus Data Space Ecosystem
config = SHConfig()
config.sh_client_id = client_id.strip()
config.sh_client_secret = client_secret.strip()
config.sh_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
config.sh_base_url = "https://sh.dataspace.copernicus.eu"

print("Configuração do Sentinel Hub:")
print(f"Client ID: {config.sh_client_id[:8]}...")
print(f"Base URL: {config.sh_base_url}")
print(f"Token URL: {config.sh_token_url}")

# Coordenadas da Unicamp (Campinas/SP) - área mais ampla para garantir dados
bbox = BBox(bbox=[-47.085, -22.835, -47.045, -22.795], crs=CRS.WGS84)

# Evalscript CORRETO para Sentinel-1 com melhor normalização
evalscript_s1 = """
//VERSION=3
function setup() {
    return {
        input: ["VV", "VH"],
        output: { 
            bands: 3,
            sampleType: "UINT8"
        }
    };
}

function evaluatePixel(sample) {
    // Valores típicos do Sentinel-1 estão em dB (geralmente entre -25 e 0)
    // Normalização melhorada para visualização
    let vv = sample.VV;
    let vh = sample.VH;
    
    // Clampear valores para range típico do Sentinel-1
    vv = Math.max(-25, Math.min(0, vv));
    vh = Math.max(-30, Math.min(-5, vh));
    
    // Normalizar para 0-255
    let vv_norm = ((vv + 25) / 25) * 255;
    let vh_norm = ((vh + 30) / 25) * 255;
    
    // Composição RGB para melhor contraste
    return [
        vv_norm,                    // Red: VV
        vh_norm,                    // Green: VH  
        Math.min(255, (vv_norm + vh_norm) / 2)  // Blue: combinação
    ];
}
"""

# Criar requisição SentinelHubRequest CORRETA
request = SentinelHubRequest(
    evalscript=evalscript_s1,
    input_data=[
        SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL1_IW.define_from(
                name="s1iw", 
                service_url="https://sh.dataspace.copernicus.eu"
            ),
            time_interval=("2024-07-01", "2024-07-31"),
            other_args={
                "dataFilter": {
                    "resolution": "HIGH"
                }
            }
        )
    ],
    responses=[
        SentinelHubRequest.output_response("default", MimeType.PNG)
    ],
    bbox=bbox,
    size=(1024, 1024),
    config=config
)

# Função para tentar diferentes períodos
def try_periods():
    periods = [
        ("2024-07-01", "2024-07-31", "Julho 2024"),
        ("2024-06-01", "2024-06-30", "Junho 2024"), 
        ("2024-08-01", "2024-08-31", "Agosto 2024"),
        ("2024-05-01", "2024-05-31", "Maio 2024"),
        ("2024-04-01", "2024-04-30", "Abril 2024")
    ]
    
    for start_date, end_date, period_name in periods:
        print(f"\nTentando período: {period_name}")
        
        # Criar nova requisição para cada período
        new_request = SentinelHubRequest(
            evalscript=evalscript_s1,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL1_IW.define_from(
                        name="s1iw", 
                        service_url="https://sh.dataspace.copernicus.eu"
                    ),
                    time_interval=(start_date, end_date),
                    other_args={
                        "dataFilter": {
                            "resolution": "HIGH"
                        }
                    }
                )
            ],
            responses=[
                SentinelHubRequest.output_response("default", MimeType.PNG)
            ],
            bbox=bbox,
            size=(1024, 1024),
            config=config
        )
        
        try:
            # Usar get_data() conforme documentação oficial
            response = new_request.get_data()
            
            if response and len(response) > 0:
                print(f"✓ Dados encontrados para {period_name}!")
                
                # Converter resposta para array numpy
                img_array = np.array(response[0])
                
                # Debug: verificar valores da imagem
                print(f"   Shape da imagem: {img_array.shape}")
                print(f"   Tipo de dados: {img_array.dtype}")
                print(f"   Valores min/max: {img_array.min()}/{img_array.max()}")
                print(f"   Valores únicos: {len(np.unique(img_array))}")
                
                # Verificar se a imagem tem dados válidos
                if img_array.size > 0:
                    # Aplicar stretching de contraste se necessário
                    if img_array.max() > 0:
                        # Normalizar para melhor visualização
                        img_display = img_array.astype(np.float32)
                        
                        # Aplicar stretch de contraste por canal
                        for i in range(img_display.shape[2]):
                            channel = img_display[:,:,i]
                            if channel.max() > channel.min():
                                # Percentil stretch para melhor contraste
                                p2, p98 = np.percentile(channel[channel > 0], [2, 98])
                                channel = np.clip((channel - p2) / (p98 - p2) * 255, 0, 255)
                                img_display[:,:,i] = channel
                        
                        img_display = img_display.astype(np.uint8)
                    else:
                        img_display = img_array
                    
                    # Plotar imagem
                    plt.figure(figsize=(15, 12))
                    plt.imshow(img_display)
                    plt.title(f"Imagem Sentinel-1 - Unicamp (Campinas/SP)\n{period_name} - Composição: VV (Vermelho), VH (Verde)", 
                             fontsize=14, pad=20)
                    plt.axis('off')
                    
                    # Adicionar informações
                    plt.figtext(0.5, 0.02, 
                               f"Coordenadas: {bbox.lower_left[1]:.3f}°S, {bbox.lower_left[0]:.3f}°W - "
                               f"{bbox.upper_right[1]:.3f}°S, {bbox.upper_right[0]:.3f}°W\n"
                               f"Resolução: {img_array.shape[0]}x{img_array.shape[1]} pixels | "
                               f"Range de valores: {img_array.min()}-{img_array.max()}", 
                               ha='center', fontsize=10)
                    
                    # Salvar imagem
                    filename = f"s1_unicamp_{start_date.replace('-', '')}.png"
                    plt.savefig(filename, dpi=300, bbox_inches='tight', 
                               facecolor='white', edgecolor='none')
                    print(f"✓ Imagem salva como '{filename}'")
                    
                    plt.show()
                    return True
                else:
                    print(f"⚠ Dados encontrados mas imagem vazia para {period_name}")
            else:
                print(f"✗ Nenhum dado disponível para {period_name}")
                
        except Exception as e:
            print(f"✗ Erro para {period_name}: {str(e)}")
            if "401" in str(e):
                print("   → Problema de autenticação!")
                return False
            elif "404" in str(e):
                print("   → Dados não encontrados para este período")
            continue
    
    print("\n❌ Não foi possível encontrar dados para nenhum período testado")
    return False

try:
    print("🛰️ Iniciando download de imagem Sentinel-1 da Unicamp...")
    print("📍 Região: Campinas/SP (Universidade Estadual de Campinas)")
    
    success = try_periods()
    
    if not success:
        print("\n🔧 DIAGNÓSTICO DE PROBLEMAS:")
        print("1. ❌ Verifique suas credenciais no arquivo .env:")
        print("   - CLIENT_ID=seu_client_id_aqui")
        print("   - CLIENT_SECRET_ID=seu_client_secret_aqui")
        print("2. ❌ Confirme que você tem uma conta ativa no Copernicus Data Space Ecosystem")
        print("3. ❌ Verifique se você criou um OAuth Client no Dashboard:")
        print("   https://shapps.dataspace.copernicus.eu/dashboard/#/")
        print("4. ❌ Teste sua conexão e tente novamente")

except Exception as e:
    print(f"\n❌ Erro crítico: {e}")
    if "401" in str(e) or "Unauthorized" in str(e):
        print("\n🔑 PROBLEMA DE AUTENTICAÇÃO DETECTADO:")
        print("1. Verifique se suas credenciais CLIENT_ID e CLIENT_SECRET_ID estão corretas")
        print("2. Confirme que você tem acesso ao Copernicus Data Space Ecosystem")
        print("3. Verifique se o OAuth Client está ativo no seu dashboard")
        print("4. Link do dashboard: https://shapps.dataspace.copernicus.eu/dashboard/#/")
    else:
        print(f"Erro técnico: {e}")

print("\n📋 INFORMAÇÕES IMPORTANTES:")
print("• Sentinel-1 é um radar SAR que funciona independente de nuvens")
print("• VV: polarização vertical-vertical (melhor para áreas urbanas)")
print("• VH: polarização vertical-horizontal (melhor para vegetação)")
print("• A composição de cores facilita a interpretação dos dados")