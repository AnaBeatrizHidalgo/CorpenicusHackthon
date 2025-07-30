# Importações
import os
import cdsapi
import xarray as xr
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from shapely.geometry import box

# Configurar diretórios
os.makedirs('data/processed', exist_ok=True)
print('✓ Diretório data/processed/ criado ou já existente')

# Verificar versão do cdsapi
import cdsapi
print(f'✓ Versão do cdsapi: {cdsapi.__version__}')

# Definir caminhos
sectors_path = 'data/area_prova_barao.geojson'
metrics_path = 'data/processed/metrics.csv'
climate_path = 'data/processed/data_0.nc'
output_csv = 'data/processed/climate_metrics.csv'

# Verificar arquivos de entrada
print('\n--- Verificando arquivos de entrada ---')
for path in [sectors_path, metrics_path]:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f'✓ {path} ({size_mb:.1f} MB)')
    else:
        print(f'❌ {path} não encontrado')
try:
    c = cdsapi.Client()
    c.retrieve(
        'reanalysis-era5-land',
        {
            'variable': ['total_precipitation', '2m_temperature'],
            'year': '2025',
            'month': '06',
            'day': [str(i).zfill(2) for i in range(1, 31)],
            'time': ['00:00', '06:00', '12:00', '18:00'],
            'area': [-22.75, -47.15, -22.95, -46.95],  # [N, W, S, E]
            'format': 'netcdf'
        },
        'data/processed/era5_climate.nc')
    print(f'✓ Dados climáticos salvos em data/processed/era5_climate.nc')
except Exception as e:
    print(f'❌ Erro ao baixar dados ERA5-Land: {e}')

try:
    # Verificar NetCDF
    if os.path.exists(climate_path):
        ds = xr.open_dataset(climate_path, engine='netcdf4')
        print(f'✓ Coordenadas do NetCDF:')
        print(f'  Latitude: {ds['latitude'].values}')
        print(f'  Longitude: {ds['longitude'].values}')
        print(f'  Bounding box: (min_lon, min_lat, max_lon, max_lat) = '
              f'({ds['longitude'].min().values}, {ds['latitude'].min().values}, '
              f'{ds['longitude'].max().values}, {ds['latitude'].max().values})')
        print(f'  Número de pontos: {len(ds['latitude']) * len(ds['longitude'])}')

        # Verificar cobertura dos setores
        gdf = gpd.read_file(sectors_path)
        gdf = gdf[(gdf['SITUACAO'] == 'Urbana') & (gdf['AREA_KM2'] <= 1.0)]
        bounds = gdf.bounds
        sectors_bbox = (bounds['minx'].min(), bounds['miny'].min(), bounds['maxx'].max(), bounds['maxy'].max())
        print(f'\n✓ Bounding box dos setores censitários:')
        print(f'  (min_lon, min_lat, max_lon, max_lat) = {sectors_bbox}')
        print(f'\n✓ Verificação de cobertura:')
        if (ds['longitude'].min() <= sectors_bbox[0] and ds['longitude'].max() >= sectors_bbox[2] and
            ds['latitude'].min() <= sectors_bbox[1] and ds['latitude'].max() >= sectors_bbox[3]):
            print('  ✓ NetCDF cobre completamente a área dos setores')
        else:
            print('  ⚠️ NetCDF não cobre completamente a área dos setores')
        ds.close()
    else:
        print(f'❌ {climate_path} não encontrado')

    # Resumo dos setores
    print(f'\n✓ Total de setores urbanos: {len(gdf)}')
except Exception as e:
    print(f'❌ Erro ao verificar coordenadas: {e}')
def aggregate_climate_by_sector(climate_path, sectors_path):
    """Agrega dados climáticos por setor censitário."""
    try:
        # Verificar arquivo NetCDF
        if not os.path.exists(climate_path):
            raise FileNotFoundError(f'{climate_path} não encontrado')
        with xr.open_dataset(climate_path, engine='netcdf4') as ds:
            print(f'✓ Arquivo {climate_path} válido, variáveis: {list(ds.variables)}')

        # Carregar setores censitários
        gdf = gpd.read_file(sectors_path)
        gdf = gdf[(gdf['SITUACAO'] == 'Urbana') & (gdf['AREA_KM2'] <= 1.0)]
        print(f'✓ Carregados {len(gdf)} setores urbanos')

        # Carregar dados climáticos
        ds = xr.open_dataset(climate_path, engine='netcdf4')
        # Corrigir nomes de variáveis
        ds['total_precipitation'] = ds['tp'] * 1000  # metros para mm
        ds['t2m'] = ds['t2m'] - 273.15  # Kelvin para °C

        # Média mensal por pixel
        precip_mean = ds['total_precipitation'].mean(dim='valid_time')
        temp_mean = ds['t2m'].mean(dim='valid_time')

        # Configurar interpoladores
        lat, lon = ds['latitude'].values, ds['longitude'].values
        precip_interp = RegularGridInterpolator(
            (lat, lon), precip_mean.values,
            method='nearest', bounds_error=False, fill_value=np.nan
        )
        temp_interp = RegularGridInterpolator(
            (lat, lon), temp_mean.values,
            method='nearest', bounds_error=False, fill_value=np.nan
        )

        climate_metrics = []
        sectors_with_data = 0
        for idx, row in gdf.iterrows():
            cd_setor = int(row['CD_SETOR'])  # Converter para int64
            geom = row['geometry']
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
            # Máscara ajustada para latitude decrescente
            mask = (ds['longitude'] >= bounds[0]) & (ds['longitude'] <= bounds[2]) & \
                   (ds['latitude'] >= bounds[3]) & (ds['latitude'] <= bounds[1])
            if mask.any():
                precip = precip_mean.where(mask, drop=True).mean().values
                temp = temp_mean.where(mask, drop=True).mean().values
                if not np.isnan(precip) and not np.isnan(temp):
                    sectors_with_data += 1
                climate_metrics.append({
                    'CD_SETOR': cd_setor,
                    'precip_mean_mm': float(precip) if not np.isnan(precip) else np.nan,
                    'temp_mean_C': float(temp) if not np.isnan(temp) else np.nan
                })
                print(f'✓ Processado setor {cd_setor}: Precip={precip:.2f} mm, Temp={temp:.2f} °C')
            else:
                # Fallback: usar interpolação no centróide do setor
                centroid = geom.centroid
                precip = precip_interp((centroid.y, centroid.x))
                temp = temp_interp((centroid.y, centroid.x))
                if not np.isnan(precip) and not np.isnan(temp):
                    sectors_with_data += 1
                climate_metrics.append({
                    'CD_SETOR': cd_setor,
                    'precip_mean_mm': float(precip) if not np.isnan(precip) else np.nan,
                    'temp_mean_C': float(temp) if not np.isnan(temp) else np.nan
                })
                print(f'⚠️ Setor {cd_setor} fora da grade; usado interpolação: Precip={precip:.2f} mm, Temp={temp:.2f} °C')
        print(f'\n✓ Total de setores com dados válidos: {sectors_with_data}/{len(gdf)}')
        climate_df = pd.DataFrame(climate_metrics)
        climate_df['CD_SETOR'] = climate_df['CD_SETOR'].astype('int64')  # Garantir tipo int64
        return climate_df
    except Exception as e:
        print(f'❌ Erro ao agregar dados climáticos: {e}')
        return None

if os.path.exists(climate_path) and os.path.exists(sectors_path):
    print('\n--- Agregando dados climáticos por setor ---')
    climate_df = aggregate_climate_by_sector(climate_path, sectors_path)
    if climate_df is not None:
        climate_df.to_csv(output_csv, index=False)
        print(f'✓ Métricas climáticas salvas em {output_csv}')
else:
    print('❌ Pulando agregação devido a arquivos ausentes')

if 'climate_df' in locals() and os.path.exists(metrics_path):
    print('\n--- Mesclando e calculando correlações ---')
    metrics_df = pd.read_csv(metrics_path)
    # Verificar tipos de dados
    print(f'✓ Tipo de CD_SETOR em metrics_df: {metrics_df['CD_SETOR'].dtype}')
    print(f'✓ Tipo de CD_SETOR em climate_df: {climate_df['CD_SETOR'].dtype}')
    # Garantir que CD_SETOR em metrics_df seja int64
    metrics_df['CD_SETOR'] = metrics_df['CD_SETOR'].astype('int64')
    merged_df = metrics_df.merge(climate_df, on='CD_SETOR', how='left')
    merged_df.to_csv(output_csv, index=False)
    print(f'✓ Dados mesclados salvos em {output_csv}')

    # Calcular correlações
    correlations = merged_df[['NDVI_mean', 'VV_mean_dB', 'VH_mean_dB', 'precip_mean_mm', 'temp_mean_C']].corr()
    print('\nCorrelações:')
    print(correlations)

    # Gráfico: NDVI vs. Precipitação
    plt.figure(figsize=(10, 6))
    plt.scatter(merged_df['precip_mean_mm'], merged_df['NDVI_mean'], color='green', alpha=0.6)
    plt.title('Correlação: NDVI Médio vs. Precipitação Média', fontsize=14)
    plt.xlabel('Precipitação Média (mm)')
    plt.ylabel('NDVI Médio')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('data/processed/ndvi_precip_correlation.png', dpi=300, bbox_inches='tight')
    plt.show()
    print('✓ Gráfico salvo em data/processed/ndvi_precip_correlation.png')

    # Gráfico: NDVI vs. Temperatura
    plt.figure(figsize=(10, 6))
    plt.scatter(merged_df['temp_mean_C'], merged_df['NDVI_mean'], color='blue', alpha=0.6)
    plt.title('Correlação: NDVI Médio vs. Temperatura Média', fontsize=14)
    plt.xlabel('Temperatura Média (°C)')
    plt.ylabel('NDVI Médio')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('data/processed/ndvi_temp_correlation.png', dpi=300, bbox_inches='tight')
    plt.show()
    print('✓ Gráfico salvo em data/processed/ndvi_temp_correlation.png')
else:
    print('❌ Pulando mesclagem devido a dados ausentes')
print('\n' + '='*50)
print('📋 RESUMO DA EXECUÇÃO')
print('='*50)
if 'climate_df' in locals():
    print(f'✓ Setores com métricas climáticas: {len(climate_df)}')
    print(f'✓ Setores com dados válidos: {len(climate_df[climate_df[["precip_mean_mm", "temp_mean_C"]].notna().all(axis=1)])}')
    print(f'✓ Média Precipitação: {climate_df["precip_mean_mm"].mean():.2f} mm')
    print(f'✓ Média Temperatura: {climate_df["temp_mean_C"].mean():.2f} °C')
if 'merged_df' in locals():
    print(f'✓ Correlação NDVI-Precipitação: {correlations.loc["NDVI_mean", "precip_mean_mm"]:.3f}')
    print(f'✓ Correlação NDVI-Temperatura: {correlations.loc["NDVI_mean", "temp_mean_C"]:.3f}')

print('\n🗂️ ARQUIVOS GERADOS:')
import glob
for file in glob.glob('data/processed/*climate*.csv') + glob.glob('data/processed/*correlation*.png'):
    if os.path.exists(file):
        print(f'  ✓ {file} (Tamanho: {os.path.getsize(file) / 1024 / 1024:.2f} MB)')