# src/analysis/risk_assessor.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

def calculate_risk_score(features_df: pd.DataFrame) -> pd.DataFrame:
    print("🎯 Calculando score de risco para cada setor censitário...")
    
    risk_factors = {
        'tp_mean': 0.40,      # Precipitação - FATOR CRÍTICO (r=0.38 na literatura)
        't2m_mean': 0.35,     # Temperatura - MUITO IMPORTANTE (r=0.28-0.30)
        'ndvi_mean': -0.15,   # Vegetação - CORRELAÇÃO NEGATIVA com dengue
        'vv_mean': 0.25,      # SAR VV - Detecção de água/umidade (substituindo humidade)
        'vh_mean': 0.15       # SAR VH - Rugosidade urbana
    }
    
    print(f"⚖️ Pesos CORRIGIDOS baseados na literatura: {risk_factors}")
    
    df = features_df.copy()
    
    if 'CD_SETOR' in df.columns:
        df.set_index('CD_SETOR', inplace=True)
    
    print(f"📊 DataFrame de entrada - Shape: {df.shape}")
    print(f"🔗 Colunas disponíveis: {list(df.columns)}")
    
    # --- NORMALIZAÇÃO MAIS RIGOROSA ---
    print("🔄 Iniciando limpeza e normalização RIGOROSA dos dados...")
    
    OPTIMAL_RANGES = {
        'tp_mean': (0.002, 0.008),    # 60-240mm/mês convertido para m/dia
        't2m_mean': (20, 28),         # Temperatura ótima para Aedes aegypti (°C)
        'ndvi_mean': (0.2, 0.6),      # NDVI médio urbano
        'vv_mean': (-25, -5),         # dB típico para SAR
        'vh_mean': (-30, -10)         # dB típico para SAR
    }
    
    for col in risk_factors:
        print(f"   📈 Processando coluna: {col}")
        
        if col not in df.columns:
            print(f"   ⚠️ Coluna '{col}' não encontrada. Usando valor neutro (0).")
            df[f'{col}_norm'] = 0
            continue
        
        if df[col].isnull().any():
            nan_count = df[col].isnull().sum()
            print(f"   🔧 Encontrados {nan_count} valores NaN em '{col}'")
            median_val = df[col].median()
            
            if pd.notna(median_val):
                df[col] = df[col].fillna(median_val)
                print(f"   ✅ Valores NaN preenchidos com a mediana ({median_val:.4f})")
            else:
                print(f"   ❌ Coluna '{col}' contém apenas valores NaN")
                df[f'{col}_norm'] = 0
                continue

        if col in OPTIMAL_RANGES:
            min_val, max_val = OPTIMAL_RANGES[col]
            
            # Normalização para faixa [0,1] onde valores ótimos = valores altos
            if col == 'ndvi_mean':
                # Para NDVI: valores muito baixos OU muito altos = risco baixo
                # Valores médios = risco alto (área urbana sem cobertura adequada)
                normalized = 1 - np.abs(df[col] - 0.4) / 0.4  # Pico em NDVI = 0.4
                df[f'{col}_norm'] = np.clip(normalized, 0, 1)
            else:
                # Para outras variáveis: normalização linear
                df[f'{col}_norm'] = np.clip((df[col] - min_val) / (max_val - min_val), 0, 1)
        else:
            try:
                scaler = MinMaxScaler()
                df[f'{col}_norm'] = scaler.fit_transform(df[[col]]).flatten()
            except:
                df[f'{col}_norm'] = 0
        
        # Debug
        norm_min = df[f'{col}_norm'].min()
        norm_max = df[f'{col}_norm'].max()
        norm_mean = df[f'{col}_norm'].mean()
        print(f"   ✅ {col}: min={norm_min:.3f}, max={norm_max:.3f}, mean={norm_mean:.3f}")

    print("\n🧮 Calculando score de risco com critérios RIGOROSOS...")
    df['risk_score'] = 0
    
    for col, weight in risk_factors.items():
        norm_col = f'{col}_norm'
        if norm_col in df.columns:
            contribution = df[norm_col] * weight
            df['risk_score'] += contribution
            
            avg_contribution = contribution.mean()
            print(f"   📊 {col}: peso {weight}, contribuição média: {avg_contribution:.4f}")
    
    df['risk_score'] = np.clip(df['risk_score'], 0, 1)
    
    risk_min = df['risk_score'].min()
    risk_max = df['risk_score'].max()
    risk_mean = df['risk_score'].mean()
    risk_std = df['risk_score'].std()
    print(f"   📊 Risk Score - Min: {risk_min:.4f}, Max: {risk_max:.4f}")
    print(f"   📊 Média: {risk_mean:.4f}, Desvio: {risk_std:.4f}")
    
    
    try:
        percentile_90 = df['risk_score'].quantile(0.90)  # Top 10%
        percentile_70 = df['risk_score'].quantile(0.70)  # Top 30%
        
        print(f"   📊 Percentil 90%: {percentile_90:.4f}")
        print(f"   📊 Percentil 70%: {percentile_70:.4f}")
        
        conditions = [
            df['risk_score'] >= percentile_90,  # Top 10% = Alto
            df['risk_score'] >= percentile_70   # Next 20% = Médio
        ]
        choices = ['Alto', 'Médio']
        df['final_risk_level'] = np.select(conditions, choices, default='Baixo')
        
    except Exception as e:
        print(f"   ⚠️ Erro na classificação: {str(e)}")
        conditions = [
            df['risk_score'] > 0.75,  # Apenas > 75% = Alto
            df['risk_score'] > 0.55   # Apenas > 55% = Médio
        ]
        choices = ['Alto', 'Médio']
        df['final_risk_level'] = np.select(conditions, choices, default='Baixo')

    if 'final_risk_level' in df.columns:
        risk_distribution = df['final_risk_level'].value_counts()
        print(f"   📊 Distribuição CORRIGIDA de risco:")
        for level, count in risk_distribution.items():
            percentage = (count / len(df)) * 100
            print(f"      {level}: {count} setores ({percentage:.1f}%)")

    print("\n✅ Cálculo de score de risco CORRIGIDO concluído!")
    
    result_df = df.reset_index()
    
    for col in result_df.columns:
        if hasattr(result_df[col], 'cat'):
            result_df[col] = result_df[col].astype(str)
    
    return result_df