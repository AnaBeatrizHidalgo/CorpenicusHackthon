#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Downloader de dados Sentinel-1/2 para monitoramento de focos de dengue
Versão ajustada para uso com configurações centralizadas
"""

import os
import glob
import requests
import rasterio
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from sentinelhub import (
    SHConfig,
    BBox,
    CRS,
    MimeType,
    DataCollection,
    SentinelHubRequest
)

# Configurações do projeto
from src.config.settings import (
    DATA_DIR,
    RAW_DIR,
    PROCESSED_DIR,
    STUDY_AREA,
    AUTH,
    FILE_NAMES,
    DATA_RANGES,
    DATA_SOURCES
)

# Debug: Mostra configurações carregadas
print("\n🔧 [DEBUG] Configurações carregadas:")
print(f" - DATA_DIR: {DATA_DIR}")
print(f" - RAW_DIR: {RAW_DIR}")
print(f" - PROCESSED_DIR: {PROCESSED_DIR}")
print(f" - Período padrão: {DATA_RANGES['default']['start']} a {DATA_RANGES['default']['end']}")
print(f" - Bands S1: {DATA_SOURCES['sentinel1']['bands']}")
print(f" - Bands S2: {DATA_SOURCES['sentinel2']['bands']}\n")

# Setup de diretórios
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Autenticação
load_dotenv()
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET_ID')

if not all([client_id, client_secret]):
    raise ValueError("❌ Credenciais não encontradas no .env")

def setup_sentinelhub_config():
    """Configura autenticação no Copernicus CDSE com debug"""
    print("🔑 [DEBUG] Configurando autenticação...")
    config = SHConfig()
    config.sh_client_id = client_id.strip()
    config.sh_client_secret = client_secret.strip()
    config.sh_token_url = AUTH['copernicus']['token_url']
    config.sh_base_url = AUTH['copernicus']['base_url']
    
    # Debug: Mostra configuração resumida
    print(f"  - Client ID: {config.sh_client_id[:8]}...")
    print(f"  - Base URL: {config.sh_base_url}")
    
    return config

config = setup_sentinelhub_config()

def test_authentication(config):
    """Testa conexão com API com verificação detalhada"""
    print("\n🔐 [DEBUG] Testando autenticação...")
    try:
        response = requests.post(
            config.sh_token_url,
            data={
                'grant_type': 'client_credentials',
                'client_id': config.sh_client_id,
                'client_secret': config.sh_client_secret
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        # Debug detalhado
        print(f"  - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("  - Token obtido com sucesso!")
            return True
        else:
            print(f"  - Erro na resposta: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ [DEBUG] Falha na autenticação: {type(e).__name__}: {str(e)}")
        return False

auth_success = test_authentication(config)

def _generate_evalscript(bands: list):
    """Gera evalscript dinamicamente com debug"""
    print(f"\n📜 [DEBUG] Gerando evalscript para bands: {bands}")
    bands_str = ", ".join([f"'{band}'" for band in bands])
    evalscript = f"""
    //VERSION=3
    function setup() {{
        return {{ input: [{bands_str}], output: {{ bands: {len(bands)} }} }};
    }}
    function evaluatePixel(sample) {{
        return [{', '.join([f'sample.{band}' for band in bands])}];
    }}
    """
    print(f"  - Evalscript gerado ({len(evalscript.splitlines())} linhas)")
    return evalscript

def download_sentinel_data(sensor_type: str):
    """Download unificado para Sentinel-1/2 com logging detalhado"""
    if not auth_success:
        print(f"❌ Pulando download {sensor_type} (falha na autenticação)")
        return None

    sensor_config = DATA_SOURCES.get(sensor_type)
    if not sensor_config:
        print(f"❌ Configuração não encontrada para {sensor_type}")
        return None

    date_range = DATA_RANGES["default"]
    print(f"\n📡 [DEBUG] Iniciando download {sensor_type.upper()}")
    print(f"  - Período: {date_range['start']} a {date_range['end']}")
    print(f"  - Bands: {sensor_config['bands']}")

    try:
        request = SentinelHubRequest(
            data_folder=str(RAW_DIR),
            evalscript=_generate_evalscript(sensor_config["bands"]),
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection[sensor_config["collection"]].define_from(
                        name=f'CUSTOM_{sensor_type.upper()}',
                        service_url=AUTH['copernicus']['base_url']
                    ),
                    time_interval=(date_range["start"], date_range["end"]),
                    mosaicking_order='leastCC' if sensor_type == "sentinel2" else None,
                    maxcc=sensor_config.get("max_cloud_cover", None)
                )
            ],
            responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
            bbox=BBox(bbox=STUDY_AREA['bbox'], crs=CRS.WGS84),
            size=(STUDY_AREA['tile_size'], STUDY_AREA['tile_size']),
            config=config
        )

        print("  - Request configurado, iniciando download...")
        request.save_data()

        # Pós-download
        tiff_files = sorted(
            glob.glob(f'{RAW_DIR}/**/response.tiff', recursive=True),
            key=os.path.getmtime, 
            reverse=True
        )

        if not tiff_files:
            print("❌ Download completo mas nenhum arquivo encontrado")
            return None

        output_filename = FILE_NAMES[sensor_type].format(
            date=datetime.now().strftime("%Y%m%d")
        )
        output_path = str(PROCESSED_DIR / output_filename)
        
        print(f"  - Movendo para: {output_path}")
        os.rename(tiff_files[0], output_path)
        
        # Verificação pós-move
        if not os.path.exists(output_path):
            print(f"❌ Arquivo não movido para {output_path}")
            return None
            
        print(f"✓ Download {sensor_type.upper()} concluído")
        return output_path

    except Exception as e:
        print(f"❌ Erro no download {sensor_type}: {type(e).__name__}: {str(e)}")
        return None

def visualize_sentinel_image(data_path, title, output_file):
    """Visualização com debug de metadados"""
    print(f"\n🎨 [DEBUG] Gerando visualização para {data_path}")
    
    if not data_path or not Path(data_path).exists():
        print(f"❌ Arquivo não encontrado: {data_path}")
        return

    try:
        with rasterio.open(data_path) as src:
            print(f"  - Metadados: {src.meta}")
            image = src.read()
            
            print(f"  - Shape: {image.shape}")
            print(f"  - Valores: min={image.min():.2f}, max={image.max():.2f}")
            
            fig, axes = plt.subplots(1, len(image), figsize=(10 * len(image), 8))
            if len(image) == 1:
                axes = [axes]

            for i, band in enumerate(image):
                axes[i].imshow(band, cmap='gray')
                axes[i].set_title(f'{title} - Band {i+1}', fontsize=12)
                plt.colorbar(axes[i].imshow(band, cmap='gray'), ax=axes[i])

            plt.tight_layout()
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"✓ Visualização salva em {output_file}")

    except Exception as e:
        print(f"❌ Erro na visualização: {type(e).__name__}: {str(e)}")

# Execução principal
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🛰️  INICIANDO DOWNLOAD DE DADOS SENTINEL")
    print("="*60)

    # Download dos dados
    s1_path = download_sentinel_data("sentinel1")
    s2_path = download_sentinel_data("sentinel2")

    # Geração de visualizações
    if s1_path:
        visualize_sentinel_image(
            s1_path,
            "Sentinel-1",
            str(PROCESSED_DIR / FILE_NAMES["s1_preview"])
        )

    if s2_path:
        visualize_sentinel_image(
            s2_path,
            "Sentinel-2",
            str(PROCESSED_DIR / FILE_NAMES["s2_preview"])
        )

    # Resumo final
    print("\n" + "="*60)
    print("📋 RESUMO FINAL")
    print("="*60)
    print(f"✅ Autenticação: {'Sucesso' if auth_success else 'Falha'}")
    print(f"📁 Dados salvos em: {PROCESSED_DIR}")
    print(f"🖼️ Visualizações geradas:")
    print(f"  - Sentinel-1: {'Sim' if s1_path else 'Não'}")
    print(f"  - Sentinel-2: {'Sim' if s2_path else 'Não'}")