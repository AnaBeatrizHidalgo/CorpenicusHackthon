# diagnostic_union_features.py
"""
Script de diagnóstico para identificar problemas na união de features
"""
import pandas as pd
from pathlib import Path
import os

def diagnose_union_problem(job_id="analysis_-22.818_-47.069_1754087668"):
    """
    Diagnostica problemas na etapa de união de features
    """
    print("🔍 DIAGNÓSTICO: União de Features")
    print("=" * 50)
    
    # Caminhos esperados baseados no log
    output_dir = Path("output") / job_id
    climate_features_path = output_dir / "climate_features.csv"
    image_features_path = output_dir / "image_features.csv"
    final_features_path = output_dir / "final_features.csv"
    
    print(f"📁 Diretório de saída: {output_dir}")
    print(f"📁 Existe? {output_dir.exists()}")
    print()
    
    # 1. Verificar se os arquivos de entrada existem
    print("1️⃣ VERIFICANDO ARQUIVOS DE ENTRADA:")
    print(f"   🌡️ Climate features: {climate_features_path}")
    print(f"   ✅ Existe? {climate_features_path.exists()}")
    if climate_features_path.exists():
        print(f"   📊 Tamanho: {climate_features_path.stat().st_size} bytes")
    
    print(f"   🛰️ Image features: {image_features_path}")
    print(f"   ✅ Existe? {image_features_path.exists()}")
    if image_features_path.exists():
        print(f"   📊 Tamanho: {image_features_path.stat().st_size} bytes")
    print()
    
    # 2. Analisar conteúdo dos arquivos se existem
    climate_df = None
    image_df = None
    
    if climate_features_path.exists():
        try:
            climate_df = pd.read_csv(climate_features_path)
            print("2️⃣ ANÁLISE DO ARQUIVO CLIMÁTICO:")
            print(f"   📏 Shape: {climate_df.shape}")
            print(f"   🔗 Colunas: {list(climate_df.columns)}")
            print(f"   🆔 Tipo da coluna CD_SETOR: {climate_df.dtypes.get('CD_SETOR', 'N/A')}")
            if 'CD_SETOR' in climate_df.columns:
                print(f"   📊 Primeiros valores CD_SETOR: {climate_df['CD_SETOR'].head().tolist()}")
                print(f"   📊 Valores únicos CD_SETOR: {climate_df['CD_SETOR'].nunique()}")
        except Exception as e:
            print(f"   ❌ ERRO ao ler arquivo climático: {e}")
    else:
        print("2️⃣ ❌ ARQUIVO CLIMÁTICO NÃO ENCONTRADO!")
    
    print()
    
    if image_features_path.exists():
        try:
            image_df = pd.read_csv(image_features_path)
            print("3️⃣ ANÁLISE DO ARQUIVO DE IMAGENS:")
            print(f"   📏 Shape: {image_df.shape}")
            print(f"   🔗 Colunas: {list(image_df.columns)}")
            print(f"   🆔 Tipo da coluna CD_SETOR: {image_df.dtypes.get('CD_SETOR', 'N/A')}")
            if 'CD_SETOR' in image_df.columns:
                print(f"   📊 Primeiros valores CD_SETOR: {image_df['CD_SETOR'].head().tolist()}")
                print(f"   📊 Valores únicos CD_SETOR: {image_df['CD_SETOR'].nunique()}")
        except Exception as e:
            print(f"   ❌ ERRO ao ler arquivo de imagens: {e}")
    else:
        print("3️⃣ ❌ ARQUIVO DE IMAGENS NÃO ENCONTRADO!")
    
    print()
    
    # 3. Testar a função de merge se ambos arquivos existem
    if climate_df is not None and image_df is not None:
        print("4️⃣ TESTANDO MERGE:")
        try:
            # Simular o que a função merge_features faz
            climate_df_test = climate_df.copy()
            image_df_test = image_df.copy()
            
            # Verificar se CD_SETOR existe em ambos
            if 'CD_SETOR' not in climate_df_test.columns:
                print("   ❌ CD_SETOR não encontrado no arquivo climático!")
                return
            if 'CD_SETOR' not in image_df_test.columns:
                print("   ❌ CD_SETOR não encontrado no arquivo de imagens!")
                return
            
            # Converter para int como na função original
            climate_df_test['CD_SETOR'] = climate_df_test['CD_SETOR'].astype(int)
            image_df_test['CD_SETOR'] = image_df_test['CD_SETOR'].astype(int)
            
            print(f"   🔄 Tipos após conversão:")
            print(f"      Climate CD_SETOR: {climate_df_test['CD_SETOR'].dtype}")
            print(f"      Image CD_SETOR: {image_df_test['CD_SETOR'].dtype}")
            
            # Fazer o merge
            final_df = pd.merge(climate_df_test, image_df_test, on='CD_SETOR', how='left')
            
            print(f"   ✅ MERGE REALIZADO COM SUCESSO!")
            print(f"   📏 Shape final: {final_df.shape}")
            print(f"   🔗 Colunas finais: {list(final_df.columns)}")
            print(f"   📊 Setores com dados climáticos: {len(climate_df_test)}")
            print(f"   📊 Setores com dados de imagem: {len(image_df_test)}")
            print(f"   📊 Setores no resultado final: {len(final_df)}")
            
            # Verificar se há valores NaN
            nan_counts = final_df.isnull().sum()
            if nan_counts.sum() > 0:
                print(f"   ⚠️ Valores NaN encontrados:")
                for col, count in nan_counts.items():
                    if count > 0:
                        print(f"      {col}: {count} NaN")
            
        except Exception as e:
            print(f"   ❌ ERRO no merge: {e}")
            import traceback
            traceback.print_exc()
    
    print()
    
    # 4. Verificar arquivo final se existe
    print("5️⃣ VERIFICANDO ARQUIVO FINAL:")
    print(f"   📄 Final features: {final_features_path}")
    print(f"   ✅ Existe? {final_features_path.exists()}")
    if final_features_path.exists():
        try:
            final_df = pd.read_csv(final_features_path)
            print(f"   📏 Shape: {final_df.shape}")
            print(f"   🔗 Colunas: {list(final_df.columns)}")
        except Exception as e:
            print(f"   ❌ ERRO ao ler arquivo final: {e}")
    
    print()
    print("6️⃣ POSSÍVEIS PROBLEMAS IDENTIFICADOS:")
    
    problems = []
    if not climate_features_path.exists():
        problems.append("❌ Arquivo climate_features.csv não existe")
    if not image_features_path.exists():
        problems.append("❌ Arquivo image_features.csv não existe")
    if climate_df is not None and climate_df.empty:
        problems.append("❌ Arquivo climático está vazio")
    if image_df is not None and image_df.empty:
        problems.append("❌ Arquivo de imagens está vazio")
    
    if not problems:
        problems.append("✅ Arquivos básicos parecem OK - problema pode ser na função merge_features")
        problems.append("🔧 SOLUÇÃO: Função merge_features precisa retornar o DataFrame final")
    
    for problem in problems:
        print(f"   {problem}")
    
    return {
        'climate_exists': climate_features_path.exists(),
        'image_exists': image_features_path.exists(),
        'climate_df': climate_df,
        'image_df': image_df
    }

if __name__ == "__main__":
    # Executa o diagnóstico
    diagnose_union_problem()
    
    print("\n" + "="*50)
    print("💡 PRÓXIMOS PASSOS:")
    print("1. Execute este script no seu projeto")
    print("2. Compartilhe a saída comigo")
    print("3. Vou criar a correção baseada no diagnóstico")