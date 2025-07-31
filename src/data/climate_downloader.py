# src/data/climate_downloader.py (Com descompactação)
"""
Módulo para download de dados climáticos ERA5-Land do Copernicus Climate Data Store (CDS).
Inclui lógica para descompactar arquivos .zip que são baixados com extensão .nc.
"""
import logging
import cdsapi
from pathlib import Path
import zipfile
import os

def _handle_decompression(downloaded_path: Path, final_path: Path):
    """Verifica se um arquivo é ZIP, extrai o conteúdo e renomeia."""
    if not zipfile.is_zipfile(downloaded_path):
        logging.info("Arquivo não é um ZIP. Renomeando para o caminho final.")
        downloaded_path.rename(final_path)
        return

    logging.info("Arquivo detectado como ZIP. Iniciando descompactação...")
    with zipfile.ZipFile(downloaded_path, 'r') as zip_ref:
        # Lista os arquivos dentro do ZIP
        file_list = zip_ref.namelist()
        logging.info(f"Arquivos no ZIP: {file_list}")

        # Encontra o primeiro arquivo .nc dentro do ZIP
        nc_files = [f for f in file_list if f.endswith('.nc')]
        if not nc_files:
            raise FileNotFoundError("Nenhum arquivo .nc encontrado dentro do arquivo ZIP baixado.")

        # Extrai o arquivo .nc
        extracted_file_name = nc_files[0]
        zip_ref.extract(extracted_file_name, path=final_path.parent)
        
        # Renomeia o arquivo extraído para o nome de saída final
        extracted_file_path = final_path.parent / extracted_file_name
        extracted_file_path.rename(final_path)

    # Remove o arquivo .zip original que foi baixado
    os.remove(downloaded_path)
    logging.info(f"Descompactação concluída. Arquivo final: {final_path}")


def download_era5_land_data(
    variables: list,
    year: str,
    month: str,
    days: list,
    time: list,
    area: list,
    output_path: Path
):
    """
    Baixa dados do reanálise ERA5-Land e lida com a descompactação.

    Args:
        ... (argumentos permanecem os mesmos) ...
        output_path (Path): Caminho FINAL desejado para o arquivo .nc.
    """
    logging.info(f"Iniciando download de dados ERA5-Land para {output_path.name}")
    
    # Define um caminho temporário para o download inicial
    temp_download_path = output_path.with_suffix('.download')

    try:
        temp_download_path.parent.mkdir(parents=True, exist_ok=True)
        
        client = cdsapi.Client()
        
        logging.info("Enviando requisição para a API do CDS...")
        client.retrieve(
            'reanalysis-era5-land',
            {
                'variable': variables, 'year': year, 'month': month, 'day': days,
                'time': time, 'area': area, 'format': 'netcdf'
            },
            str(temp_download_path)
        )
        logging.info(f"Download inicial concluído em: {temp_download_path}")

        # Chama a função para lidar com a possível descompactação
        _handle_decompression(temp_download_path, output_path)

    except Exception as e:
        logging.error(f"Falha ao baixar os dados do ERA5-Land: {e}", exc_info=True)
        # Limpa o arquivo temporário em caso de erro
        if temp_download_path.exists():
            os.remove(temp_download_path)
        raise


# Bloco para execução standalone (para testes)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.info("--- MODO DE TESTE: Executando climate_downloader.py de forma isolada ---")

    try:
        from config import settings
        from src.utils import paths
        from calendar import monthrange
    except ModuleNotFoundError:
        logging.error("Execute este script a partir da raiz do projeto: python -m src.data.climate_downloader")
        exit()

    paths.create_project_dirs()

    bbox_sh = settings.STUDY_AREA['bbox']
    area_cds = [bbox_sh[3], bbox_sh[0], bbox_sh[1], bbox_sh[2]]
    date_config = settings.DATA_RANGES['monitoramento_dengue']
    
    year, month = date_config['start'][:4], date_config['start'][5:7]
    num_days = monthrange(int(year), int(month))[1]
    days_list = [str(day).zfill(2) for day in range(1, num_days + 1)]

    test_output_path = paths.RAW_CLIMATE_DIR / f"era5_test_{year}-{month}.nc"

    try:
        download_era5_land_data(
            variables=['total_precipitation', '2m_temperature'],
            year=year, month=month, days=days_list,
            time=['00:00', '06:00', '12:00', '18:00'],
            area=area_cds,
            output_path=test_output_path
        )
        logging.info("--- TESTE STANDALONE DO CLIMATE DOWNLOADER CONCLUÍDO COM SUCESSO ---")
    except Exception as e:
        logging.error(f"--- TESTE STANDALONE DO CLIMATE DOWNLOADER FALHOU: {e} ---")