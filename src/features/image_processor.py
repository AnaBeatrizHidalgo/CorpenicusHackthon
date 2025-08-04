# src/features/image_processor_fixed.py

import logging
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import traceback
import glob

def find_raster_file(raster_path: Path, job_id: str = None) -> Path:
    """
    Localiza inteligentemente o arquivo raster, mesmo se o caminho estiver incorreto.
    """
    # Se o arquivo existe no caminho especificado, retorna
    if raster_path.exists():
        return raster_path
    
    logging.warning(f"Arquivo não encontrado em {raster_path}. Procurando automaticamente...")
    
    # Possíveis diretórios onde o arquivo pode estar
    base_dir = Path.cwd()
    search_dirs = [
        base_dir / "data" / "raw" / "sentinel",
        base_dir / "data" / "processed", 
        base_dir / "data",
        base_dir / "output" / (job_id or ""),
        raster_path.parent,
    ]
    
    # Padrões de busca baseados no nome do arquivo original
    sensor = "s1" if "s1" in raster_path.name.lower() else "s2"
    patterns = [
        f"*{job_id or ''}*{sensor}*.tiff",
        f"*{job_id or ''}*{sensor}*.tif",
        f"*{sensor}*.tiff",
        f"*{sensor}*.tif",
        f"*{sensor.upper()}*.tiff",
        f"*{sensor.upper()}*.tif",
        raster_path.name,  # Nome exato
        f"*{raster_path.stem}*",  # Qualquer arquivo com nome similar
    ]
    
    logging.info(f"Procurando arquivo {sensor.upper()} em {len(search_dirs)} diretórios...")
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
            
        logging.info(f"  Verificando: {search_dir}")
        
        for pattern in patterns:
            found_files = list(search_dir.glob(pattern))
            if found_files:
                found_file = found_files[0]  #
                logging.info(f"  ✅ Arquivo encontrado: {found_file}")
                return found_file
    
    # Se não encontrou nada, lista arquivos disponíveis para ajudar no debug
    logging.error(f"❌ Arquivo {sensor.upper()} não encontrado em nenhum diretório.")
    logging.error("📁 Arquivos .tiff encontrados:")
    
    for search_dir in search_dirs[:3]:  # Mostra apenas os 3 primeiros diretórios
        if search_dir.exists():
            tiff_files = list(search_dir.glob("*.tiff")) + list(search_dir.glob("*.tif"))
            for tiff_file in tiff_files[:5]:  # Máximo 5 arquivos por diretório
                logging.error(f"     {tiff_file}")
    
    raise FileNotFoundError(f"Arquivo raster {sensor.upper()} não encontrado: {raster_path}")

def validate_raster_file(raster_path: Path) -> bool:
    """
    Valida se um arquivo raster está íntegro e contém dados válidos.
    """
    try:
        with rasterio.open(raster_path) as src:
            logging.info(f"📊 Validando raster: {raster_path.name}")
            logging.info(f"   Bandas: {src.count}, CRS: {src.crs}, Shape: {src.width}x{src.height}")
            
            # Verificar se há dados válidos em uma amostra
            sample_window = rasterio.windows.Window(0, 0, min(100, src.width), min(100, src.height))
            sample_data = src.read(1, window=sample_window)
            
            if src.nodata is not None:
                valid_pixels = np.sum(~np.isnan(sample_data) & (sample_data != src.nodata))
            else:
                valid_pixels = np.sum(~np.isnan(sample_data))
            
            total_pixels = sample_data.size
            valid_ratio = valid_pixels / total_pixels if total_pixels > 0 else 0
            
            logging.info(f"   Pixels válidos na amostra: {valid_pixels}/{total_pixels} ({valid_ratio:.1%})")
            
            if valid_ratio < 0.01:  # Menos de 1% de pixels válidos
                logging.warning(f"⚠️ Raster {raster_path.name} tem poucos dados válidos ({valid_ratio:.1%})")
                
            return True
            
    except Exception as e:
        logging.error(f"❌ Raster {raster_path.name} está corrompido: {e}")
        return False

def clip_raster_by_sectors(
    raster_path: Path,
    geodata_path: Path,
    output_dir: Path,
    job_id: str = None
):

    logging.info(f"🚀 Iniciando recorte ROBUSTO do raster '{raster_path.name}' por setores.")
    
    try:
        # 1. Localizar arquivo raster automaticamente
        try:
            actual_raster_path = find_raster_file(raster_path, job_id)
            logging.info(f"✅ Raster localizado: {actual_raster_path}")
        except FileNotFoundError as e:
            logging.error(f"❌ {e}")
            raise
        
        # 2. Validar integridade do raster
        if not validate_raster_file(actual_raster_path):
            raise ValueError(f"Arquivo raster corrompido: {actual_raster_path}")
        
        # 3. Verificar arquivo GeoJSON
        if not geodata_path.exists():
            raise FileNotFoundError(f"Arquivo GeoJSON não encontrado: {geodata_path}")
        
        try:
            sectors = gpd.read_file(geodata_path)
            if sectors.empty:
                raise ValueError("GeoJSON não contém setores")
            
            if 'CD_SETOR' not in sectors.columns:
                logging.warning(f"⚠️ Coluna 'CD_SETOR' não encontrada. Colunas disponíveis: {list(sectors.columns)}")
                # Tentar usar a primeira coluna como ID
                id_column = sectors.columns[0]
                logging.warning(f"⚠️ Usando coluna '{id_column}' como ID dos setores")
                sectors['CD_SETOR'] = sectors[id_column]
            
            logging.info(f"✅ GeoJSON carregado: {len(sectors)} setores, CRS: {sectors.crs}")
            
        except Exception as e:
            logging.error(f"❌ Erro ao carregar GeoJSON: {e}")
            raise
        
        # 4. Criar diretório de saída
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 5. Executar recorte com tratamento robusto
        successful_clips = 0
        failed_clips = 0
        
        with rasterio.open(actual_raster_path) as src:
            # Reprojetar setores para CRS do raster se necessário
            if sectors.crs != src.crs:
                logging.info(f"🔄 Reprojetando setores de {sectors.crs} para {src.crs}")
                sectors_proj = sectors.to_crs(src.crs)
            else:
                sectors_proj = sectors.copy()
            
            # Verificar sobreposição espacial
            raster_bounds = src.bounds
            sectors_bounds = sectors_proj.total_bounds
            
            logging.info(f"📏 Raster bounds: {raster_bounds}")
            logging.info(f"📏 Setores bounds: {sectors_bounds}")
            
            # Calcular sobreposição
            overlap_x = not (sectors_bounds[2] < raster_bounds[0] or sectors_bounds[0] > raster_bounds[2])
            overlap_y = not (sectors_bounds[3] < raster_bounds[1] or sectors_bounds[1] > raster_bounds[3])
            
            if not (overlap_x and overlap_y):
                logging.error(f"❌ ERRO CRÍTICO: Não há sobreposição espacial!")
                logging.error(f"   Overlap X: {overlap_x}, Overlap Y: {overlap_y}")
                raise ValueError("Raster e setores não se sobrepõem espacialmente")
            
            logging.info(f"✅ Sobreposição espacial confirmada")
            
            # Processar cada setor
            logging.info(f"🔄 Processando {len(sectors_proj)} setores...")
            
            for index, sector in sectors_proj.iterrows():
                sector_id = sector.get('CD_SETOR', f'sector_{index}')
                
                try:
                    # Converter ID para string se necessário
                    if isinstance(sector_id, (int, float)):
                        sector_id = str(int(sector_id))
                    
                    # Verificar se o setor se sobrepõe ao raster ANTES de tentar recortar
                    sector_bounds = sector.geometry.bounds
                    sector_overlaps = not (
                        sector_bounds[2] < raster_bounds[0] or  # setor max_x < raster min_x
                        sector_bounds[0] > raster_bounds[2] or  # setor min_x > raster max_x
                        sector_bounds[3] < raster_bounds[1] or  # setor max_y < raster min_y
                        sector_bounds[1] > raster_bounds[3]     # setor min_y > raster max_y
                    )
                    
                    if not sector_overlaps:
                        # Pular setores que estão fora da área do raster (sem erro)
                        if failed_clips < 3:  # Mostrar apenas os primeiros 3 para não poluir o log
                            logging.debug(f"   ⏭️ Setor {sector_id}: fora da área do raster (pulando)")
                        failed_clips += 1
                        continue
                    
                    # Verificar se a geometria é válida
                    if not sector.geometry.is_valid:
                        logging.warning(f"⚠️ Geometria inválida para setor {sector_id}. Tentando corrigir...")
                        sector.geometry = sector.geometry.buffer(0)  # Tenta corrigir
                    
                    # Aplicar a máscara de recorte
                    geom = [sector.geometry]
                    out_image, out_transform = mask(src, geom, crop=True)
                    
                    # Verificar se o recorte resultou em dados válidos
                    if out_image.size == 0:
                        logging.warning(f"⚠️ Setor {sector_id}: recorte resultou em imagem vazia")
                        failed_clips += 1
                        continue
                    
                    # Contar pixels válidos
                    if src.nodata is not None:
                        valid_pixels = np.sum(~np.isnan(out_image) & (out_image != src.nodata))
                    else:
                        valid_pixels = np.sum(~np.isnan(out_image))
                    
                    if valid_pixels == 0:
                        logging.warning(f"⚠️ Setor {sector_id}: recorte sem dados válidos")
                        failed_clips += 1
                        continue
                    
                    # Atualizar metadados para o arquivo de saída
                    out_meta = src.meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_image.shape[1],
                        "width": out_image.shape[2],
                        "transform": out_transform,
                        "compress": "deflate"
                    })
                    
                    # Definir caminho de saída
                    output_path = output_dir / f"{actual_raster_path.stem}_sector_{sector_id}.tiff"
                    
                    # Salvar arquivo recortado
                    with rasterio.open(output_path, "w", **out_meta) as dest:
                        dest.write(out_image)
                    
                    successful_clips += 1
                    
                    # Log progressivo (mostrar apenas alguns para não poluir)
                    if successful_clips <= 5 or successful_clips % 10 == 0:
                        logging.info(f"✅ Setor {sector_id}: recorte salvo ({valid_pixels} pixels válidos)")
                
                except ValueError as e:
                    if "Input shapes do not overlap raster" in str(e):
                        # Este erro específico significa que o setor está fora da área
                        if failed_clips < 3:  # Mostrar apenas os primeiros 3
                            logging.debug(f"   ⏭️ Setor {sector_id}: fora dos limites do raster")
                        failed_clips += 1
                    else:
                        logging.warning(f"⚠️ Setor {sector_id}: erro de valor - {e}")
                        failed_clips += 1
                    continue
                
                except Exception as e:
                    logging.error(f"❌ Erro inesperado no setor {sector_id}: {e}")
                    failed_clips += 1
                    continue
            
            # Relatório final
            total_sectors = len(sectors_proj)
            success_rate = (successful_clips / total_sectors * 100) if total_sectors > 0 else 0
            overlap_rate = (successful_clips / (successful_clips + failed_clips) * 100) if (successful_clips + failed_clips) > 0 else 0
            
            logging.info(f"\n📊 RESUMO DO RECORTE:")
            logging.info(f"   - Total de setores no GeoJSON: {total_sectors}")
            logging.info(f"   - Setores processados (que se sobrepõem): {successful_clips + failed_clips}")
            logging.info(f"   - Recortes bem-sucedidos: {successful_clips}")
            logging.info(f"   - Recortes falharam: {failed_clips}")
            logging.info(f"   - Taxa de sucesso geral: {success_rate:.1f}%")
            logging.info(f"   - Taxa de sucesso dos setores sobrepostos: {overlap_rate:.1f}%")
            
            if successful_clips == 0:
                raise RuntimeWarning(
                    f"Nenhum setor foi recortado com sucesso. "
                    f"Verifique se há setores que realmente se sobrepõem à área do raster."
                )
            
            if successful_clips < 5:
                logging.warning(f"⚠️ Poucos setores foram processados ({successful_clips}). "
                               f"Isso pode indicar que o raster cobre uma área muito pequena "
                               f"comparado ao GeoJSON usado.")
            
            logging.info(f"✅ Recorte concluído com sucesso! Arquivos salvos em: {output_dir}")
            return True
            
    except FileNotFoundError as e:
        logging.error(f"❌ Arquivo não encontrado: {e}")
        raise
    except ValueError as e:
        logging.error(f"❌ Erro de dados: {e}")
        raise
    except RuntimeWarning as e:
        logging.warning(f"⚠️ Aviso: {e}")
        return False
    except Exception as e:
        logging.error(f"❌ Falha crítica no recorte do raster '{raster_path.name}': {e}")
        traceback.print_exc()
        raise


def clip_raster_by_sectors_original_signature(raster_path, geodata_path, output_dir):

    return clip_raster_by_sectors(
        raster_path=Path(raster_path) if not isinstance(raster_path, Path) else raster_path,
        geodata_path=Path(geodata_path) if not isinstance(geodata_path, Path) else geodata_path,
        output_dir=Path(output_dir) if not isinstance(output_dir, Path) else output_dir,
        job_id=None
    )


if __name__ == '__main__':
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Permitir especificar job_id como argumento
    job_id = sys.argv[1] if len(sys.argv) > 1 else "debug_test"
    
    print(f"🔧 TESTE STANDALONE - Job ID: {job_id}")
    
    # Caminhos baseados na estrutura do projeto
    base_dir = Path.cwd()
    
    # Usar os arquivos encontrados pelo diagnóstico
    s1_file = base_dir / "data" / "raw" / "sentinel" / "analysis_-22.818_-47.069_1754005045_s1.tiff"
    s2_file = base_dir / "data" / "raw" / "sentinel" / "analysis_-22.818_-47.069_1754001033_s2.tiff" 
    geojson_file = base_dir / "data" / "campinas_all.geojson"
    
    # Diretórios de saída
    s1_output_dir = base_dir / "output" / job_id / "processed_images" / "sentinel-1"
    s2_output_dir = base_dir / "output" / job_id / "processed_images" / "sentinel-2"
    
    try:
        print(f"\n🛰️ Processando Sentinel-1...")
        clip_raster_by_sectors(s1_file, geojson_file, s1_output_dir, job_id)
        
        print(f"\n🛰️ Processando Sentinel-2...")
        clip_raster_by_sectors(s2_file, geojson_file, s2_output_dir, job_id)
        
        print(f"\n🎉 TESTE STANDALONE CONCLUÍDO COM SUCESSO!")
        
    except Exception as e:
        print(f"\n❌ TESTE STANDALONE FALHOU: {e}")
        sys.exit(1)