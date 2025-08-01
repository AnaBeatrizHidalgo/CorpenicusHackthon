# src/analysis/risk_assessor.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

def calculate_risk_score(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a normalized risk score, handling edge cases where
    feature values are constant or NaN.
    
    Args:
        features_df (pd.DataFrame): DataFrame com features climáticas e de imagem
        
    Returns:
        pd.DataFrame: DataFrame com risk_score e final_risk_level adicionados
    """
    print("🎯 Calculando score de risco para cada setor censitário...")
    
    risk_factors = {
        'ndvi_mean': 0.20, 
        't2m_mean': 0.40, 
        'tp_mean': 0.30,
        'vv_mean': 0.05, 
        'vh_mean': 0.05
    }
    
    print(f"⚖️ Pesos dos fatores de risco: {risk_factors}")
    
    df = features_df.copy()
    original_index_name = df.index.name
    
    # Usar CD_SETOR como índice temporário se existir
    if 'CD_SETOR' in df.columns:
        df.set_index('CD_SETOR', inplace=True)
    
    print(f"📊 DataFrame de entrada - Shape: {df.shape}")
    print(f"🔗 Colunas disponíveis: {list(df.columns)}")
    
    # --- Data Cleaning and Normalization ---
    print("🔄 Iniciando limpeza e normalização dos dados...")
    
    for col in risk_factors:
        print(f"   📈 Processando coluna: {col}")
        
        if col not in df.columns:
            print(f"   ⚠️ Coluna '{col}' não encontrada. Usando valor neutro (0).")
            df[f'{col}_norm'] = 0  # Assign a neutral value if column is missing
            continue
        
        # Fill NaN values with the column's mean
        if df[col].isnull().any():
            nan_count = df[col].isnull().sum()
            print(f"   🔧 Encontrados {nan_count} valores NaN em '{col}'")
            
            # Calculate mean ignoring NaNs
            mean_val = df[col].mean() 
            
            # Only fill if the mean is a valid number (i.e., the column wasn't all NaN)
            if pd.notna(mean_val):
                df[col] = df[col].fillna(mean_val)
                print(f"   ✅ Valores NaN preenchidos com a média ({mean_val:.4f})")
            else:
                # If the whole column is NaN, the mean will be NaN. Keep it that way.
                print(f"   ❌ Coluna '{col}' contém apenas valores NaN")

        # If after filling, the column is STILL all NaN (because it was empty), fill with 0
        if df[col].isnull().all():
            df[f'{col}_norm'] = 0
            print(f"   ⚠️ Coluna '{col}' completamente vazia. Tratando como risco 0.")
            continue
        
        # Check if all values are the same (no variance)
        unique_values = df[col].nunique()
        if unique_values <= 1:
            df[f'{col}_norm'] = 0.5  # Neutral value for no variance
            print(f"   ⚠️ Coluna '{col}' sem variância ({unique_values} valores únicos). Usando valor neutro (0.5).")
            continue
            
        # Normalize the column from 0 to 1
        try:
            col_min = df[col].min()
            col_max = df[col].max()
            print(f"   📊 Range original: {col_min:.4f} - {col_max:.4f}")
            
            scaler = MinMaxScaler()
            df[f'{col}_norm'] = scaler.fit_transform(df[[col]]).flatten()
            
            norm_min = df[f'{col}_norm'].min()
            norm_max = df[f'{col}_norm'].max()
            print(f"   ✅ Normalização concluída: {norm_min:.4f} - {norm_max:.4f}")
            
        except Exception as e:
            print(f"   ❌ Erro na normalização de '{col}': {str(e)}")
            df[f'{col}_norm'] = 0

    # --- Risk Score Calculation ---
    print("\n🧮 Calculando score de risco...")
    df['risk_score'] = 0
    
    for col, weight in risk_factors.items():
        norm_col = f'{col}_norm'
        if norm_col in df.columns:
            if col == 'ndvi_mean':
                # Inverted U-shaped curve for NDVI (medium values = higher risk)
                contribution = (-4 * df[norm_col]**2 + 4 * df[norm_col]) * weight
                print(f"   🌱 NDVI (curva invertida): peso {weight}")
            else:
                contribution = df[norm_col] * weight
                print(f"   📊 {col}: peso {weight}")
            
            df['risk_score'] += contribution
            
            # Debug: mostrar contribuição média
            avg_contribution = contribution.mean()
            print(f"      💡 Contribuição média: {avg_contribution:.4f}")
    
    # Ensure risk_score is between 0 and 1
    df['risk_score'] = df['risk_score'].clip(0, 1)
    
    # Fill any remaining NaN values in risk_score
    nan_risk_count = df['risk_score'].isnull().sum()
    if nan_risk_count > 0:
        print(f"   🔧 Preenchendo {nan_risk_count} valores NaN no risk_score com 0.5")
        df['risk_score'] = df['risk_score'].fillna(0.5)  # Neutral risk for undefined cases
    
    # Estatísticas do risk_score
    risk_min = df['risk_score'].min()
    risk_max = df['risk_score'].max()
    risk_mean = df['risk_score'].mean()
    print(f"   📊 Risk Score - Min: {risk_min:.4f}, Max: {risk_max:.4f}, Média: {risk_mean:.4f}")
    
    # --- ROBUST RISK LEVEL CLASSIFICATION ---
    print("\n🏷️ Criando classificação de nível de risco...")
    
    # Check for valid scores before attempting to create bins
    valid_scores = df['risk_score'].dropna()
    
    if valid_scores.empty:
        # Case 1: All scores are NaN
        df['final_risk_level'] = 'Indeterminado'
        print("   ❌ Todos os scores são NaN. Nível de risco: Indeterminado.")
        
    elif valid_scores.nunique() < 3:
        # Case 2: Not enough unique score values to create 3 bins.
        # Assign a level based on the average score.
        mean_score = valid_scores.mean()
        if mean_score > 0.6:
            level = 'Alto'
        elif mean_score > 0.3:
            level = 'Médio'
        else:
            level = 'Baixo'
        df['final_risk_level'] = level
        print(f"   ⚠️ Poucos valores únicos para criar categorias múltiplas.")
        print(f"   📊 Atribuindo nível único: {level} (score médio: {mean_score:.4f})")
        
    else:
        try:
            # Case 3: Enough unique scores to create quantile-based bins.
            # Using qcut is safer as it handles duplicate bin edges.
            df['final_risk_level'] = pd.qcut(
                df['risk_score'], 
                q=[0, 0.33, 0.66, 1.0], 
                labels=['Baixo', 'Médio', 'Alto'],
                duplicates='drop'
            )
            
            # Convert categorical to string to avoid GeoJSON issues later
            df['final_risk_level'] = df['final_risk_level'].astype(str)
            print("   ✅ Classificação baseada em quantis (33%, 66%, 100%)")
            
        except Exception as e:
            print(f"   ⚠️ Erro na classificação por quantis: {str(e)}")
            print("   🔄 Usando classificação por limites fixos...")
            
            # Fallback to simple thresholding
            conditions = [
                df['risk_score'] > 0.66,
                df['risk_score'] > 0.33
            ]
            choices = ['Alto', 'Médio']
            df['final_risk_level'] = np.select(conditions, choices, default='Baixo')

    # Mostrar distribuição final
    if 'final_risk_level' in df.columns:
        risk_distribution = df['final_risk_level'].value_counts()
        print(f"   📊 Distribuição final de risco:")
        for level, count in risk_distribution.items():
            percentage = (count / len(df)) * 100
            print(f"      {level}: {count} setores ({percentage:.1f}%)")

    print("\n✅ Cálculo de score de risco concluído!")
    
    # Ensure all columns are in appropriate formats
    result_df = df.reset_index()
    
    # Convert any remaining categorical columns to string
    for col in result_df.columns:
        if hasattr(result_df[col], 'cat'):
            result_df[col] = result_df[col].astype(str)
    
    # Verificação final
    print(f"📋 Colunas no resultado final: {list(result_df.columns)}")
    
    required_columns = ['risk_score', 'final_risk_level']
    missing_cols = [col for col in required_columns if col not in result_df.columns]
    if missing_cols:
        print(f"❌ ERRO: Colunas obrigatórias faltando: {missing_cols}")
    else:
        print(f"✅ Todas as colunas obrigatórias presentes: {required_columns}")
    
    return result_df