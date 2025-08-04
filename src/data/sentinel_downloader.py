# src/data/sentinel_downloader.py
import logging
import os
from pathlib import Path
import glob
import shutil
import rasterio
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
    image_size: tuple = (512, 512),
    job_id: str = None
):
    """
    Baixa dados de um sensor Sentinel, valida o formato TIFF e salva.
    """
    logging.info(f"--- Iniciando download para sensor: {sensor}, job_id: {job_id} ---")
    logging.info(f"Parâmetros: bbox={bbox}, time_interval={time_interval}, output_path={output_path}")

    try:
        config = _setup_config(auth_config['client_id'], auth_config['client_secret'])
    except ValueError as e:
        logging.error(f"Não foi possível configurar a autenticação: {e}")
        return None

    # Validar bbox
    if not (isinstance(bbox, list) and len(bbox) == 4):
        logging.error(f"BBox inválido: {bbox}")
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = map(float, bbox)
        if min_lon >= max_lon or min_lat >= max_lat:
            logging.error(f"BBox com coordenadas inválidas: min_lon={min_lon}, max_lon={max_lon}, min_lat={min_lat}, max_lat={max_lat}")
            return None
    except ValueError:
        logging.error(f"BBox contém valores não numéricos: {bbox}")
        return None

    study_area_bbox = BBox(bbox, crs=CRS.WGS84)
    cache_folder = output_path.parent / f".sh_cache_{job_id}" if job_id else output_path.parent / ".sh_cache"
    cache_folder.mkdir(parents=True, exist_ok=True)
    logging.info(f"Diretório de cache: {cache_folder}")

    # Configurações específicas por sensor
    expected_bands = {'S1': 2, 'S2': 4}  # Número esperado de bandas
    if sensor.upper() == 'S1':
        evalscript = """
            //VERSION=3
            function setup() { return { input: ['VV', 'VH'], output: { bands: 2, sampleType: 'FLOAT32' } }; }
            function evaluatePixel(sample) { return [sample.VV, sample.VH]; }
        """
        data_collection = DataCollection.SENTINEL1_IW
    elif sensor.upper() == 'S2':
        evalscript = """
            //VERSION=3
            function setup() { return { input: ['B04', 'B03', 'B02', 'B08'], output: { bands: 4, sampleType: 'FLOAT32' } }; }
            function evaluatePixel(sample) { return [sample.B04, sample.B03, sample.B02, sample.B08]; }
        """
        data_collection = DataCollection.SENTINEL2_L2A
    else:
        logging.error(f"Sensor '{sensor}' não suportado. Use 'S1' ou 'S2'.")
        return None

    # Criação e execução da requisição
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
        logging.info(f"Arquivos TIFF encontrados no cache: {tiff_files}")
        
        if not tiff_files:
            logging.error(f"Download para {sensor} não encontrou response.tiff no cache: {cache_folder}")
            return None

        latest_tiff = tiff_files[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Validar e corrigir o arquivo TIFF
        try:
            with rasterio.open(latest_tiff) as src:
                band_count = src.count
                logging.info(f"Arquivo TIFF temporário {latest_tiff} tem {band_count} bandas.")
                if band_count != expected_bands[sensor.upper()]:
                    logging.warning(f"Número de bandas inesperado: {band_count} (esperado: {expected_bands[sensor.upper()]}). Tentando corrigir.")
                    # Reabrir e salvar apenas as bandas esperadas
                    data = src.read()[:expected_bands[sensor.upper()]]  # Lê apenas as bandas esperadas
                    profile = src.profile
                    profile.update(count=expected_bands[sensor.upper()])  # Atualiza o número de bandas
                    with rasterio.open(output_path, 'w', **profile) as dst:
                        dst.write(data)
                else:
                    # Copiar o arquivo diretamente se o número de bandas estiver correto
                    shutil.copy(latest_tiff, output_path)
        except Exception as e:
            logging.error(f"Erro ao validar ou corrigir arquivo TIFF {latest_tiff}: {e}")
            return None

        logging.info(f"Download concluído com sucesso. Arquivo salvo em: {output_path}")
        # Limpar diretório de cache
        shutil.rmtree(cache_folder, ignore_errors=True)
        return output_path

    except Exception as e:
        logging.error(f"Falha durante o download para {sensor}: {str(e)}", exc_info=True)
        return None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    try:
        from dotenv import load_dotenv
    except ImportError:
        logging.error("Para testar, instale 'python-dotenv': pip install python-dotenv")
        exit()

    dotenv_path = Path(__file__).resolve().parent.parent.parent / '.env'
    load_dotenv(dotenv_path=dotenv_path)
    
    TEST_AUTH_CONFIG = {
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET_ID"),
    }
    TEST_BBOX = [-47.10, -22.85, -47.03, -22.78]
    TEST_TIME_INTERVAL = ("2024-07-01", "2024-07-30")
    
    output_dir = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "sentinel"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    s1_output_file = output_dir / f"s1_test_{TEST_TIME_INTERVAL[0]}_{TEST_TIME_INTERVAL[1]}.tiff"
    s2_output_file = output_dir / f"s2_test_{TEST_TIME_INTERVAL[0]}_{TEST_TIME_INTERVAL[1]}.tiff"
    
    logging.info("--- INICIANDO TESTE DO MÓDULO DE DOWNLOAD ---")
    try:
        download_and_save_sentinel_data(
            sensor='S1',
            auth_config=TEST_AUTH_CONFIG,
            bbox=TEST_BBOX,
            time_interval=TEST_TIME_INTERVAL,
            output_path=s1_output_file,
            job_id="test_s1"
        )
        download_and_save_sentinel_data(
            sensor='S2',
            auth_config=TEST_AUTH_CONFIG,
            bbox=TEST_BBOX,
            time_interval=TEST_TIME_INTERVAL,
            output_path=s2_output_file,
            job_id="test_s2"
        )
        logging.info("--- TESTE DO MÓDULO CONCLUÍDO COM SUCESSO ---")
    except Exception as e:
        logging.error(f"--- TESTE DO MÓDULO FALHOU: {e} ---")