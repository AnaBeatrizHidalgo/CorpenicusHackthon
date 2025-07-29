# main.py - Código para Copernicus Data Space Ecosystem (CDSE)
import matplotlib.pyplot as plt
import numpy as np
import requests
from datetime import datetime, timedelta
from auth import get_copernicus_config

def get_access_token():
    """Obtém token de acesso para o CDSE"""
    config = get_copernicus_config()
    
    response = requests.post(
        config.sh_token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': config.sh_client_id,
            'client_secret': config.sh_client_secret
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception(f"Erro ao obter token: {response.text}")

def search_sentinel2_products():
    """
    Busca produtos Sentinel-2 usando OData API do CDSE
    """
    # Obtém token de acesso
    token = get_access_token()
    
    # URL base da OData API do CDSE
    odata_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    
    # Parâmetros de busca
    # Área de São Paulo (aproximada)
    aoi = "POLYGON((-46.8 -23.8, -46.4 -23.8, -46.4 -23.4, -46.8 -23.4, -46.8 -23.8))"
    
    # Filtros OData
    filter_params = (
        "Collection/Name eq 'SENTINEL-2' and "
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'S2MSI1C') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{aoi}') and "
        "ContentDate/Start gt 2024-01-01T00:00:00.000Z and "
        "ContentDate/Start lt 2024-01-31T23:59:59.999Z"
    )
    
    params = {
        '$filter': filter_params,
        '$orderby': 'ContentDate/Start desc',
        '$top': 10,
        '$expand': 'Attributes'
    }
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    print("Buscando produtos Sentinel-2...")
    response = requests.get(odata_url, params=params, headers=headers)
    
    if response.status_code == 200:
        products = response.json()
        print(f"✓ Encontrados {len(products.get('value', []))} produtos")
        
        for product in products.get('value', [])[:5]:  # Mostra apenas os primeiros 5
            name = product.get('Name', 'N/A')
            date = product.get('ContentDate', {}).get('Start', 'N/A')
            size = product.get('ContentLength', 0) / (1024**3)  # GB
            
            # Busca cloud cover nos atributos
            cloud_cover = 'N/A'
            for attr in product.get('Attributes', []):
                if attr.get('Name') == 'cloudCover':
                    cloud_cover = f"{attr.get('Value', 'N/A')}%"
                    break
            
            print(f"📅 {date[:10]} | ☁️ {cloud_cover} | 📦 {size:.2f}GB | {name}")
        
        return products.get('value', [])
    
    else:
        print(f"❌ Erro na busca: {response.status_code}")
        print(response.text)
        return []

def download_product_quicklook(product_id):
    """
    Baixa uma imagem quicklook de um produto usando S3 API
    """
    token = get_access_token()
    
    # URL para quicklook via S3 API do CDSE
    s3_url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/Nodes({product_id}.SAFE)/Nodes(GRANULE)/Nodes"
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    print(f"Buscando quicklook do produto {product_id}...")
    
    try:
        # Primeiro, lista os nós para encontrar o quicklook
        response = requests.get(s3_url, headers=headers)
        
        if response.status_code == 200:
            nodes = response.json().get('value', [])
            
            # Procura por arquivos de quicklook
            for node in nodes:
                node_name = node.get('Name', '')
                if 'TCI' in node_name or 'quicklook' in node_name.lower():
                    print(f"Encontrado arquivo de visualização: {node_name}")
                    break
            
            print("ℹ️  Para baixar imagens completas, use a S3 API ou Sentinel Hub Processing API")
            return True
        else:
            print(f"❌ Erro ao acessar produto: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def get_sentinel_hub_image():
    """
    Exemplo usando Sentinel Hub Processing API do CDSE
    """
    token = get_access_token()
    
    # URL do Sentinel Hub no CDSE
    process_url = "https://sh.dataspace.copernicus.eu/api/v1/process"
    
    # Payload para requisição de imagem
    payload = {
        "input": {
            "bounds": {
                "bbox": [-46.8, -23.8, -46.4, -23.4],
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
            },
            "data": [
                {
                    "type": "sentinel-2-l1c",
                    "dataFilter": {
                        "timeRange": {
                            "from": "2024-01-01T00:00:00Z",
                            "to": "2024-01-31T23:59:59Z"
                        },
                        "mosaickingOrder": "leastCC"
                    }
                }
            ]
        },
        "output": {
            "width": 512,
            "height": 512,
            "responses": [
                {
                    "identifier": "default",
                    "format": {"type": "image/tiff"}
                }
            ]
        },
        "evalscript": """
            //VERSION=3
            function setup() {
                return {
                    input: [{
                        bands: ["B02", "B03", "B04"]
                    }],
                    output: {
                        bands: 3,
                        sampleType: "AUTO"
                    }
                };
            }
            
            function evaluatePixel(sample) {
                return [sample.B04 * 3.5, sample.B03 * 3.5, sample.B02 * 3.5];
            }
        """
    }
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("Requisitando imagem via Sentinel Hub Processing API...")
    response = requests.post(process_url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print("✓ Imagem baixada com sucesso!")
        
        # Salva a imagem
        with open('sentinel2_image.tiff', 'wb') as f:
            f.write(response.content)
        
        print("💾 Imagem salva como 'sentinel2_image.tiff'")
        return True
    else:
        print(f"❌ Erro na requisição: {response.status_code}")
        print(response.text)
        return False

def main():
    """Função principal com exemplos de uso"""
    try:
        print("=== COPERNICUS DATA SPACE ECOSYSTEM - EXEMPLOS ===\n")
        
        # Exemplo 1: Buscar produtos via OData
        print("1️⃣ BUSCANDO PRODUTOS VIA ODATA API")
        products = search_sentinel2_products()
        
        if products:
            print(f"\n2️⃣ EXPLORANDO PRODUTO: {products[0]['Name']}")
            product_id = products[0]['Id']
            download_product_quicklook(product_id)
        
        print(f"\n3️⃣ BAIXANDO IMAGEM VIA SENTINEL HUB")
        get_sentinel_hub_image()
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")

if __name__ == "__main__":
    main()