# src/features/image_processor.py
"""
Módulo para processar imagens de satélite brutas.

A principal função é recortar (clip) as imagens de satélite (rasters)
com base nos polígonos dos setores censitários (vetor).
"""
import logging
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.mask import mask

def clip_raster_by_sectors(
    raster_path: Path,
    geodata_path: Path,
    output_dir: Path
):
    """
    Recorta um raster para cada polígono de um arquivo GeoJSON.

    Para cada setor no GeoJSON, um novo arquivo GeoTIFF recortado é salvo
    no diretório de saída, nomeado com o ID do setor.

    Args:
        raster_path (Path): Caminho para o arquivo GeoTIFF de entrada (ex: Sentinel-2).
        geodata_path (Path): Caminho para o arquivo GeoJSON dos setores.
        output_dir (Path): Diretório onde os arquivos recortados serão salvos.
    """
    logging.info(f"Iniciando recorte do raster '{raster_path.name}' por setores.")
    
    try:
        sectors = gpd.read_file(geodata_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with rasterio.open(raster_path) as src:
            # Garante que os setores estejam na mesma projeção do raster
            sectors = sectors.to_crs(src.crs)
            
            logging.info(f"Processando {len(sectors)} setores...")
            for index, sector in sectors.iterrows():
                sector_id = sector['CD_SETOR']
                geom = [sector.geometry] # A função mask espera uma lista de geometrias

                try:
                    # Aplica a máscara
                    out_image, out_transform = mask(src, geom, crop=True)
                    out_meta = src.meta.copy()

                    # Atualiza o metadado do novo arquivo recortado
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_image.shape[1],
                        "width": out_image.shape[2],
                        "transform": out_transform
                    })
                    
                    # Define o caminho de saída para o arquivo recortado
                    output_path = output_dir / f"{raster_path.stem}_sector_{sector_id}.tiff"

                    with rasterio.open(output_path, "w", **out_meta) as dest:
                        dest.write(out_image)

                except ValueError as e:
                    # Este erro acontece se um setor estiver totalmente fora da imagem
                    logging.warning(f"Setor {sector_id} fora dos limites do raster '{raster_path.name}'. Pulando. Erro: {e}")
                    continue
            
        logging.info(f"Recorte do raster '{raster_path.name}' concluído. Arquivos salvos em: {output_dir}")

    except Exception as e:
        logging.error(f"Falha ao recortar o raster '{raster_path.name}': {e}", exc_info=True)
        raise

# Bloco para execução standalone (para testes)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.info("--- MODO DE TESTE: Executando image_processor.py de forma isolada ---")

    try:
        from config import settings
        from src.utils import paths
    except ModuleNotFoundError:
        logging.error("Execute este script a partir da raiz do projeto: python -m src.features.image_processor")
        exit()

    # Define os caminhos de entrada e saída para o teste
    # Usando uma das imagens que o pipeline já baixou
    raw_s2_image = paths.RAW_SENTINEL_DIR / "s2_2024-07-01_a_2024-07-30.tiff" 
    geodata_file = paths.RAW_GEODATA_DIR / "setores_barao.geojson"
    
    # Salva os recortes do S2 em um subdiretório
    processed_s2_dir = paths.PROCESSED_DIR / "images" / "sentinel-2"

    if not raw_s2_image.exists() or not geodata_file.exists():
        logging.error("Arquivos de entrada para o teste não encontrados!")
        logging.error(f"Verifique se '{raw_s2_image}' e '{geodata_file}' existem.")
    else:
        try:
            clip_raster_by_sectors(
                raster_path=raw_s2_image,
                geodata_path=geodata_file,
                output_dir=processed_s2_dir
            )
            logging.info("--- TESTE STANDALONE DO IMAGE PROCESSOR CONCLUÍDO COM SUCESSO ---")
        except Exception as e:
            logging.error(f"--- TESTE STANDALONE DO IMAGE PROCESSOR FALHOU: {e} ---")