# src/data/climate_downloader.py (CORRIGIDO - SEM LOGGING)
"""
Módulo para download de dados climáticos ERA5-Land do Copernicus Climate Data Store (CDS).
Inclui lógica para descompactar arquivos .zip que são baixados com extensão .nc.
"""
import cdsapi
from pathlib import Path
import zipfile
import os
import sys

def _handle_decompression(downloaded_path: Path, final_path: Path):
    """Verifica se um arquivo é ZIP, extrai o conteúdo e renomeia."""
    if not zipfile.is_zipfile(downloaded_path):
        print("Arquivo não é um ZIP. Renomeando para o caminho final.")
        downloaded_path.rename(final_path)
        return

    print("Arquivo detectado como ZIP. Iniciando descompactação...")
    with zipfile.ZipFile(downloaded_path, 'r') as zip_ref:
        # Lista os arquivos dentro do ZIP
        file_list = zip_ref.namelist()
        print(f"Arquivos no ZIP: {file_list}")

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
    print(f"Descompactação concluída. Arquivo final: {final_path}")

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
    
    CORREÇÕES APLICADAS:
    1. Adicionado parâmetro 'grid' obrigatório para netcdf
    2. Melhor validação da área
    3. Removido logging, usando apenas prints
    4. Melhor tratamento de erros
    """
    print(f"🌍 Iniciando download de dados ERA5-Land para {output_path.name}")
    print(f"📍 Área solicitada: {area} (Norte/Oeste/Sul/Leste)")
    
    # Validar área
    norte, oeste, sul, leste = area
    if norte <= sul:
        raise ValueError(f"❌ Área inválida: Norte ({norte}) deve ser > Sul ({sul})")
    if oeste >= leste:
        raise ValueError(f"❌ Área inválida: Oeste ({oeste}) deve ser < Leste ({leste})")
    
    # Calcular tamanho da área
    area_lat = abs(norte - sul)
    area_lon = abs(leste - oeste) 
    print(f"📏 Dimensões da área: {area_lat:.4f}° x {area_lon:.4f}°")
    
    # Verificar se a área é muito grande (limite da API)
    if area_lat > 10 or area_lon > 10:
        print(f"⚠️ ÁREA MUITO GRANDE! Lat: {area_lat:.2f}°, Lon: {area_lon:.2f}°")
        print(f"   Reduzindo para limites seguros da API...")
        
        # Reduzir para máximo de 5° em cada direção
        center_lat = (norte + sul) / 2
        center_lon = (oeste + leste) / 2
        
        max_size = 5.0  # graus
        half_size = max_size / 2
        
        area = [
            center_lat + half_size,  # norte
            center_lon - half_size,  # oeste
            center_lat - half_size,  # sul
            center_lon + half_size   # leste
        ]
        
        print(f"📐 Nova área ajustada: {area}")
        print(f"📏 Novas dimensões: {max_size:.1f}° x {max_size:.1f}°")
    
    # Define um caminho temporário para o download inicial
    temp_download_path = output_path.with_suffix('.download')

    try:
        temp_download_path.parent.mkdir(parents=True, exist_ok=True)
        
        client = cdsapi.Client()
        
        print("📡 Enviando requisição para a API do CDS...")
        
        # CORREÇÃO PRINCIPAL: Adicionar parâmetro 'grid' obrigatório
        request_data = {
            'variable': variables,
            'year': year,
            'month': month, 
            'day': days,
            'time': time,
            'area': area,
            'format': 'netcdf',
            'grid': [0.1, 0.1]  # 🔥 ADICIONADO: Grid de 0.1° (essencial!)
        }
        
        print(f"📋 Parâmetros da requisição: {request_data}")
        
        client.retrieve(
            'reanalysis-era5-land',
            request_data,
            str(temp_download_path)
        )
        print(f"✅ Download inicial concluído em: {temp_download_path}")

        # Verificar se o arquivo foi baixado
        if not temp_download_path.exists():
            raise FileNotFoundError(f"Arquivo não foi baixado: {temp_download_path}")
        
        # Verificar tamanho do arquivo
        file_size = temp_download_path.stat().st_size
        print(f"📦 Tamanho do arquivo baixado: {file_size / 1024:.1f} KB")
        
        if file_size < 1000:  # Menor que 1KB provavelmente é erro
            print(f"⚠️ Arquivo muito pequeno ({file_size} bytes), pode haver erro")

        # Chama a função para lidar com a possível descompactação
        _handle_decompression(temp_download_path, output_path)
        
        # Verificar arquivo final
        if output_path.exists():
            final_size = output_path.stat().st_size
            print(f"✅ Arquivo final: {final_size / 1024:.1f} KB")
        else:
            raise FileNotFoundError(f"Arquivo final não encontrado: {output_path}")
        
        print(f"🎉 Download completo! Arquivo salvo em: {output_path}")
        return output_path  # Add this line

    except Exception as e:
        print(f"❌ Falha ao baixar os dados do ERA5-Land: {e}")
        print(f"💡 Dicas para resolver:")
        print(f"   1. Verifique suas credenciais do CDS")
        print(f"   2. Verifique se a área não é muito grande")
        print(f"   3. Verifique se as datas são válidas")
        print(f"   4. Tente novamente em alguns minutos")
        
        # Limpa o arquivo temporário em caso de erro
        if temp_download_path.exists():
            os.remove(temp_download_path)
        raise
# Bloco para execução standalone (para testes)
if __name__ == '__main__':
    print("--- MODO DE TESTE: Executando climate_downloader.py de forma isolada ---")
    
    # Adiciona o diretório raiz do projeto ao PYTHONPATH
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    try:
        # CORREÇÃO: Imports corrigidos para a estrutura real do projeto
        from src.config import settings
        from src.utils import paths
        from calendar import monthrange
    except ModuleNotFoundError as e:
        print(f"❌ Erro de importação: {e}")
        print("📁 Estrutura de projeto esperada:")
        print("   - src/config/settings.py")
        print("   - src/utils/paths.py")
        print("💡 Certifique-se de que:")
        print("   1. Os arquivos existem nos caminhos corretos")
        print("   2. Há arquivos __init__.py nas pastas src/, src/config/ e src/utils/")
        print("   3. Você está executando do diretório raiz do projeto")
        exit(1)

    # Cria estrutura de diretórios
    paths.create_project_dirs()

    # Configura parâmetros de teste
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
        print("✅ --- TESTE STANDALONE DO CLIMATE DOWNLOADER CONCLUÍDO COM SUCESSO ---")
    except Exception as e:
        print(f"❌ --- TESTE STANDALONE DO CLIMATE DOWNLOADER FALHOU: {e} ---")