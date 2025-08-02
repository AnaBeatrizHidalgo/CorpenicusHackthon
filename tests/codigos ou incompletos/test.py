
#!/usr/bin/env python3
# test_clip_fix.py
"""
Script para testar a correção do problema de recorte.
"""

import sys
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_clip_fix():
    """Testa a função corrigida de recorte"""
    
    # Arquivos identificados pelo diagnóstico
    base_dir = Path.cwd()
    s1_file = base_dir / "data" / "raw" / "sentinel" / "analysis_-22.818_-47.069_1754005045_s1.tiff"
    s2_file = base_dir / "data" / "raw" / "sentinel" / "analysis_-22.818_-47.069_1754001033_s2.tiff"
    geojson_file = base_dir / "data" / "campinas_all.geojson"
    
    job_id = "debug_test"
    s1_output_dir = base_dir / "output" / job_id / "processed_images" / "sentinel-1"
    s2_output_dir = base_dir / "output" / job_id / "processed_images" / "sentinel-2"
    
    print(f"🧪 === TESTE DA CORREÇÃO DE RECORTE ===")
    print(f"Job ID: {job_id}")
    print(f"S1 File: {s1_file}")
    print(f"S2 File: {s2_file}")
    print(f"GeoJSON: {geojson_file}")
    
    # Importar a função corrigida
    try:
        # Assumindo que você salvou o código corrigido como image_processor_fixed.py
        sys.path.insert(0, str(Path(__file__).parent))
        from image_processor_fixed import clip_raster_by_sectors
        print(f"✅ Função corrigida importada com sucesso")
    except ImportError as e:
        print(f"❌ Erro ao importar função corrigida: {e}")
        print(f"💡 Certifique-se de salvar o código corrigido como 'image_processor_fixed.py'")
        return False
    
    # Testar S1
    try:
        print(f"\n🛰️ === TESTANDO SENTINEL-1 ===")
        result_s1 = clip_raster_by_sectors(s1_file, geojson_file, s1_output_dir, job_id)
        if result_s1:
            print(f"✅ Sentinel-1 processado com sucesso!")
        else:
            print(f"⚠️ Sentinel-1 processado com avisos")
    except Exception as e:
        print(f"❌ Erro no Sentinel-1: {e}")
        return False
    
    # Testar S2
    try:
        print(f"\n🛰️ === TESTANDO SENTINEL-2 ===")
        result_s2 = clip_raster_by_sectors(s2_file, geojson_file, s2_output_dir, job_id)
        if result_s2:
            print(f"✅ Sentinel-2 processado com sucesso!")
        else:
            print(f"⚠️ Sentinel-2 processado com avisos")
    except Exception as e:
        print(f"❌ Erro no Sentinel-2: {e}")
        return False
    
    # Verificar resultados
    print(f"\n📊 === VERIFICAÇÃO DOS RESULTADOS ===")
    
    s1_files = list(s1_output_dir.glob("*.tiff")) if s1_output_dir.exists() else []
    s2_files = list(s2_output_dir.glob("*.tiff")) if s2_output_dir.exists() else []
    
    print(f"Arquivos S1 gerados: {len(s1_files)}")
    print(f"Arquivos S2 gerados: {len(s2_files)}")
    
    if s1_files:
        print(f"📁 Exemplos S1:")
        for f in s1_files[:3]:  # Mostrar apenas 3 exemplos
            print(f"   {f.name}")
        if len(s1_files) > 3:
            print(f"   ... e mais {len(s1_files)-3} arquivos")
    
    if s2_files:
        print(f"📁 Exemplos S2:")
        for f in s2_files[:3]:  # Mostrar apenas 3 exemplos
            print(f"   {f.name}")
        if len(s2_files) > 3:
            print(f"   ... e mais {len(s2_files)-3} arquivos")
    
    total_files = len(s1_files) + len(s2_files)
    
    if total_files > 0:
        print(f"\n🎉 TESTE CONCLUÍDO COM SUCESSO!")
        print(f"✅ Total de {total_files} arquivos de recorte gerados")
        return True
    else:
        print(f"\n⚠️ TESTE CONCLUÍDO COM AVISOS")
        print(f"❌ Nenhum arquivo de recorte foi gerado")
        return False

if __name__ == "__main__":
    success = test_clip_fix()
    sys.exit(0 if success else 1)