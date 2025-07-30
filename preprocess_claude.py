# Correção para a seção "2. Validação da Bounding Box"

import os
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import matplotlib.pyplot as plt
import numpy as np
from rasterio.plot import show
import glob

# Configurar diretórios
os.makedirs('data/processed', exist_ok=True)
print('✓ Diretório data/processed/ criado ou já existente')

# Definir caminhos
s1_path = 'data/sentinel1_unicamp.tiff'
s2_path = 'data/sentinel2_unicamp.tiff'
bbox_path = 'data/area_prova_bbox.geojson'
sectors_path = 'data/area_prova_barao.geojson'

# CORREÇÃO 1: Carregamento da Bounding Box
try:
    bbox_gdf = gpd.read_file(bbox_path)
    print(f'✓ Bounding box carregada: {len(bbox_gdf)} polígono(s)')
    print(f'  CRS original: {bbox_gdf.crs}')
    
    # Verificar se já está em WGS84, se não, converter
    if bbox_gdf.crs != 'EPSG:4326':
        bbox_gdf = bbox_gdf.to_crs('EPSG:4326')
        print('✓ Bounding box convertida para EPSG:4326 (WGS84)')
    
    # Mostrar bounds para debug
    bounds = bbox_gdf.bounds
    print(f'  Bounds: minx={bounds.minx.iloc[0]:.4f}, miny={bounds.miny.iloc[0]:.4f}, '
          f'maxx={bounds.maxx.iloc[0]:.4f}, maxy={bounds.maxy.iloc[0]:.4f}')
    
except Exception as e:
    print(f'❌ Erro ao carregar {bbox_path}: {e}')
    bbox_gdf = None

# CORREÇÃO 2: Função de validação melhorada
def validate_bbox_coverage(tiff_path, gdf, title, output_file):
    """Visualiza a imagem com a bounding box sobreposta."""
    if not os.path.exists(tiff_path):
        print(f'❌ Arquivo {tiff_path} não encontrado')
        return False
    
    try:
        with rasterio.open(tiff_path) as src:
            print(f'  CRS da imagem: {src.crs}')
            print(f'  Bounds da imagem: {src.bounds}')
            print(f'  Dimensões: {src.width} x {src.height}')
            print(f'  Bandas: {src.count}')
            
            # Converter GeoDataFrame para o CRS da imagem
            gdf_reproj = gdf.to_crs(src.crs)
            print(f'  Bounds da bbox reprojetada: {gdf_reproj.bounds.iloc[0].values}')
            
            # Ler a imagem
            image = src.read()
            
            # Preparar visualização
            fig, ax = plt.subplots(figsize=(15, 12))
            
            # Mostrar imagem baseada no tipo
            if image.shape[0] >= 3:  # Sentinel-2 (RGB+NIR)
                # Normalizar para RGB
                rgb = image[[0, 1, 2]]  # R, G, B
                # Aplicar stretch para melhor visualização
                rgb_norm = np.zeros_like(rgb, dtype=np.float32)
                for i in range(3):
                    band = rgb[i]
                    p2, p98 = np.percentile(band[band > 0], [2, 98])
                    rgb_norm[i] = np.clip((band - p2) / (p98 - p2), 0, 1)
                
                img_display = rgb_norm.transpose(1, 2, 0)
                ax.imshow(img_display, extent=[src.bounds.left, src.bounds.right, 
                                             src.bounds.bottom, src.bounds.top])
                print('  Visualizando Sentinel-2 como RGB')
                
            else:  # Sentinel-1 (VV/VH)
                # Usar primeira banda (VV)
                band = image[0]
                # Aplicar log para SAR
                band_log = np.log10(band + 1e-10)
                vmin, vmax = np.percentile(band_log[band_log > -10], [5, 95])
                
                im = ax.imshow(band_log, cmap='gray', vmin=vmin, vmax=vmax,
                              extent=[src.bounds.left, src.bounds.right, 
                                     src.bounds.bottom, src.bounds.top])
                plt.colorbar(im, ax=ax, label='Log Backscatter (dB)')
                print('  Visualizando Sentinel-1 (VV) em escala log')
            
            # Plotar bounding box
            gdf_reproj.boundary.plot(ax=ax, color='yellow', linewidth=3, label='Área de Interesse')
            
            # Configurar plot
            ax.set_title(title, fontsize=16)
            ax.set_xlabel('Longitude' if src.crs.to_string() == 'EPSG:4326' else 'X (m)')
            ax.set_ylabel('Latitude' if src.crs.to_string() == 'EPSG:4326' else 'Y (m)')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.show()
            print(f'✓ Visualização salva em {output_file}')
            return True
            
    except Exception as e:
        print(f'❌ Erro na validação da bounding box para {tiff_path}: {e}')
        import traceback
        traceback.print_exc()
        return False

# CORREÇÃO 3: Executar validação com tratamento de erros
if bbox_gdf is not None:
    print('\n--- Validando Sentinel-1 ---')
    s1_ok = validate_bbox_coverage(s1_path, bbox_gdf, 
                                  'Sentinel-1 (VV) com Área de Interesse - Barão Geraldo', 
                                  'data/processed/s1_bbox_validation.png')
    
    print('\n--- Validando Sentinel-2 ---')
    s2_ok = validate_bbox_coverage(s2_path, bbox_gdf, 
                                  'Sentinel-2 (RGB) com Área de Interesse - Barão Geraldo', 
                                  'data/processed/s2_bbox_validation.png')
    
    print(f'\n✅ Resultados da validação:')
    print(f'  Sentinel-1: {"✓" if s1_ok else "❌"}')
    print(f'  Sentinel-2: {"✓" if s2_ok else "❌"}')
else:
    print('❌ Não foi possível carregar a bounding box para validação')

# CORREÇÃO 4: Verificar se os arquivos existem
print('\n--- Verificando arquivos de entrada ---')
files_to_check = [s1_path, s2_path, bbox_path, sectors_path]
for file_path in files_to_check:
    if os.path.exists(file_path):
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f'✓ {file_path} ({size_mb:.1f} MB)')
    else:
        print(f'❌ {file_path} não encontrado')