#!/usr/bin/env python3
# diagnostic_complete_fix.py
"""
Script completo para diagnosticar e corrigir problemas no pipeline de processamento de imagens.
Identifica onde estão os arquivos e corrige os caminhos automaticamente.
"""

import logging
import os
import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import traceback
import glob

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PipelineDiagnostic:
    def __init__(self, job_id="debug_test"):
        self.job_id = job_id
        self.base_dir = Path.cwd()
        self.output_dir = self.base_dir / "output" / job_id
        
        # Possíveis localizações dos arquivos
        self.possible_sentinel_dirs = [
            self.base_dir / "data" / "raw" / "sentinel",
            self.base_dir / "data" / "processed",
            self.base_dir / "data",
            self.output_dir,
        ]
        
        # Arquivos que estamos procurando
        self.target_files = {
            's1_file': None,
            's2_file': None,
            'geojson_file': None
        }
    
    def find_files(self):
        """Localiza automaticamente os arquivos necessários"""
        print(f"\n🔍 === LOCALIZANDO ARQUIVOS AUTOMATICAMENTE ===")
        
        # Procurar arquivos S1
        s1_patterns = [
            f"*{self.job_id}*s1*.tiff",
            f"*{self.job_id}*s1*.tif", 
            "*s1*.tiff",
            "*s1*.tif",
            "*S1*.tiff",
            "*S1*.tif"
        ]
        
        print(f"🛰️ Procurando arquivos Sentinel-1...")
        for directory in self.possible_sentinel_dirs:
            if not directory.exists():
                continue
            print(f"   Verificando: {directory}")
            for pattern in s1_patterns:
                files = list(directory.glob(pattern))
                if files:
                    self.target_files['s1_file'] = files[0]  # Pega o primeiro encontrado
                    print(f"   ✅ S1 encontrado: {self.target_files['s1_file']}")
                    break
            if self.target_files['s1_file']:
                break
        
        # Procurar arquivos S2
        s2_patterns = [
            f"*{self.job_id}*s2*.tiff",
            f"*{self.job_id}*s2*.tif",
            "*s2*.tiff", 
            "*s2*.tif",
            "*S2*.tiff",
            "*S2*.tif"
        ]
        
        print(f"🛰️ Procurando arquivos Sentinel-2...")
        for directory in self.possible_sentinel_dirs:
            if not directory.exists():
                continue
            print(f"   Verificando: {directory}")
            for pattern in s2_patterns:
                files = list(directory.glob(pattern))
                if files:
                    self.target_files['s2_file'] = files[0]
                    print(f"   ✅ S2 encontrado: {self.target_files['s2_file']}")
                    break
            if self.target_files['s2_file']:
                break
        
        # Procurar GeoJSON
        geojson_path = self.output_dir / "area_of_interest.geojson"
        if geojson_path.exists():
            self.target_files['geojson_file'] = geojson_path
            print(f"✅ GeoJSON encontrado: {geojson_path}")
        else:
            # Procurar em outros lugares
            geojson_patterns = ["*.geojson", "*area*.geojson", "*setores*.geojson"]
            for directory in [self.output_dir, self.base_dir / "data"]:
                if not directory.exists():
                    continue
                for pattern in geojson_patterns:
                    files = list(directory.rglob(pattern))
                    if files:
                        self.target_files['geojson_file'] = files[0]
                        print(f"✅ GeoJSON encontrado: {self.target_files['geojson_file']}")
                        break
                if self.target_files['geojson_file']:
                    break
        
        # Relatório final
        print(f"\n📊 === RESULTADO DA BUSCA ===")
        for file_type, file_path in self.target_files.items():
            if file_path:
                print(f"✅ {file_type}: {file_path}")
            else:
                print(f"❌ {file_type}: NÃO ENCONTRADO")
        
        return all(self.target_files.values())
    
    def diagnose_files(self):
        """Diagnóstica a integridade dos arquivos encontrados"""
        print(f"\n🔬 === DIAGNÓSTICO DE INTEGRIDADE ===")
        
        # Verificar S1
        if self.target_files['s1_file']:
            try:
                with rasterio.open(self.target_files['s1_file']) as src:
                    print(f"✅ S1 válido - Bandas: {src.count}, CRS: {src.crs}, Shape: {src.width}x{src.height}")
                    # Verificar se tem dados
                    sample = src.read(1, window=rasterio.windows.Window(0, 0, 50, 50))
                    valid_pixels = np.sum(~np.isnan(sample) & (sample != src.nodata))
                    print(f"   Pixels válidos na amostra: {valid_pixels}/2500")
            except Exception as e:
                print(f"❌ S1 corrompido: {e}")
                return False
        
        # Verificar S2
        if self.target_files['s2_file']:
            try:
                with rasterio.open(self.target_files['s2_file']) as src:
                    print(f"✅ S2 válido - Bandas: {src.count}, CRS: {src.crs}, Shape: {src.width}x{src.height}")
            except Exception as e:
                print(f"❌ S2 corrompido: {e}")
                return False
        
        # Verificar GeoJSON
        if self.target_files['geojson_file']:
            try:
                gdf = gpd.read_file(self.target_files['geojson_file'])
                print(f"✅ GeoJSON válido - {len(gdf)} setores, CRS: {gdf.crs}")
                if 'CD_SETOR' in gdf.columns:
                    print(f"   Coluna CD_SETOR encontrada com {gdf['CD_SETOR'].nunique()} valores únicos")
                else:
                    print(f"   ⚠️ Coluna CD_SETOR não encontrada. Colunas: {list(gdf.columns)}")
            except Exception as e:
                print(f"❌ GeoJSON corrompido: {e}")
                return False
        
        return True
    
    def test_clipping(self):
        """Testa o processo de recorte com um setor"""
        print(f"\n✂️ === TESTE DE RECORTE ===")
        
        if not all(self.target_files.values()):
            print("❌ Nem todos os arquivos foram encontrados. Não é possível testar recorte.")
            return False
        
        try:
            # Carregar dados
            gdf = gpd.read_file(self.target_files['geojson_file'])
            
            with rasterio.open(self.target_files['s1_file']) as src:
                # Reprojetar setores se necessário
                gdf_proj = gdf.to_crs(src.crs)
                
                # Verificar sobreposição
                raster_bounds = src.bounds
                sectors_bounds = gdf_proj.total_bounds
                
                print(f"Raster bounds: {raster_bounds}")
                print(f"Setores bounds: {sectors_bounds}")
                
                # Teste de sobreposição
                overlap_x = not (sectors_bounds[2] < raster_bounds[0] or sectors_bounds[0] > raster_bounds[2])
                overlap_y = not (sectors_bounds[3] < raster_bounds[1] or sectors_bounds[1] > raster_bounds[3])
                
                if not (overlap_x and overlap_y):
                    print(f"❌ PROBLEMA CRÍTICO: Não há sobreposição espacial!")
                    print(f"   Overlap X: {overlap_x}, Overlap Y: {overlap_y}")
                    return False
                
                print(f"✅ Há sobreposição espacial")
                
                # Testar recorte no primeiro setor
                first_sector = gdf_proj.iloc[0]
                sector_id = first_sector['CD_SETOR'] if 'CD_SETOR' in gdf_proj.columns else f"sector_{0}"
                
                try:
                    out_image, out_transform = mask(src, [first_sector.geometry], crop=True)
                    valid_pixels = np.sum(~np.isnan(out_image) & (out_image != src.nodata) if src.nodata is not None else ~np.isnan(out_image))
                    
                    print(f"✅ Teste de recorte bem-sucedido!")
                    print(f"   Setor testado: {sector_id}")
                    print(f"   Shape do recorte: {out_image.shape}")
                    print(f"   Pixels válidos: {valid_pixels}")
                    
                    return True
                    
                except Exception as e:
                    print(f"❌ Falha no recorte do setor {sector_id}: {e}")
                    return False
                    
        except Exception as e:
            print(f"❌ Erro durante teste de recorte: {e}")
            traceback.print_exc()
            return False
    
    def fix_and_run_clipping(self):
        """Executa o recorte corrigido para todos os setores"""
        print(f"\n🔧 === EXECUTANDO RECORTE CORRIGIDO ===")
        
        if not all(self.target_files.values()):
            print("❌ Arquivos necessários não encontrados.")
            return False
        
        # Criar diretório de saída
        s1_output_dir = self.output_dir / "processed_images" / "sentinel-1"
        s2_output_dir = self.output_dir / "processed_images" / "sentinel-2"
        
        s1_output_dir.mkdir(parents=True, exist_ok=True)
        s2_output_dir.mkdir(parents=True, exist_ok=True)
        
        success_count = 0
        total_count = 0
        
        try:
            gdf = gpd.read_file(self.target_files['geojson_file'])
            
            # Processar S1
            if self.target_files['s1_file']:
                print(f"🛰️ Processando Sentinel-1...")
                success_count += self._clip_single_raster(
                    self.target_files['s1_file'], gdf, s1_output_dir, "s1"
                )
                total_count += 1
            
            # Processar S2  
            if self.target_files['s2_file']:
                print(f"🛰️ Processando Sentinel-2...")
                success_count += self._clip_single_raster(
                    self.target_files['s2_file'], gdf, s2_output_dir, "s2"
                )
                total_count += 1
            
            print(f"\n📊 === RESULTADO FINAL ===")
            print(f"Processamento concluído: {success_count}/{total_count} rasters processados com sucesso")
            
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Erro durante processamento: {e}")
            traceback.print_exc()
            return False
    
    def _clip_single_raster(self, raster_path, gdf, output_dir, sensor_name):
        """Processa um único raster"""
        try:
            with rasterio.open(raster_path) as src:
                gdf_proj = gdf.to_crs(src.crs)
                
                successful_clips = 0
                failed_clips = 0
                
                for idx, sector in gdf_proj.iterrows():
                    sector_id = sector.get('CD_SETOR', f'sector_{idx}')
                    
                    try:
                        # Converter ID para string se necessário
                        if isinstance(sector_id, (int, float)):
                            sector_id = str(int(sector_id))
                        
                        # Aplicar máscara
                        out_image, out_transform = mask(src, [sector.geometry], crop=True)
                        
                        # Verificar se tem dados válidos
                        if out_image.size == 0:
                            print(f"   ⚠️ Setor {sector_id}: recorte vazio")
                            failed_clips += 1
                            continue
                        
                        valid_pixels = np.sum(~np.isnan(out_image) & (out_image != src.nodata) if src.nodata is not None else ~np.isnan(out_image))
                        
                        if valid_pixels == 0:
                            print(f"   ⚠️ Setor {sector_id}: sem dados válidos")
                            failed_clips += 1
                            continue
                        
                        # Salvar arquivo
                        out_meta = src.meta.copy()
                        out_meta.update({
                            "driver": "GTiff",
                            "height": out_image.shape[1],
                            "width": out_image.shape[2],
                            "transform": out_transform,
                            "compress": "deflate"
                        })
                        
                        output_path = output_dir / f"{raster_path.stem}_sector_{sector_id}.tiff"
                        
                        with rasterio.open(output_path, "w", **out_meta) as dest:
                            dest.write(out_image)
                        
                        successful_clips += 1
                        if successful_clips <= 5:  # Mostrar apenas os primeiros 5
                            print(f"   ✅ Setor {sector_id}: salvo com {valid_pixels} pixels válidos")
                        
                    except ValueError as e:
                        if "Input shapes do not overlap raster" in str(e):
                            print(f"   ⚠️ Setor {sector_id}: fora dos limites")
                        else:
                            print(f"   ⚠️ Setor {sector_id}: erro - {e}")
                        failed_clips += 1
                        continue
                    
                    except Exception as e:
                        print(f"   ❌ Setor {sector_id}: erro inesperado - {e}")
                        failed_clips += 1
                        continue
                
                total_sectors = len(gdf_proj)
                success_rate = (successful_clips / total_sectors * 100) if total_sectors > 0 else 0
                
                print(f"   📊 {sensor_name.upper()}: {successful_clips}/{total_sectors} setores processados ({success_rate:.1f}% sucesso)")
                
                return 1 if successful_clips > 0 else 0
                
        except Exception as e:
            print(f"❌ Erro ao processar {sensor_name}: {e}")
            return 0
    
    def run_complete_diagnostic(self):
        """Executa diagnóstico completo"""
        print(f"🚀 === DIAGNÓSTICO COMPLETO DO PIPELINE ===")
        print(f"Job ID: {self.job_id}")
        print(f"Diretório base: {self.base_dir}")
        print(f"Diretório de saída: {self.output_dir}")
        
        # Passo 1: Encontrar arquivos
        if not self.find_files():
            print(f"\n❌ FALHA CRÍTICA: Arquivos necessários não foram encontrados.")
            self._suggest_solutions()
            return False
        
        # Passo 2: Verificar integridade
        if not self.diagnose_files():
            print(f"\n❌ FALHA CRÍTICA: Arquivos corrompidos ou inválidos.")
            return False
        
        # Passo 3: Testar recorte
        if not self.test_clipping():
            print(f"\n❌ FALHA CRÍTICA: Teste de recorte falhou.")
            return False
        
        # Passo 4: Executar processamento completo
        if self.fix_and_run_clipping():
            print(f"\n🎉 SUCESSO TOTAL: Pipeline de recorte executado com sucesso!")
            return True
        else:
            print(f"\n❌ FALHA NO PROCESSAMENTO: Recorte não foi bem-sucedido.")
            return False
    
    def _suggest_solutions(self):
        """Sugere soluções baseadas nos problemas encontrados"""
        print(f"\n💡 === SUGESTÕES DE SOLUÇÃO ===")
        
        if not self.target_files['s1_file']:
            print(f"📁 Arquivo S1 não encontrado:")
            print(f"   1. Verifique se o download foi bem-sucedido")
            print(f"   2. Procure por arquivos .tiff em: {self.base_dir / 'data'}")
            print(f"   3. Execute novamente o download com job_id correto")
        
        if not self.target_files['s2_file']:
            print(f"📁 Arquivo S2 não encontrado:")
            print(f"   1. Verifique se o download foi bem-sucedido")
            print(f"   2. Procure por arquivos .tiff em: {self.base_dir / 'data'}")
        
        if not self.target_files['geojson_file']:
            print(f"📁 Arquivo GeoJSON não encontrado:")
            print(f"   1. Verifique se a área de estudo foi criada")
            print(f"   2. Procure por arquivos .geojson em: {self.output_dir}")


def main():
    """Função principal"""
    # Permitir especificar job_id como argumento
    job_id = sys.argv[1] if len(sys.argv) > 1 else "debug_test"
    
    print(f"🔧 Iniciando diagnóstico completo para job_id: {job_id}")
    
    diagnostic = PipelineDiagnostic(job_id=job_id)
    
    try:
        success = diagnostic.run_complete_diagnostic() 
        
        if success:
            print(f"\n✅ DIAGNÓSTICO CONCLUÍDO COM SUCESSO!")
            print(f"🎯 O pipeline de recorte agora deve funcionar normalmente.")
        else:
            print(f"\n❌ DIAGNÓSTICO ENCONTROU PROBLEMAS NÃO RESOLVIDOS.")
            print(f"📋 Verifique as sugestões acima e tente novamente.")
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Diagnóstico interrompido pelo usuário.")
    except Exception as e:
        print(f"\n💥 ERRO INESPERADO: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()