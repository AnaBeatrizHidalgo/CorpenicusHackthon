# diagnostic_risk_level.py
"""
Script de diagnóstico para identificar o problema com final_risk_level
"""
import pandas as pd
import numpy as np
from pathlib import Path

def diagnose_risk_level_problem(job_id="analysis_-22.818_-47.069_1754088501"):
    """
    Diagnostica o problema com a coluna final_risk_level
    """
    print("🔍 DIAGNÓSTICO: Coluna final_risk_level")
    print("=" * 50)
    
    # Caminhos esperados
    output_dir = Path("output") / job_id
    final_features_path = output_dir / "final_features.csv"
    
    print(f"📁 Diretório de saída: {output_dir}")
    print(f"📁 Existe? {output_dir.exists()}")
    print()
    
    # 1. Verificar o arquivo final_features.csv (entrada para risk_assessor)
    print("1️⃣ ANALISANDO ARQUIVO DE FEATURES:")
    print(f"   📄 Final features: {final_features_path}")
    print(f"   ✅ Existe? {final_features_path.exists()}")
    
    if final_features_path.exists():
        try:
            features_df = pd.read_csv(final_features_path)
            print(f"   📊 Shape: {features_df.shape}")
            print(f"   🔗 Colunas: {list(features_df.columns)}")
            
            # Verificar se já tem risk_score ou risk_level
            risk_columns = [col for col in features_df.columns if 'risk' in col.lower()]
            print(f"   🎯 Colunas relacionadas a risco: {risk_columns}")
            
            # Mostrar uma amostra dos dados
            print(f"   📊 Primeiras 3 linhas:")
            print(features_df.head(3).to_string(index=False))
            
        except Exception as e:
            print(f"   ❌ ERRO ao ler final_features.csv: {e}")
            return
    else:
        print("   ❌ Arquivo final_features.csv não encontrado!")
        return
    
    print()
    
    # 2. Simular o que o risk_assessor deveria fazer
    print("2️⃣ SIMULANDO CÁLCULO DE RISK_SCORE:")
    try:
        # Assumindo que o risk_assessor calcula baseado nas features
        test_df = features_df.copy()
        
        # Simular um cálculo simples de risco (exemplo)
        # Normalizar as features para 0-1
        numeric_cols = ['tp_mean', 't2m_mean', 'ndvi_mean', 'vv_mean', 'vh_mean']
        available_cols = [col for col in numeric_cols if col in test_df.columns]
        
        print(f"   🔢 Colunas numéricas disponíveis: {available_cols}")
        
        if available_cols:
            # Exemplo de cálculo de risco (isso seria feito pelo risk_assessor)
            for col in available_cols:
                if test_df[col].notna().any():
                    col_min = test_df[col].min()
                    col_max = test_df[col].max()
                    if col_max != col_min:
                        test_df[f'{col}_normalized'] = (test_df[col] - col_min) / (col_max - col_min)
                    else:
                        test_df[f'{col}_normalized'] = 0.5
            
            # Simular risk_score (média das features normalizadas)
            norm_cols = [col for col in test_df.columns if col.endswith('_normalized')]
            if norm_cols:
                test_df['risk_score'] = test_df[norm_cols].mean(axis=1)
                print(f"   ✅ Risk_score simulado calculado")
                print(f"   📊 Range do risk_score: {test_df['risk_score'].min():.3f} - {test_df['risk_score'].max():.3f}")
            
                # Simular final_risk_level baseado no risk_score
                conditions = [
                    test_df['risk_score'] > 0.75,
                    test_df['risk_score'] > 0.50
                ]
                choices = ['Alto', 'Médio']
                test_df['final_risk_level'] = np.select(conditions, choices, default='Baixo')
                
                print(f"   ✅ final_risk_level simulado criado")
                print(f"   📊 Distribuição de risco:")
                risk_dist = test_df['final_risk_level'].value_counts()
                for level, count in risk_dist.items():
                    print(f"      {level}: {count} setores")
        
    except Exception as e:
        print(f"   ❌ ERRO na simulação: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # 3. Verificar onde o problema está acontecendo
    print("3️⃣ IDENTIFICANDO O PROBLEMA:")
    
    # O warning vem do map_generator, então vamos simular o que ele espera
    expected_columns = ['CD_SETOR', 'risk_score', 'final_risk_level', 'geometry']
    print(f"   📋 Colunas esperadas pelo map_generator: {expected_columns}")
    
    missing_columns = []
    if 'risk_score' not in features_df.columns:
        missing_columns.append('risk_score')
    if 'final_risk_level' not in features_df.columns:
        missing_columns.append('final_risk_level')
    
    print(f"   ❌ Colunas faltando: {missing_columns}")
    
    print()
    print("4️⃣ ANÁLISE DO FLUXO:")
    print("   1. final_features.csv → risk_assessor → adiciona risk_score")
    print("   2. risk_assessor → deveria adicionar final_risk_level")  
    print("   3. map_generator → espera receber final_risk_level")
    print()
    print("   🔍 PROBLEMA IDENTIFICADO:")
    if 'risk_score' not in features_df.columns:
        print("   ❌ risk_assessor não está adicionando risk_score")
    else:
        print("   ❓ risk_assessor adiciona risk_score mas não final_risk_level")
        print("   🔧 SOLUÇÃO: risk_assessor deve criar final_risk_level baseado no risk_score")
    
    return {
        'features_df': features_df,
        'missing_columns': missing_columns
    }

if __name__ == "__main__":
    # Executa o diagnóstico
    result = diagnose_risk_level_problem()
    
    print("\n" + "="*50)
    print("💡 PRÓXIMOS PASSOS:")
    print("1. Execute este script no seu projeto")
    print("2. Compartilhe a saída comigo")
    print("3. Vou identificar qual arquivo precisa ser corrigido")
    print("4. Vou criar a correção específica")