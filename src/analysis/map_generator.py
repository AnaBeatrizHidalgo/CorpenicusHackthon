# Importações
import os
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import contextily as ctx

# Configurar diretórios
os.makedirs('data/processed', exist_ok=True)
print('✓ Diretório data/processed/ criado ou já existente')

# Definir caminhos
sectors_path = 'data/area_prova_barao.geojson'
metrics_path = 'data/processed/climate_metrics.csv'
output_dir = 'data/processed'

# Verificar arquivos de entrada
print('\n--- Verificando arquivos de entrada ---')
for path in [sectors_path, metrics_path]:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f'✓ {path} ({size_mb:.1f} MB)')
    else:
        print(f'❌ {path} não encontrado')
try:
    # Carregar setores censitários
    gdf = gpd.read_file(sectors_path)
    gdf = gdf[(gdf['SITUACAO'] == 'Urbana') & (gdf['AREA_KM2'] <= 1.0)]
    print(f'✓ Carregados {len(gdf)} setores urbanos')

    # Carregar métricas mescladas
    metrics_df = pd.read_csv(metrics_path)
    print(f'✓ Carregadas {len(metrics_df)} métricas de setores')

    # Corrigir tipo de CD_SETOR em gdf para int64
    gdf['CD_SETOR'] = pd.to_numeric(gdf['CD_SETOR'], errors='coerce').astype('int64')
    print(f'✓ Tipo de CD_SETOR em gdf: {gdf['CD_SETOR'].dtype}')

    # Mesclar geometria com métricas
    gdf = gdf.merge(metrics_df, on='CD_SETOR', how='left')
    print(f'✓ Dados mesclados com sucesso: {len(gdf)} setores')
except Exception as e:
    print(f'❌ Erro ao carregar dados: {e}')

if 'gdf' in locals():
    # Configurar figura
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    # Mapa de Precipitação
    gdf.plot(column='precip_mean_mm', ax=ax1, legend=True, cmap='Blues',
             missing_kwds={'color': 'lightgrey'}, vmin=gdf['precip_mean_mm'].min(),
             vmax=gdf['precip_mean_mm'].max())
    ax1.set_title('Precipitação Média (mm)')
    ctx.add_basemap(ax1, crs=gdf.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik)

    # Mapa de Temperatura
    gdf.plot(column='temp_mean_C', ax=ax2, legend=True, cmap='Reds',
             missing_kwds={'color': 'lightgrey'}, vmin=gdf['temp_mean_C'].min(),
             vmax=gdf['temp_mean_C'].max())
    ax2.set_title('Temperatura Média (°C)')
    ctx.add_basemap(ax2, crs=gdf.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik)

    # Mapa de NDVI
    gdf.plot(column='NDVI_mean', ax=ax3, legend=True, cmap='Greens',
             missing_kwds={'color': 'lightgrey'}, vmin=gdf['NDVI_mean'].min(),
             vmax=gdf['NDVI_mean'].max())
    ax3.set_title('NDVI Médio')
    ctx.add_basemap(ax3, crs=gdf.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik)

    # Ajustes finais
    for ax in [ax1, ax2, ax3]:
        ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(f'{output_dir}/spatial_maps.png', dpi=300, bbox_inches='tight')
    print(f'✓ Mapas salvos em {output_dir}/spatial_maps.png')
else:
    print('❌ Pulando geração de mapas devido a dados ausentes')
if 'gdf' in locals():
    print('\n' + '='*50)
    print('📋 RESUMO DA VISUALIZAÇÃO')
    print('='*50)
    print(f'✓ Setores com dados: {len(gdf)}')
    print(f'✓ Média Precipitação: {gdf["precip_mean_mm"].mean():.2f} mm')
    print(f'✓ Média Temperatura: {gdf["temp_mean_C"].mean():.2f} °C')
    print(f'✓ Média NDVI: {gdf["NDVI_mean"].mean():.2f}')
    print(f'✓ Setores com NaN: {len(gdf[gdf[["precip_mean_mm", "temp_mean_C", "NDVI_mean"]].isna().any(axis=1)])}')

    print('\n🗂️ ARQUIVOS GERADOS:')
    import glob
    for file in glob.glob(f'{output_dir}/*spatial*.png'):
        if os.path.exists(file):
            print(f'  ✓ {file} (Tamanho: {os.path.getsize(file) / 1024 / 1024:.2f} MB)')