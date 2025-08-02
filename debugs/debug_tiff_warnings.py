# debug_tiff_warnings.py
import logging
from pathlib import Path
import os
import shutil
import rasterio
from rasterio.mask import mask
import geopandas as gpd
from sentinelhub import SHConfig, BBox, CRS, MimeType, DataCollection, SentinelHubRequest
import glob
import numpy as np
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('rasterio').setLevel(logging.WARNING)

def setup_config(client_id: str, client_secret: str) -> SHConfig:
    config = SHConfig()
    if not all([client_id, client_secret]):
        logging.error("[TEST] Credenciais do Sentinel Hub não foram fornecidas.")
        raise ValueError("SH_CLIENT_ID e SH_CLIENT_SECRET devem ser definidos.")
    config.sh_client_id = client_id
    config.sh_client_secret = client_secret
    config.sh_token_url = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
    config.sh_base_url = 'https://sh.dataspace.copernicus.eu'
    logging.info("[TEST] Configuração do Sentinel Hub pronta.")
    return config

def clip_raster_by_sectors(raster_path: Path, geodata_path: Path, output_dir: Path):
    logging.info(f"[TEST] Iniciando recorte do raster '{raster_path.name}' por setores.")
    try:
        sectors = gpd.read_file(geodata_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        with rasterio.open(raster_path) as src:
            sectors = sectors.to_crs(src.crs)
            logging.info(f"[TEST] Processando {len(sectors)} setores...")
            available_fields = sectors.columns.tolist()
            logging.info(f"[TEST] Campos disponíveis no GeoJSON: {available_fields}")
            sector_id_field = 'CD_SETOR' if 'CD_SETOR' in available_fields else 'id' if 'id' in available_fields else available_fields[0]
            logging.info(f"[TEST] Usando campo '{sector_id_field}' como identificador.")
            for index, sector in sectors.iterrows():
                sector_id = sector[sector_id_field]
                geom = [sector.geometry]
                try:
                    out_image, out_transform = mask(src, geom, crop=True)
                    out_meta = src.meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_image.shape[1],
                        "width": out_image.shape[2],
                        "transform": out_transform,
                        "photometric": "MINISBLACK",
                        "compress": "deflate",
                        "interleave": "pixel"
                    })
                    output_path = output_dir / f"debug_{raster_path.stem}_sector_{sector_id}.tiff"
                    with rasterio.open(output_path, "w", **out_meta) as dest:
                        dest.write(out_image)
                    logging.info(f"[TEST] Arquivo recortado salvo: {output_path}")
                    with rasterio.open(output_path) as cropped:
                        logging.info(f"[TEST] Arquivo recortado {output_path}:")
                        logging.info(f"  Band count: {cropped.count}")
                        logging.info(f"  Profile: {cropped.profile}")
                        data = cropped.read()
                        logging.info(f"  Data shape: {data.shape}")
                        min_max_per_band = [(np.min(band), np.max(band)) for band in data]
                        logging.info(f"  Data min/max (per band): {min_max_per_band}")
                except ValueError as e:
                    logging.warning(f"[TEST] Setor {sector_id} fora dos limites do raster. Erro: {e}")
                    continue
    except Exception as e:
        logging.error(f"[TEST] Falha ao recortar o raster '{raster_path.name}': {e}")
        raise

def download_and_save_sentinel_data(sensor: str, auth_config: dict, bbox: list, time_interval: tuple, output_path: Path, job_id: str = "debug"):
    logging.info(f"--- [TEST] Iniciando download para {sensor}, job_id: {job_id} ---")
    logging.info(f"Parâmetros: bbox={bbox}, time_interval={time_interval}, output_path={output_path}")
    try:
        config = setup_config(auth_config['client_id'], auth_config['client_secret'])
    except ValueError as e:
        logging.error(f"[TEST] Não foi possível configurar a autenticação: {e}")
        return None
    min_lon, min_lat, max_lon, max_lat = map(float, bbox)
    if min_lon >= max_lon or min_lat >= max_lat:
        logging.error(f"[TEST] BBox inválido: {bbox}")
        return None
    study_area_bbox = BBox(bbox, crs=CRS.WGS84)
    cache_folder = output_path.parent / f".sh_cache_{job_id}"
    cache_folder.mkdir(parents=True, exist_ok=True)
    logging.info(f"[TEST] Diretório de cache: {cache_folder}")
    expected_bands = {'S1': 2, 'S2': 4}
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
        logging.error(f"[TEST] Sensor '{sensor}' não suportado.")
        return None
    request = SentinelHubRequest(
        data_folder=str(cache_folder),
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=data_collection.define_from(name=f'{sensor.upper()}_CUSTOM', service_url=config.sh_base_url),
                time_interval=time_interval,
                mosaicking_order='leastCC' if sensor.upper() == 'S2' else None
            )
        ],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=study_area_bbox,
        size=(512, 512),
        config=config
    )
    logging.info(f"[TEST] Enviando requisição para {sensor}.")
    request.save_data()
    tiff_files = sorted(glob.glob(str(cache_folder / '**' / 'response.tiff'), recursive=True), key=os.path.getmtime, reverse=True)
    if not tiff_files:
        logging.error(f"[TEST] Nenhum response.tiff encontrado em {cache_folder}")
        return None
    latest_tiff = tiff_files[0]
    logging.info(f"[TEST] response.tiff encontrado: {latest_tiff}")
    try:
        with rasterio.open(latest_tiff) as src:
            logging.info(f"[TEST] Inspecting response.tiff:")
            logging.info(f"  Band count: {src.count}")
            logging.info(f"  Profile: {src.profile}")
            data = src.read()
            logging.info(f"  Data shape: {data.shape}")
            min_max_per_band = [(np.min(band), np.max(band)) for band in data]
            logging.info(f"  Data min/max (per band): {min_max_per_band}")
            profile = src.profile.copy()
            profile.update(
                driver='GTiff',
                count=expected_bands[sensor.upper()],
                photometric='MINISBLACK',
                compress='deflate',
                interleave='pixel',
                tiled=False
            )
            # Forçar configuração GDAL para MINISBLACK
            with rasterio.Env(GDAL_TIFF_OVR_BLOCKSIZE=512):
                with rasterio.open(output_path, 'w', **profile) as dst:
                    dst.write(data[:expected_bands[sensor.upper()]])
                    # Definir explicitamente a tag Photometric
                    dst.update_tags(PHOTOMETRIC='MINISBLACK')
    except Exception as e:
        logging.error(f"[TEST] Erro ao processar TIFF: {e}")
        return None
    try:
        with rasterio.open(output_path) as src:
            logging.info(f"[TEST] Arquivo final {output_path}:")
            logging.info(f"  Band count: {src.count}")
            logging.info(f"  Profile: {src.profile}")
            logging.info(f"  Tags: {src.tags()}")
            data = src.read()
            logging.info(f"  Data shape: {data.shape}")
            min_max_per_band = [(np.min(band), np.max(band)) for band in data]
            logging.info(f"  Data min/max (per band): {min_max_per_band}")
            if np.all(data == 0) or np.any(np.isnan(data)):
                logging.warning(f"[TEST] Dados inválidos detectados em {output_path}: todos zeros ou NaN")
            else:
                logging.info(f"[TEST] Dados válidos em {output_path}")
    except Exception as e:
        logging.error(f"[TEST] Erro ao validar arquivo final {output_path}: {e}")
        return None
    geodata_path = Path(f"output/analysis_-22.818_-47.069_1754079865/area_of_interest.geojson")
    if geodata_path.exists():
        clip_output_dir = output_path.parent / f"debug_processed_{sensor.lower()}"
        clip_raster_by_sectors(output_path, geodata_path, clip_output_dir)
    else:
        logging.warning(f"[TEST] GeoJSON {geodata_path} não encontrado. Pulando teste de recorte.")
    shutil.rmtree(cache_folder, ignore_errors=True)
    logging.info(f"[TEST] Download concluído: {output_path}")
    return output_path

if __name__ == '__main__':
    load_dotenv()
    auth_config = {
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET_ID"),
    }
    if not all(auth_config.values()):
        logging.error("[TEST] Credenciais não encontradas no .env")
        exit()
    bbox = [-47.110683, -22.846961, -47.03274, -22.769711]
    time_interval = ("2024-07-01", "2024-07-30")
    output_dir = Path("data/raw/sentinel")
    output_dir.mkdir(parents=True, exist_ok=True)
    s1_output = output_dir / "debug_s1.tiff"
    s2_output = output_dir / "debug_s2.tiff"
    job_id = "debug_tiff_warnings"
    logging.info("🚀 [TEST] Iniciando teste para Sentinel-1")
    download_and_save_sentinel_data('S1', auth_config, bbox, time_interval, s1_output, job_id=job_id)
    logging.info("🚀 [TEST] Iniciando teste para Sentinel-2")
    download_and_save_sentinel_data('S2', auth_config, bbox, time_interval, s2_output, job_id=job_id)
    logging.info("✅ [TEST] Teste concluído")
