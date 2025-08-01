import cdsapi
from pathlib import Path
import zipfile
import os
import xarray as xr
from calendar import monthrange

def _handle_decompression(downloaded_path: Path, final_path: Path):
    """Verifica se um arquivo é ZIP, extrai o conteúdo e renomeia."""
    if not zipfile.is_zipfile(downloaded_path):
        print("Arquivo não é ZIP. Renomeando para o caminho final.")
        downloaded_path.rename(final_path)
        return

    print("Arquivo detectado como ZIP. Iniciando descompactação...")
    with zipfile.ZipFile(downloaded_path, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        print(f"Arquivos no ZIP: {file_list}")

        nc_files = [f for f in file_list if f.endswith('.nc')]
        if not nc_files:
            raise FileNotFoundError("Nenhum arquivo .nc encontrado dentro do arquivo ZIP baixado.")

        extracted_file_name = nc_files[0]
        zip_ref.extract(extracted_file_name, path=final_path.parent)
        
        extracted_file_path = final_path.parent / extracted_file_name
        extracted_file_path.rename(final_path)

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
    Returns the output path on success.
    """
    print(f"🌍 Iniciando download de dados ERA5-Land para {output_path.name}")
    print(f"📍 Área solicitada: {area} (Norte/Oeste/Sul/Leste)")
    
    norte, oeste, sul, leste = area
    if norte <= sul:
        raise ValueError(f"❌ Área inválida: Norte ({norte}) deve ser > Sul ({sul})")
    if oeste >= leste:
        raise ValueError(f"❌ Área inválida: Oeste ({oeste}) deve ser < Leste ({leste})")
    
    area_lat = abs(norte - sul)
    area_lon = abs(leste - oeste) 
    print(f"📏 Dimensões da área: {area_lat:.4f}° x {area_lon:.4f}°")
    
    if area_lat > 10 or area_lon > 10:
        print(f"⚠️ ÁREA MUITO GRANDE! Lat: {area_lat:.2f}°, Lon: {area_lon:.2f}°")
        print(f"   Reduzindo para limites seguros da API...")
        
        center_lat = (norte + sul) / 2
        center_lon = (oeste + leste) / 2
        
        max_size = 5.0
        half_size = max_size / 2
        
        area = [
            center_lat + half_size,
            center_lon - half_size,
            center_lat - half_size,
            center_lon + half_size
        ]
        
        print(f"📐 Nova área ajustada: {area}")
        print(f"📏 Novas dimensões: {max_size:.1f}° x {max_size:.1f}°")
    
    temp_download_path = output_path.with_suffix('.download')

    try:
        temp_download_path.parent.mkdir(parents=True, exist_ok=True)
        
        client = cdsapi.Client()
        
        print("📡 Enviando requisição para a API do CDS...")
        
        request_data = {
            'variable': variables,
            'year': year,
            'month': month, 
            'day': days,
            'time': time,
            'area': area,
            'format': 'netcdf',
            'grid': [0.1, 0.1]
        }
        
        print(f"📋 Parâmetros da requisição: {request_data}")
        
        client.retrieve(
            'reanalysis-era5-land',
            request_data,
            str(temp_download_path)
        )
        print(f"✅ Download inicial concluído em: {temp_download_path}")

        if not temp_download_path.exists():
            raise FileNotFoundError(f"Arquivo não foi baixado: {temp_download_path}")
        
        file_size = temp_download_path.stat().st_size
        print(f"📦 Tamanho do arquivo baixado: {file_size / 1024:.1f} KB")
        
        if file_size < 1000:
            print(f"⚠️ Arquivo muito pequeno ({file_size} bytes), pode haver erro")

        _handle_decompression(temp_download_path, output_path)
        
        if output_path.exists():
            final_size = output_path.stat().st_size
            print(f"✅ Arquivo final: {final_size / 1024:.1f} KB")
        else:
            raise FileNotFoundError(f"Arquivo final não encontrado: {output_path}")
        
        print(f"🎉 Download completo! Arquivo salvo em: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Falha ao baixar os dados do ERA5-Land: {e}")
        print(f"💡 Dicas para resolver:")
        print(f"   1. Verifique suas credenciais do CDS")
        print(f"   2. Verifique se a área não é muito grande")
        print(f"   3. Verifique se as datas são válidas")
        print(f"   4. Tente novamente em alguns minutos")
        
        if temp_download_path.exists():
            os.remove(temp_download_path)
        raise

def safe_execute(func, description, *args, **kwargs):
    """Simulates the safe_execute function from run_analysis.py."""
    print(f"\n[TEST] Iniciando: {description}...")
    try:
        result = func(*args, **kwargs)
        if result is None and "Geração do mapa" not in description:
            print(f"⚠️ Etapa '{description}' não produziu resultados.")
            return None
        print(f"✅ [TEST-SUCCESS] Etapa '{description}' concluída.")
        return result
    except Exception as e:
        print(f"❌ [TEST-ERROR] Falha crítica na etapa '{description}': {str(e)}")
        raise

def test_download_era5():
    """Test harness for download_era5_land_data."""
    print("🚀 Starting ERA5-Land download test...")
    
    # Parameters from your pipeline run
    job_id = "analysis_-22.818_-47.069_1754078650"
    output_path = Path(f"data/raw/climate/{job_id}_era5.nc")
    area_cds = [-22.40409587125399, -47.510241818393816, -23.212575928745903, -46.63318158160609]
    year = "2024"
    month = "07"
    days = [str(d).zfill(2) for d in range(1, monthrange(int(year), int(month))[1] + 1)]
    variables = ["total_precipitation", "2m_temperature"]
    time = ["00:00", "12:00"]

    print(f"\n📋 Test parameters:")
    print(f"Output path: {output_path}")
    print(f"Area (N/W/S/E): {area_cds}")
    print(f"Year: {year}, Month: {month}, Days: {days}")
    print(f"Variables: {variables}")
    print(f"Time: {time}")

    # Run the download with safe_execute
    result = safe_execute(
        download_era5_land_data,
        "Download de dados climáticos ERA5",
        variables,
        year,
        month,
        days,
        time,
        area_cds,
        output_path
    )

    print(f"\n📈 Download function returned: {result}")

    # Verify the downloaded file
    if output_path.exists():
        print(f"✅ File exists at: {output_path}")
        file_size = output_path.stat().st_size / 1024
        print(f"📦 File size: {file_size:.1f} KB")

        try:
            ds = xr.open_dataset(output_path)
            print(f"\n📊 NetCDF file contents:")
            print(f"Dimensions: {dict(ds.sizes)}")
            print(f"Coordinates: {list(ds.coords)}")
            print(f"Variables: {list(ds.data_vars)}")

            era5_var_map = {
                "total_precipitation": "tp",
                "2m_temperature": "t2m"
            }
            for input_var in variables:
                era5_var = era5_var_map.get(input_var, input_var)
                if era5_var in ds.data_vars:
                    print(f"\n🔍 Variable {era5_var}:")
                    print(f"Shape: {ds[era5_var].shape}")
                    print(f"Mean value: {ds[era5_var].mean().values:.4f}")
                else:
                    print(f"⚠️ Variable {era5_var} not found in dataset")

            ds.close()
        except Exception as e:
            print(f"❌ Error opening NetCDF file: {e}")
    else:
        print(f"❌ File not found: {output_path}")

if __name__ == "__main__":
    test_download_era5()