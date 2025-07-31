# src/data/sentinel_downloader.py (Refatorado a partir do seu código original)
"""
Módulo para download de dados Sentinel-1 e Sentinel-2, adaptado para
a arquitetura modular do projeto NAIÁ.
"""
import logging
import os
from pathlib import Path
import glob

from sentinelhub import (
    SHConfig,
    BBox,
    CRS,
    MimeType,
    DataCollection,
    SentinelHubRequest
)

def _setup_config(client_id: str, client_secret: str) -> SHConfig:
    """Configura e autentica no Copernicus Data Space Ecosystem."""
    config = SHConfig()
    if not all([client_id, client_secret]):
        logging.error("Credenciais do Sentinel Hub não foram fornecidas.")
        raise ValueError("SH_CLIENT_ID e SH_CLIENT_SECRET devem ser definidos.")

    config.sh_client_id = client_id
    config.sh_client_secret = client_secret
    config.sh_token_url = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
    config.sh_base_url = 'https://sh.dataspace.copernicus.eu'
    
    logging.info("Configuração do Sentinel Hub pronta.")
    return config

def download_and_save_sentinel_data(
    sensor: str,
    auth_config: dict,
    bbox: list,
    time_interval: tuple,
    output_path: Path,
    image_size: tuple = (512, 512)
):
    """
    Baixa dados de um sensor Sentinel, salva e renomeia o arquivo.

    Args:
        sensor (str): O sensor a ser usado ('S1' ou 'S2').
        auth_config (dict): Dicionário com 'client_id' e 'client_secret'.
        bbox (list): Bounding box da área de estudo.
        time_interval (tuple): Intervalo de tempo (data_inicio, data_fim).
        output_path (Path): Caminho completo (incluindo nome) para salvar o arquivo final.
        image_size (tuple): Tamanho da imagem em pixels.
    """
    logging.info(f"--- Iniciando download para o sensor: {sensor} ---")
    
    try:
        config = _setup_config(
            auth_config['client_id'], 
            auth_config['client_secret']
        )
    except ValueError as e:
        logging.error(f"Não foi possível configurar a autenticação: {e}")
        return

    study_area_bbox = BBox(bbox, crs=CRS.WGS84)
    cache_folder = output_path.parent / ".sh_cache" # Pasta para cache
    cache_folder.mkdir(exist_ok=True)

    # --- Configurações específicas por sensor ---
    if sensor.upper() == 'S1':
        evalscript = """
            //VERSION=3
            function setup() { return { input: ['VV', 'VH'], output: { bands: 2 } }; }
            function evaluatePixel(sample) { return [sample.VV, sample.VH]; }
        """
        data_collection = DataCollection.SENTINEL1_IW
    elif sensor.upper() == 'S2':
        evalscript = """
            //VERSION=3
            function setup() { return { input: ['B04', 'B03', 'B02', 'B08'], output: { bands: 4 } }; }
            function evaluatePixel(sample) { return [sample.B04, sample.B03, sample.B02, sample.B08]; }
        """
        data_collection = DataCollection.SENTINEL2_L2A
    else:
        logging.error(f"Sensor '{sensor}' não suportado. Use 'S1' ou 'S2'.")
        return

    # --- Criação e execução da requisição ---
    request = SentinelHubRequest(
        data_folder=str(cache_folder),
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=data_collection.define_from(
                    name=f'{sensor.upper()}_CUSTOM', service_url=config.sh_base_url
                ),
                time_interval=time_interval,
                mosaicking_order='leastCC' if sensor.upper() == 'S2' else None
            )
        ],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=study_area_bbox,
        size=image_size,
        config=config
    )

    try:
        logging.info(f"Enviando requisição para {sensor} no período {time_interval}.")
        request.save_data()
        
        # Encontra o arquivo 'response.tiff' mais recente na pasta de cache
        tiff_files = sorted(
            glob.glob(str(cache_folder / '**' / 'response.tiff'), recursive=True), 
            key=os.path.getmtime, 
            reverse=True
        )
        
        if tiff_files:
            latest_tiff = tiff_files[0]
            # Renomeia (move) o arquivo para o caminho de saída final
            os.rename(latest_tiff, output_path)
            logging.info(f"Download concluído com sucesso. Arquivo salvo em: {output_path}")
        else:
            logging.error("Download parece ter ocorrido, mas o arquivo response.tiff não foi encontrado.")

    except Exception as e:
        logging.error(f"Falha durante o download para {sensor}: {e}", exc_info=True)
        raise

# --- Bloco de Teste ---
if __name__ == '__main__':
    # Configuração de logging para o teste
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    try:
        from dotenv import load_dotenv
    except ImportError:
        logging.error("Para testar, instale 'python-dotenv': pip install python-dotenv")
        exit()

    # Carrega as variáveis de ambiente do arquivo .env na raiz do projeto
    dotenv_path = Path(__file__).resolve().parent.parent.parent / '.env'
    load_dotenv(dotenv_path=dotenv_path)
    
    # Configurações para o teste
    TEST_AUTH_CONFIG = {
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET_ID"),
    }
    
    TEST_BBOX = [-47.10, -22.85, -47.03, -22.78]  # Barão Geraldo
    TEST_TIME_INTERVAL = ("2024-07-01", "2024-07-30")
    
    # Define o caminho de saída para os arquivos de teste
    output_dir = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "sentinel"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    s1_output_file = output_dir / f"s1_test_{TEST_TIME_INTERVAL[0]}_{TEST_TIME_INTERVAL[1]}.tiff"
    s2_output_file = output_dir / f"s2_test_{TEST_TIME_INTERVAL[0]}_{TEST_TIME_INTERVAL[1]}.tiff"
    
    logging.info("--- INICIANDO TESTE DO MÓDULO DE DOWNLOAD ---")

    try:
        # Teste para Sentinel-1
        download_and_save_sentinel_data(
            sensor='S1',
            auth_config=TEST_AUTH_CONFIG,
            bbox=TEST_BBOX,
            time_interval=TEST_TIME_INTERVAL,
            output_path=s1_output_file
        )
        
        # Teste para Sentinel-2
        download_and_save_sentinel_data(
            sensor='S2',
            auth_config=TEST_AUTH_CONFIG,
            bbox=TEST_BBOX,
            time_interval=TEST_TIME_INTERVAL,
            output_path=s2_output_file
        )
        logging.info("--- TESTE DO MÓDULO CONCLUÍDO COM SUCESSO ---")
        
    except Exception as e:
        logging.error(f"--- TESTE DO MÓDULO FALHOU: {e} ---")